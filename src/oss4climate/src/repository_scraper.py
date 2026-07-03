"""
Repository scraper that manages scraping data to a SQLModel-backed database.

This module provides the RepositoryScraper class which orchestrates the full
scraping lifecycle:
1. Sync from TOML — reconcile TOML with DB (upsert orgs, discover repos, prune inactive)
2. Scrape active repos — fetch fresh data for repos past their refresh threshold
3. Export — write results to feather file, summary TOML, and failures TOML
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from oss4climate.src.crawler import scrape_all_targets
from oss4climate.src.database.repos import (
    Repository,
    get_active_repos_to_scrape,
    get_all_active_repos,
    get_engine,
    mark_repos_inactive,
    reset_repo_error,
    set_repo_error,
    upsert_organisation,
    upsert_repository,
)
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.models import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.parsers import ParsingTargets
from oss4climate.src.parsers.git_platforms.bitbucket_io import BitbucketScraper
from oss4climate.src.parsers.git_platforms.codeberg_io import CodebergScraper
from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper

# Platform scraper mapping
PLATFORM_SCRAPERS = {
    "github": GithubScraper,
    "gitlab": GitlabScraper,
    "codeberg": CodebergScraper,
    "bitbucket": BitbucketScraper,
}


class RepositoryScraper:
    """
    Orchestrates the full scraping lifecycle for repositories stored in a SQLModel database.

    The scraper:
    - Reads the TOML index as the source of truth for which orgs/repos to track
    - Stores scraped data in a SQLModel-backed database
    - Supports incremental re-scraping based on a refresh interval
    - Exports results to feather file, summary TOML, and failures TOML
    """

    def __init__(
        self,
        refresh_days: int = 28,
        cache_lifetime: timedelta | None = None,
    ):
        """
        Initialize the repository scraper.

        :param refresh_days: Default number of days since last scrape before re-scraping
        :param cache_lifetime: Optional cache lifetime for API responses
        """
        self.refresh_days = refresh_days
        self.cache_lifetime = cache_lifetime

    def _get_platform_from_url(self, url: str) -> tuple[str, str]:
        """
        Extract platform name and repo path from a URL or path.

        :param url: URL or path (e.g., "https://github.com/oss4climate/oss4climate" or "github.com/oss4climate/oss4climate")
        :return: Tuple of (platform_name, repo_path)
        """
        url_lower = url.lower()
        if "github.com" in url_lower:
            platform = "github"
            path = url_lower.replace("https://github.com/", "").replace(
                "http://github.com/", ""
            )
        elif "gitlab.com" in url_lower or url_lower.startswith("https://git."):
            platform = "gitlab"
            # For self-hosted GitLab, extract host + path
            if url_lower.startswith("https://"):
                rest = url_lower.replace("https://", "", 1)
                host, path = rest.split("/", 1)
                path = f"{host}/{path}"
            else:
                path = url_lower
        elif "codeberg.org" in url_lower:
            platform = "codeberg"
            path = url_lower.replace("https://codeberg.org/", "").replace(
                "http://codeberg.org/", ""
            )
        elif "bitbucket.org" in url_lower:
            platform = "bitbucket"
            path = url_lower.replace("https://bitbucket.org/", "").replace(
                "http://bitbucket.org/", ""
            )
        else:
            platform = "unknown"
            path = url_lower

        return platform, path

    def _get_repo_id(self, url: str) -> str:
        """
        Get the repository ID in the format "host/repo_path".

        :param url: URL or path
        :return: Repository ID (e.g., "github.com/oss4climate/oss4climate")
        """
        platform, path = self._get_platform_from_url(url)
        if platform == "unknown":
            # Try to extract host from URL
            if "://" in url:
                host = url.split("://")[1].split("/")[0]
                return (
                    f"{host}/{url.split('/', 3)[-1] if len(url.split('/')) > 3 else ''}"
                )
            return url
        return (
            f"{platform}.{'com' if platform != 'gitlab' else ''}/{path}"
            if platform != "gitlab"
            else path
        )

    def _get_org_id(self, url: str) -> str:
        """
        Get the organisation ID in the format "host/org_path".

        :param url: URL or path
        :return: Organisation ID (e.g., "github.com/oss4climate")
        """
        platform, path = self._get_platform_from_url(url)
        if platform == "unknown":
            if "://" in url:
                host = url.split("://")[1].split("/")[0]
                org_path = (
                    url.split("/", 3)[-1].split("/")[0]
                    if len(url.split("/")) > 3
                    else ""
                )
                return f"{host}/{org_path}"
            return url
        return (
            f"{platform}.{'com' if platform != 'gitlab' else ''}/{path.split('/')[0]}"
            if platform != "gitlab"
            else f"{path.split('/')[0]}"
        )

    def _extract_host_and_path(self, url: str) -> tuple[str, str]:
        """
        Extract host and path from a URL.

        :param url: URL
        :return: Tuple of (host, path)
        """
        if "://" in url:
            rest = url.split("://")[1]
        else:
            rest = url
        host = rest.split("/")[0]
        path = rest[len(host) :].lstrip("/")
        return host, path

    def sync_from_toml(self, toml_path: str) -> None:
        """
        Synchronize the database with the TOML index file.

        This method:
        1. Reads the TOML to get the current list of orgs/repos
        2. For each org/group, fetches metadata and discovers repos
        3. For each explicit repo, records it in the DB
        4. Marks repos as inactive if they're no longer in scope

        :param toml_path: Path to the TOML index file
        """
        log_info(f"Syncing from TOML: {toml_path}")

        # Load targets from TOML
        targets = ParsingTargets.from_toml(toml_path)

        # Collect all repo IDs that should be active
        active_repo_ids: set[str] = set()
        active_org_ids: set[str] = set()

        with Session(get_engine()) as session:
            # Process GitHub organisations
            for org_url in targets.github_organisations:
                try:
                    scraper = GithubScraper(cache_lifetime=self.cache_lifetime)
                    org_id = self._get_org_id(org_url)
                    active_org_ids.add(org_id)

                    # Fetch org metadata
                    org_data = scraper.fetch_organisation_details(
                        org_url.split("github.com/")[-1]
                    )
                    org_data["id"] = org_id
                    upsert_organisation(session, org_data)

                    # Discover repos
                    repos = scraper.fetch_repositories_in_organisation(org_url)
                    for repo_name, repo_url in repos.items():
                        repo_id = self._get_repo_id(repo_url)
                        active_repo_ids.add(repo_id)
                        # Upsert repo with minimal data (full scrape happens later)
                        upsert_repository(
                            session,
                            {
                                "id": repo_id,
                                "organisation_id": org_id,
                                "name": repo_name,
                                "url": repo_url,
                            },
                        )
                except Exception as e:
                    session.rollback()
                    log_warning(f"Failed to sync GitHub org {org_url}: {e}")
                    # Still upsert the org with error info
                    org_id = self._get_org_id(org_url)
                    active_org_ids.add(org_id)
                    upsert_organisation(
                        session,
                        {
                            "id": org_id,
                            "last_error": str(e),
                            "error_count": 1,
                        },
                    )

            # Process GitHub explicit repos
            for repo_url in targets.github_repositories:
                repo_id = self._get_repo_id(repo_url)
                active_repo_ids.add(repo_id)
                upsert_repository(
                    session,
                    {
                        "id": repo_id,
                        "url": repo_url,
                    },
                )

            # Process GitLab groups
            for group_url in targets.gitlab_groups:
                try:
                    scraper = GitlabScraper(cache_lifetime=self.cache_lifetime)
                    host, group_path = self._extract_host_and_path(group_url)
                    org_id = f"{host}/{group_path.split('/')[0]}"
                    active_org_ids.add(org_id)

                    # Fetch group metadata
                    from oss4climate.src.parsers.git_platforms.gitlab_io import _web_get

                    group_data = _web_get(
                        f"https://{host}/api/v4/groups/{group_path}",
                        is_json=True,
                        cache_lifetime=self.cache_lifetime,
                    )
                    group_data["id"] = org_id
                    upsert_organisation(session, group_data)

                    # Discover repos
                    repos = scraper.fetch_repositories_in_group(group_url)
                    for repo_name, repo_url in repos.items():
                        repo_id = self._get_repo_id(repo_url)
                        active_repo_ids.add(repo_id)
                        upsert_repository(
                            session,
                            {
                                "id": repo_id,
                                "organisation_id": org_id,
                                "name": repo_name,
                                "url": repo_url,
                            },
                        )
                except Exception as e:
                    session.rollback()
                    log_warning(f"Failed to sync GitLab group {group_url}: {e}")
                    host, group_path = self._extract_host_and_path(group_url)
                    org_id = f"{host}/{group_path.split('/')[0]}"
                    active_org_ids.add(org_id)
                    upsert_organisation(
                        session,
                        {
                            "id": org_id,
                            "last_error": str(e),
                            "error_count": 1,
                        },
                    )

            # Process GitLab explicit projects
            for project_url in targets.gitlab_projects:
                repo_id = self._get_repo_id(project_url)
                active_repo_ids.add(repo_id)
                upsert_repository(
                    session,
                    {
                        "id": repo_id,
                        "url": project_url,
                    },
                )

            # Process Codeberg organisations
            for org_url in targets.codeberg_organisations:
                try:
                    org_id = self._get_org_id(org_url)
                    active_org_ids.add(org_id)
                    # Codeberg scraper doesn't support org details yet, just record the org
                    upsert_organisation(
                        session,
                        {
                            "id": org_id,
                        },
                    )
                except Exception as e:
                    session.rollback()
                    log_warning(f"Failed to sync Codeberg org {org_url}: {e}")

            # Process Codeberg explicit repos
            for repo_url in targets.codeberg_repositories:
                repo_id = self._get_repo_id(repo_url)
                active_repo_ids.add(repo_id)
                upsert_repository(
                    session,
                    {
                        "id": repo_id,
                        "url": repo_url,
                    },
                )

            # Process Bitbucket projects
            for project_url in targets.bitbucket_projects:
                try:
                    scraper = BitbucketScraper(cache_lifetime=self.cache_lifetime)
                    org_id = self._get_org_id(project_url)
                    active_org_ids.add(org_id)

                    # Fetch project/org metadata
                    from oss4climate.src.parsers.git_platforms.bitbucket_io import (
                        _web_get,
                    )

                    project_data = _web_get(
                        f"https://api.bitbucket.org/2.0/workspaces/{project_url.split('/')[-1]}",
                        is_json=True,
                        cache_lifetime=self.cache_lifetime,
                    )
                    project_data["id"] = org_id
                    upsert_organisation(session, project_data)

                    # Discover repos
                    repos = scraper.fetch_repositories_in_group(project_url)
                    for repo_name, repo_url in repos.items():
                        repo_id = self._get_repo_id(repo_url)
                        active_repo_ids.add(repo_id)
                        upsert_repository(
                            session,
                            {
                                "id": repo_id,
                                "organisation_id": org_id,
                                "name": repo_name,
                                "url": repo_url,
                            },
                        )
                except Exception as e:
                    log_warning(f"Failed to sync Bitbucket project {project_url}: {e}")
                    org_id = self._get_org_id(project_url)
                    active_org_ids.add(org_id)
                    upsert_organisation(
                        session,
                        {
                            "id": org_id,
                            "last_error": str(e),
                            "error_count": 1,
                        },
                    )

            # Process Bitbucket explicit repos
            for repo_url in targets.bitbucket_repositories:
                repo_id = self._get_repo_id(repo_url)
                active_repo_ids.add(repo_id)
                upsert_repository(
                    session,
                    {
                        "id": repo_id,
                        "url": repo_url,
                    },
                )

            # Mark repos as inactive if they're not in the active set
            mark_repos_inactive(session, active_repo_ids)

            session.commit()

        log_info(
            f"Sync complete: {len(active_org_ids)} orgs, {len(active_repo_ids)} repos in scope"
        )

    def scrape_active_repos(self) -> dict[str, str]:
        """
        Scrape all active repositories that are past their refresh threshold.

        :return: Dictionary of errors keyed by repo ID
        """
        log_info(f"Scraping active repos (refresh threshold: {self.refresh_days} days)")

        with Session(get_engine()) as session:
            repos_to_scrape = get_active_repos_to_scrape(session, self.refresh_days)

        if not repos_to_scrape:
            log_info("No repos need scraping")
            return {}

        log_info(f"{len(repos_to_scrape)} repos need scraping")

        # Build a ParsingTargets from the repos to scrape
        targets = ParsingTargets()
        repo_map: dict[str, Repository] = {}

        for repo in repos_to_scrape:
            repo_map[repo.id] = repo
            # Parse the repo ID to determine platform and add to targets
            repo_id = repo.id
            if repo_id.startswith("github.com/"):
                targets.github_repositories.add(repo_id.replace("github.com/", ""))
            elif repo_id.startswith("gitlab.com/") or repo_id.startswith("git."):
                # For GitLab, we need the full path
                if repo.url:
                    targets.gitlab_projects.add(repo.url)
            elif repo_id.startswith("codeberg.org/"):
                targets.codeberg_repositories.add(repo_id.replace("codeberg.org/", ""))
            elif repo_id.startswith("bitbucket.org/"):
                targets.bitbucket_repositories.add(
                    repo_id.replace("bitbucket.org/", "")
                )

        # Use the existing scrape_all_targets for the actual scraping
        # This reuses all the caching, rate limiting, and platform dispatch logic
        scrape_result = scrape_all_targets(
            targets=targets,
            fail_on_issue=False,
            cache_lifetime=self.cache_lifetime,
        )

        # Sync results back to the DB
        errors: dict[str, str] = {}
        with Session(get_engine()) as session:
            for repo_id, repo in repo_map.items():
                # Check if this repo was in the scrape results
                if repo_id in scrape_result.errors:
                    error_msg = str(scrape_result.errors[repo_id])
                    set_repo_error(session, repo_id, error_msg)
                    errors[repo_id] = error_msg
                    continue

                # Find the corresponding ProjectDetails in the results
                project_details = None
                for detail in scrape_result.results_as_df.itertuples():
                    if hasattr(detail, "id") and detail.id == repo_id:
                        project_details = detail
                        break

                if project_details is None:
                    # Repo was skipped (e.g., .github repo)
                    continue

                # Convert ProjectDetails to dict for upsert
                repo_data = self._project_details_to_dict(project_details)
                repo_data["id"] = repo_id
                repo_data["last_scraped_at"] = self._now()
                repo_data["active"] = True

                # Reset error tracking on success
                reset_repo_error(session, repo_id)

                upsert_repository(session, repo_data)

            session.commit()

        log_info(
            f"Scraping complete: {len(repos_to_scrape) - len(errors)} succeeded, {len(errors)} failed"
        )
        return errors

    def _project_details_to_dict(self, details: ProjectDetails | Any) -> dict[str, Any]:
        """
        Convert a ProjectDetails object to a dictionary suitable for DB upsert.

        :param details: ProjectDetails object or DataFrame row
        :return: Dictionary of fields
        """
        if isinstance(details, ProjectDetails):
            d = details.model_dump()
        else:
            # DataFrame row (pandas Series)
            d = {
                "id": getattr(details, "id", None),
                "name": getattr(details, "name", None),
                "organisation": getattr(details, "organisation", None),
                "url": getattr(details, "url", None),
                "website": getattr(details, "website", None),
                "description": getattr(details, "description", None),
                "license": getattr(details, "license", None),
                "license_url": getattr(details, "license_url", None),
                "latest_update": getattr(details, "latest_update", None),
                "last_commit": getattr(details, "last_commit", None),
                "language": getattr(details, "language", None),
                "all_languages": getattr(details, "all_languages", None),
                "open_pull_requests": getattr(details, "open_pull_requests", None),
                "master_branch": getattr(details, "master_branch", None),
                "readme": getattr(details, "readme", None),
                "readme_type": getattr(details, "readme_type", None),
                "is_fork": getattr(details, "is_fork", None),
                "forked_from": getattr(details, "forked_from", None),
            }

        # Convert all_languages to JSON string if it's a list
        all_langs = d.get("all_languages")
        if isinstance(all_langs, list):
            d["all_languages"] = json.dumps(all_langs)
        elif all_langs is not None:
            d["all_languages"] = str(all_langs)

        # Convert readme_type enum to string value
        readme_type = d.get("readme_type")
        if isinstance(readme_type, EnumDocumentationFileType):
            d["readme_type"] = readme_type.value

        # Remove raw_details
        d.pop("raw_details", None)

        return d

    def _now(self) -> str:
        """
        Get current UTC datetime as ISO string.

        :return: Current UTC datetime as ISO string
        """
        return datetime.now(tz=UTC).isoformat()

    def export_to_feather(
        self,
        output_path: str,
    ) -> None:
        """
        Export active repositories to a feather file.

        :param output_path: Path to the output feather file
        """
        import pandas as pd

        with Session(get_engine()) as session:
            repos = get_all_active_repos(session)

        if not repos:
            log_info("No active repos to export")
            return

        records = []
        for repo in repos:
            record = {
                "id": repo.id,
                "name": repo.name,
                "organisation": None,  # Would need to join with organisations table
                "url": repo.url,
                "website": repo.website,
                "description": repo.description,
                "license": repo.license,
                "license_url": repo.license_url,
                "latest_update": repo.latest_update,
                "last_commit": repo.last_commit,
                "language": repo.language,
                "all_languages": json.loads(repo.all_languages)
                if repo.all_languages
                else [],
                "open_pull_requests": repo.open_pull_requests,
                "master_branch": repo.master_branch,
                "readme": repo.readme,
                "readme_type": repo.readme_type,
                "is_fork": repo.is_fork,
                "forked_from": repo.forked_from,
            }
            records.append(record)

        df = pd.DataFrame(records).set_index("id")

        # Determine output format
        if output_path.endswith(".csv"):
            df.drop(columns=["readme"]).to_csv(output_path, sep=";")
        elif output_path.endswith(".json"):
            df.T.to_json(output_path)
        elif output_path.endswith(".feather"):
            df.reset_index().to_feather(output_path)
        else:
            raise ValueError(f"Unsupported file type for export: {output_path}")

        log_info(f"Exported {len(records)} repos to {output_path}")

    def export_summary_toml(
        self,
        output_path: str,
    ) -> None:
        """
        Export summary statistics to a TOML file.

        :param output_path: Path to the output TOML file
        """
        from tomlkit import document, dump

        with Session(get_engine()) as session:
            repos = get_all_active_repos(session)

        if not repos:
            log_info("No active repos for summary")
            return

        # Convert to dict for easier processing
        repo_dicts = [
            {
                "language": repo.language,
                "organisation": None,  # Would need join
                "license": repo.license,
            }
            for repo in repos
        ]

        languages = sorted_list_of_unique_elements(
            [r["language"] for r in repo_dicts if r["language"]]
        )
        licences = sorted_list_of_unique_elements(
            [r["license"] for r in repo_dicts if r["license"]]
        )

        stats = {
            "repositories": len(repos),
            "organisations": len(repos),  # Simplified - would need distinct count
        }

        doc = document()
        doc.add("statistics", stats)
        doc.add("organisations", [])
        doc.add("language", [str(i) for i in languages])
        doc.add("licences", [str(i) for i in licences])

        with open(output_path, "w") as fp:
            dump(doc, fp, sort_keys=True)

        log_info(f"Exported summary to {output_path}")

    def export_failures_toml(
        self,
        output_path: str,
    ) -> None:
        """
        Export failure information to a TOML file.

        :param output_path: Path to the output TOML file
        """
        from tomlkit import document, dump

        with Session(get_engine()) as session:
            repos = session.exec(
                select(Repository).where(
                    Repository.active == True,  # noqa: E712
                    Repository.last_error != None,  # noqa: E711
                )
            ).all()

        failures = {}
        for repo in repos:
            if repo.last_error:
                failures[repo.id] = repo.last_error

        doc = document()
        doc.add("failures", failures)

        with open(output_path, "w") as fp:
            dump(doc, fp, sort_keys=True)

        log_info(f"Exported {len(failures)} failures to {output_path}")

    def run(
        self,
        toml_path: str,
        feather_output: str | None = None,
        summary_output: str | None = None,
        failures_output: str | None = None,
    ) -> None:
        """
        Run the full scraping pipeline.

        :param toml_path: Path to the TOML index file
        :param feather_output: Path to output feather file (optional)
        :param summary_output: Path to output summary TOML (optional)
        :param failures_output: Path to output failures TOML (optional)
        """
        log_info("Starting repository scraping pipeline")

        # Step 1: Sync from TOML
        self.sync_from_toml(toml_path)

        # Step 2: Scrape active repos
        errors = self.scrape_active_repos()

        if errors:
            log_warning(f"Scraping had {len(errors)} failures")

        # Step 3: Export results
        if feather_output:
            self.export_to_feather(feather_output)

        if summary_output:
            self.export_summary_toml(summary_output)

        if failures_output:
            self.export_failures_toml(failures_output)

        log_info("Repository scraping pipeline complete")

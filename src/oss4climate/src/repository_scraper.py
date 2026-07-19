"""
Repository scraper that manages scraping data to a SQLModel-backed database.

This module provides the RepositoryScraper class which orchestrates the full
scraping lifecycle:
1. Sync from TOML — reconcile TOML with DB (upsert orgs, discover repos, prune inactive)
2. Scrape active repos — fetch fresh data for repos past their refresh threshold
3. Export — write results to feather file, summary TOML, and failures TOML
"""

import json
from datetime import timedelta
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from oss4climate.src.database import open_database_session
from oss4climate.src.database.repos import (
    Repository,
    get_active_repos_to_scrape,
    get_all_active_repos,
    mark_repos_inactive,
    reset_repo_error,
    set_repo_error,
    upsert_organisation,
    upsert_repository,
)
from oss4climate.src.helpers import now, sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.models import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.parsers import ParsingTargets, RateLimitError
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
        host = url.split("://")[1].split("/")[0]
        if platform == "unknown":
            # Try to extract host from URL
            if "://" in url:
                return (
                    f"{host}/{url.split('/', 3)[-1] if len(url.split('/')) > 3 else ''}"
                )
            return url
        return f"{host}/{path}" if platform != "gitlab" else path

    def _get_org_id(self, url: str) -> str:
        """
        Get the organisation ID in the format "host/org_path".

        :param url: URL or path
        :return: Organisation ID (e.g., "github.com/oss4climate")
        """
        platform, path = self._get_platform_from_url(url)
        host = url.split("://")[1].split("/")[0]
        if platform == "unknown":
            if "://" in url:
                org_path = (
                    url.split("/", 3)[-1].split("/")[0]
                    if len(url.split("/")) > 3
                    else ""
                )
                return f"{host}/{org_path}"
            return url
        return (
            f"{host}/{path.split('/')[0]}"
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

        with open_database_session() as session:
            # First sync Github and commit
            self._sync_github_organisations(
                session, targets, active_org_ids, active_repo_ids
            )
            self._upsert_explicit_repos(
                session, targets.github_repositories, active_repo_ids
            )
            session.commit()
            # Then Gitlab
            self._sync_gitlab_groups(session, targets, active_org_ids, active_repo_ids)
            self._upsert_explicit_repos(
                session, targets.gitlab_projects, active_repo_ids
            )
            session.commit()
            # Then codeberg
            self._sync_codeberg_organisations(
                session, targets, active_org_ids, active_repo_ids
            )
            self._upsert_explicit_repos(
                session, targets.codeberg_repositories, active_repo_ids
            )
            session.commit()
            # Then Bitbucket
            self._sync_bitbucket_projects(
                session, targets, active_org_ids, active_repo_ids
            )
            self._upsert_explicit_repos(
                session, targets.bitbucket_repositories, active_repo_ids
            )
            session.commit()

            # Mark repos as inactive if they're not in the active set
            mark_repos_inactive(session, active_repo_ids)
            session.commit()

        log_info(
            f"Sync complete: {len(active_org_ids)} orgs, {len(active_repo_ids)} repos in scope"
        )

    def _upsert_explicit_repos(
        self, session: Session, urls: set[str], active_repo_ids: set[str]
    ) -> None:
        """Upsert a list of explicit repository URLs into the DB.

        :param session: Database session (must be open)
        :param urls: Set of repo URL strings to upsert
        :param active_repo_ids: Mutable set tracking all active repo IDs (updated in-place)
        """
        for url in urls:
            repo_id = self._get_repo_id(url)
            active_repo_ids.add(repo_id)
            upsert_repository(session, {"id": repo_id, "url": url})

    def _sync_github_organisations(
        self,
        session: Session,
        targets: ParsingTargets,
        active_org_ids: set[str],
        active_repo_ids: set[str],
    ) -> None:
        """Sync GitHub organisations and their discovered repos.

        :param session: Database session (must be open)
        :param targets: Parsed TOML targets containing github_organisations list
        :param active_org_ids: Mutable set tracking all active org IDs (updated in-place)
        :param active_repo_ids: Mutable set tracking all active repo IDs (updated in-place)
        """
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
                upsert_organisation(session, org_data, update_scraped_at=True)

                # Discover repos
                for repo_name, repo_url in scraper.fetch_repositories_in_organisation(
                    org_url
                ).items():
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

                # Commit after each successful org (for interruption tolerance).
                session.commit()
            except Exception as e:
                session.rollback()
                log_warning(f"Failed to sync GitHub org {org_url}: {e}")
                # Still upsert the org with error info
                active_org_ids.add(self._get_org_id(org_url))
                upsert_organisation(
                    session,
                    {
                        "id": self._get_org_id(org_url),
                        "last_error": str(e),
                        "error_count": 1,
                    },
                    update_scraped_at=True,
                )

            # Commit the error record so it's persisted even on interruption.
            session.commit()

    def _sync_gitlab_groups(
        self,
        session: Session,
        targets: ParsingTargets,
        active_org_ids: set[str],
        active_repo_ids: set[str],
    ) -> None:
        """Sync GitLab groups and their discovered repos.

        :param session: Database session (must be open)
        :param targets: Parsed TOML targets containing gitlab_groups list
        :param active_org_ids: Mutable set tracking all active org IDs (updated in-place)
        :param active_repo_ids: Mutable set tracking all active repo IDs (updated in-place)
        """
        from oss4climate.src.parsers.git_platforms import gitlab_io

        for group_url in targets.gitlab_groups:
            try:
                scraper = GitlabScraper(cache_lifetime=self.cache_lifetime)
                host, group_path = self._extract_host_and_path(group_url)
                org_id = f"{host}/{group_path.split('/')[0]}"
                active_org_ids.add(org_id)

                # Fetch group metadata via API
                group_data = gitlab_io.web_get(
                    f"https://{host}/api/v4/groups/{group_path}",
                    is_json=True,
                    cache_lifetime=self.cache_lifetime,
                )
                group_data["id"] = org_id
                upsert_organisation(session, group_data, update_scraped_at=True)

                # Discover repos
                for repo_name, repo_url in scraper.fetch_repositories_in_group(
                    group_url
                ).items():
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

                # Commit after each successful group (for interruption tolerance).
                session.commit()
            except Exception as e:
                session.rollback()
                log_warning(f"Failed to sync GitLab group {group_url}: {e}")
                host, group_path = self._extract_host_and_path(group_url)
                org_id = f"{host}/{group_path.split('/')[0]}"
                active_org_ids.add(org_id)
                upsert_organisation(
                    session,
                    {"id": org_id, "last_error": str(e), "error_count": 1},
                    update_scraped_at=True,
                )

            # Commit the error record so it's persisted even on interruption.
            session.commit()

    def _sync_codeberg_organisations(
        self,
        session: Session,
        targets: ParsingTargets,
        active_org_ids: set[str],
        active_repo_ids: set[str],
    ) -> None:
        """Sync Codeberg organisations (org records only; no detailed scraping yet).

        :param session: Database session (must be open)
        :param targets: Parsed TOML targets containing codeberg_organisations list
        :param active_org_ids: Mutable set tracking all active org IDs (updated in-place)
        :param active_repo_ids: Mutable set tracking all active repo IDs (not modified here)
        """
        for org_url in targets.codeberg_organisations:
            try:
                org_id = self._get_org_id(org_url)
                active_org_ids.add(org_id)
                upsert_organisation(session, {"id": org_id}, update_scraped_at=True)

                # Commit after each successful org (for interruption tolerance).
                session.commit()
            except Exception as e:
                session.rollback()
                log_warning(f"Failed to sync Codeberg org {org_url}: {e}")

    def _sync_bitbucket_projects(
        self,
        session: Session,
        targets: ParsingTargets,
        active_org_ids: set[str],
        active_repo_ids: set[str],
    ) -> None:
        """Sync Bitbucket projects and their discovered repos.

        :param session: Database session (must be open)
        :param targets: Parsed TOML targets containing bitbucket_projects list
        :param active_org_ids: Mutable set tracking all active org IDs (updated in-place)
        :param active_repo_ids: Mutable set tracking all active repo IDs (updated in-place)
        """
        from oss4climate.src.parsers.git_platforms import bitbucket_io

        for project_url in targets.bitbucket_projects:
            try:
                scraper = BitbucketScraper(cache_lifetime=self.cache_lifetime)
                org_id = self._get_org_id(project_url)
                active_org_ids.add(org_id)

                # Fetch project/org metadata via API
                project_data = bitbucket_io.web_get(
                    f"https://api.bitbucket.org/2.0/workspaces/{project_url.split('/')[-1]}",
                    is_json=True,
                    cache_lifetime=self.cache_lifetime,
                )
                project_data["id"] = org_id
                upsert_organisation(session, project_data, update_scraped_at=True)

                # Discover repos
                for repo_name, repo_url in scraper.fetch_repositories_in_group(
                    project_url
                ).items():
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

                # Commit after each successful project (for interruption tolerance).
                session.commit()
            except Exception as e:
                session.rollback()
                log_warning(f"Failed to sync Bitbucket project {project_url}: {e}")
                active_org_ids.add(self._get_org_id(project_url))
                upsert_organisation(
                    session,
                    {
                        "id": self._get_org_id(project_url),
                        "last_error": str(e),
                        "error_count": 1,
                    },
                    update_scraped_at=True,
                )

            # Commit the error record so it's persisted even on interruption.
            session.commit()

    def scrape_active_repos(self) -> dict[str, str]:
        """
        Scrape all active repositories that are past their refresh threshold.

        Processes repos one at a time per platform with immediate DB commits for
        interruption tolerance. Rate limit errors on one provider do not block
        other providers from continuing.

        :return: Dictionary of errors keyed by repo ID
        """
        log_info(f"Scraping active repos (refresh threshold: {self.refresh_days} days)")

        with open_database_session() as session:
            repos_to_scrape = get_active_repos_to_scrape(session, self.refresh_days)

        if not repos_to_scrape:
            log_info("No repos need scraping")
            return {}

        log_info(f"{len(repos_to_scrape)} repos need scraping")

        # Group repo IDs by platform for per-provider streaming.
        github_ids: list[str] = []
        gitlab_entries: list[tuple[str, str]] = []  # (url, repo_id) pairs
        codeberg_ids: list[str] = []
        bitbucket_ids: list[str] = []

        for repo in repos_to_scrape:
            if repo.id.startswith("github.com/"):
                github_ids.append(repo.id)
            elif repo.id.startswith("gitlab.com/") or repo.id.startswith("git."):
                url_str = str(repo.url)  # type: ignore[arg-type]
                gitlab_entries.append((url_str, repo.id))
            elif repo.id.startswith("codeberg.org/"):
                codeberg_ids.append(repo.id)
            elif repo.id.startswith("bitbucket.org/"):
                bitbucket_ids.append(repo.id)

        log_info(
            f"{len(repos_to_scrape)} repos need scraping "
            f"(GitHub: {len(github_ids)}, GitLab: {len(gitlab_entries)}, "
            f"Codeberg: {len(codeberg_ids)}, Bitbucket: {len(bitbucket_ids)})"
        )

        errors: dict[str, str] = {}

        # GitHub — per-repo streaming with rate limit break-out.
        for repo_id in github_ids:
            try:
                scraper = GithubScraper(cache_lifetime=self.cache_lifetime)
                project_details = scraper.fetch_project_details(
                    repo_id, fail_on_issue=False
                )
            except RateLimitError as e:
                log_warning("GitHub rate limit hit — skipping remaining GitHub repos")
                for rid in github_ids[github_ids.index(repo_id) :]:  # type: ignore[arg-type]
                    errors[rid] = f"github.com/RateLimitError: {e}"
                break
            except Exception as e:
                with open_database_session() as session:
                    set_repo_error(session, repo_id, str(e))
                    session.commit()
                errors[repo_id] = str(e)
                continue

            try:
                repo_data = self._project_details_to_dict(project_details)
                repo_data["id"] = repo_id
                repo_data["last_scraped_at"] = self._now()
                repo_data["active"] = True
                with open_database_session() as session:
                    reset_repo_error(session, repo_id)
                    upsert_repository(session, repo_data)
                    log_info(f" > Committed repository to the database ({repo_id})")
                    session.commit()
            except Exception as e:
                log_warning(
                    f" > Failed to commit repository to the database ({repo_id}) : {e}"
                )
                errors[repo_id] = str(e)

        # GitLab — per-repo streaming. Rate limit on other providers does not affect this bucket.
        for url, repo_id in gitlab_entries:
            try:
                scraper = GitlabScraper(cache_lifetime=self.cache_lifetime)
                project_details = scraper.fetch_project_details(
                    url, fail_on_issue=False
                )
            except Exception as e:
                with open_database_session() as session:
                    set_repo_error(session, repo_id, str(e))
                    session.commit()
                errors[repo_id] = str(e)
                continue

            try:
                repo_data = self._project_details_to_dict(project_details)
                repo_data["id"] = repo_id
                with open_database_session() as session:
                    reset_repo_error(session, repo_id)
                    upsert_repository(session, repo_data)
                    session.commit()
            except Exception as e:
                errors[repo_id] = str(e)

        for codeberg_id in codeberg_ids:
            try:
                scraper = CodebergScraper(cache_lifetime=self.cache_lifetime)
                project_details = scraper.fetch_project_details(
                    codeberg_id, fail_on_issue=False
                )
            except Exception as e:
                with open_database_session() as session:
                    set_repo_error(session, codeberg_id, str(e))
                    session.commit()
                errors[codeberg_id] = str(e)
                continue

            try:
                repo_data = self._project_details_to_dict(project_details)
                repo_data["id"] = codeberg_id
                repo_data["last_scraped_at"] = self._now()
                repo_data["active"] = True
                with open_database_session() as session:
                    reset_repo_error(session, codeberg_id)
                    upsert_repository(session, repo_data)
                    session.commit()
            except Exception as e:
                errors[codeberg_id] = str(e)

        for bitbucket_id in bitbucket_ids:
            try:
                scraper = BitbucketScraper(cache_lifetime=self.cache_lifetime)
                project_details = scraper.fetch_project_details(
                    bitbucket_id, fail_on_issue=False
                )
            except Exception as e:
                with open_database_session() as session:
                    set_repo_error(session, bitbucket_id, str(e))
                    session.commit()
                errors[bitbucket_id] = str(e)
                continue

            try:
                repo_data = self._project_details_to_dict(project_details)
                repo_data["id"] = bitbucket_id
                repo_data["last_scraped_at"] = self._now()
                repo_data["active"] = True
                with open_database_session() as session:
                    reset_repo_error(session, bitbucket_id)
                    upsert_repository(session, repo_data)
                    session.commit()
            except Exception as e:
                errors[bitbucket_id] = str(e)

        log_info(
            f"Scraping complete: {len(repos_to_scrape) - len(errors)} succeeded, "
            f"{len(errors)} failed"
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
                "organisation_id": getattr(details, "organisation_id", None),
                "url": getattr(details, "url", None),
                "website": getattr(details, "website", None),
                "description": getattr(details, "description", None),
                "licence": getattr(details, "licence", None),
                "licence_url": getattr(details, "licence_url", None),
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
        return now().isoformat()

    def export_to_feather(
        self,
        output_path: str,
    ) -> None:
        """
        Export active repositories to a feather file.

        :param output_path: Path to the output feather file
        """

        with open_database_session() as session:
            repos = get_all_active_repos(session)

        if not repos:
            log_info("No active repos to export")
            return

        records = []
        for repo in repos:
            record = {
                "id": repo.id,
                "name": repo.name,
                "organisation_id": repo.organisation_id,
                "url": repo.url,
                "website": repo.website,
                "description": repo.description,
                "licence": repo.licence,
                "licence_url": repo.licence_url,
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

        with open_database_session() as session:
            repos = get_all_active_repos(session)

        if not repos:
            log_info("No active repos for summary")
            return

        # Convert to dict for easier processing
        repo_dicts = [
            {
                "language": repo.language,
                "organisation_id": None,  # Would need join
                "licence": repo.licence,
            }
            for repo in repos
        ]

        languages = sorted_list_of_unique_elements(
            [r["language"] for r in repo_dicts if r["language"]]
        )
        licences = sorted_list_of_unique_elements(
            [r["licence"] for r in repo_dicts if r["licence"]]
        )

        stats = {
            "repositories": len({i.id for i in repos}),
            "organisations": len({i.organisation_id for i in repos}),
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

        with open_database_session() as session:
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

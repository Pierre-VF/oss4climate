"""
This module takes care of scraping data from Github-hosted code

This implements:
- Fetching repositories in an organisation
- Fetching data in a repository (details in the ProjectDetails(...) return)
- Github URL identification and management (cleanup, type classification, ...)
"""

from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache

import requests

from oss4climate.src.config import SETTINGS
from oss4climate.src.helpers import get_key_of_maximum_value, url_base_matches_domain
from oss4climate.src.log import log_info
from oss4climate.src.models import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.parsers import (
    ParsingTargets,
    cached_web_get_json,
    cached_web_get_text,
)

_GITHUB_DOMAIN = "github.com"
_GITHUB_URL_BASE = f"https://{_GITHUB_DOMAIN}/"


def _extract_organisation_and_repository_as_url_block(x: str) -> str:
    # Cleaning up Github prefix
    if GithubScraper.is_relevant_url(x):
        x = x.replace(_GITHUB_URL_BASE, "")
    fixed_x = "/".join(x.split("/")[:2])
    # Removing eventual extra information in URL
    for i in ["#", "&"]:
        if i in fixed_x:
            fixed_x = fixed_x.split(i)[0]
    # Removing trailing "/", if any
    while fixed_x.endswith("/"):
        fixed_x = fixed_x[:-1]
    return fixed_x


class _GithubTargetType(Enum):
    ORGANISATION = "ORGANISATION"
    REPOSITORY = "REPOSITORY"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def identify(url: str) -> "_GithubTargetType":
        if not GithubScraper.is_relevant_url(url):
            return _GithubTargetType.UNKNOWN
        processed = _extract_organisation_and_repository_as_url_block(url)
        n_slashes = processed.count("/")
        if n_slashes < 1:
            return _GithubTargetType.ORGANISATION
        elif n_slashes == 1:
            return _GithubTargetType.REPOSITORY
        else:
            return _GithubTargetType.UNKNOWN


@lru_cache(maxsize=1)
def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if SETTINGS.GITHUB_API_TOKEN is None:
        log_info("Github running in PUBLIC mode")
    else:
        log_info("Github running in AUTHENTICATED mode")
        headers["Authorization"] = f"Bearer {SETTINGS.GITHUB_API_TOKEN}"
    return headers


def _web_get(
    url: str,
    with_headers: bool = True,
    is_json: bool = True,
    raise_rate_limit_error_on_403: bool = True,
    cache_lifetime: timedelta | None = None,
) -> dict:
    if with_headers:
        headers = _github_headers()
    else:
        headers = None

    # Based upon 5000 requests per hour
    #   (also taking into account the extra side computations that spend time on other things than calls)
    rate_limiting_wait_s = 0.5

    if is_json:
        res = cached_web_get_json(
            url=url,
            headers=headers,
            raise_rate_limit_error_on_403=raise_rate_limit_error_on_403,
            rate_limiting_wait_s=rate_limiting_wait_s,
            cache_lifetime=cache_lifetime,
        )
    else:
        res = cached_web_get_text(
            url=url,
            headers=headers,
            raise_rate_limit_error_on_403=raise_rate_limit_error_on_403,
            rate_limiting_wait_s=rate_limiting_wait_s,
            cache_lifetime=cache_lifetime,
        )
    return res


def _master_branch_name(
    cleaned_repo_path: str,
    cache_lifetime: timedelta | None = None,
) -> str | None:
    # Gather extra metadata
    more_data_needed = True
    branches_names = []
    page = 1
    while more_data_needed:
        r_branches = _web_get(
            f"https://api.github.com/repos/{cleaned_repo_path}/branches?per_page=100&page={page}",
            cache_lifetime=cache_lifetime,
        )
        branches_i = [i["name"] for i in r_branches]
        page += 1
        more_data_needed = len(branches_i) == 100
        branches_names += branches_i

    if len(branches_names) == 1:
        # If only one branch, then the choice is clear
        branch2use = branches_names[0]
    elif "main" in branches_names:
        # Else, first looking for a "main" branch
        branch2use = "main"
    elif "master" in branches_names:
        # Then looking for a "master" branch
        branch2use = "master"
    else:
        log_info(f"Unable to select branch among: {branches_names}")
        branch2use = None
    return branch2use


def extract_repository_organisation(repo_path: str) -> str:
    repo_path = _extract_organisation_and_repository_as_url_block(repo_path)
    organisation = repo_path.split("/")[0]
    return organisation


# -----
from oss4climate.src.parsers.git_platforms.common import GitPlatformScraper


class GithubScraper(GitPlatformScraper):
    def __init__(
        self,
        cache_lifetime: timedelta | None = None,
    ):
        super().__init__(cache_lifetime=cache_lifetime)

    @classmethod
    def is_relevant_url(
        cls,
        url: str,
    ) -> bool:
        return url_base_matches_domain(url, _GITHUB_DOMAIN)

    @classmethod
    def split_across_target_sets(
        cls,
        x: list[str],
    ) -> ParsingTargets:
        orgs = []
        repos = []
        others = []
        for i in x:
            tt_i = _GithubTargetType.identify(i)
            if tt_i is _GithubTargetType.ORGANISATION:
                orgs.append(i)
            elif tt_i is _GithubTargetType.REPOSITORY:
                repos.append(i)
            else:
                others.append(i)
        return ParsingTargets(
            github_organisations=orgs, github_repositories=repos, unknown=others
        )

    def fetch_repository_readme(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
    ) -> tuple[str | None, EnumDocumentationFileType]:
        cache_lifetime = self.cache_lifetime
        repo_name = _extract_organisation_and_repository_as_url_block(repo_id)

        if branch is None:
            branch = _master_branch_name(repo_name, cache_lifetime=cache_lifetime)

        md_content = None
        readme_type = EnumDocumentationFileType.UNKNOWN

        file_tree = self.fetch_repository_file_tree(
            repo_name,
            fail_on_issue=fail_on_issue,
        )
        for i in file_tree:
            lower_i = i.lower()
            if lower_i.startswith("readme.") or lower_i.startswith("docs/readme."):
                try:
                    if branch == "main":
                        # Keeping what worked well so far
                        readme_url = (
                            f"https://raw.githubusercontent.com/{repo_name}/main/{i}"
                        )
                    else:
                        readme_url = f"https://raw.githubusercontent.com/{repo_name}/refs/heads/{branch}/{i}"
                    md_content = _web_get(
                        readme_url,
                        with_headers=None,
                        is_json=False,
                        cache_lifetime=cache_lifetime,
                    )
                    readme_type = EnumDocumentationFileType.from_filename(lower_i)
                except Exception as e:
                    md_content = f"ERROR with {i} ({e})"

                # Only using the first file matching
                break

        if md_content is None:
            if fail_on_issue:
                raise ValueError(
                    f"Unable to identify a README on the repository: {_GITHUB_URL_BASE}{repo_name}"
                )
            else:
                md_content = "(NO README)"

        return md_content, readme_type

    def fetch_project_details(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
    ) -> ProjectDetails:
        cache_lifetime = self.cache_lifetime
        repo_path = _extract_organisation_and_repository_as_url_block(repo_id)

        r = _web_get(
            f"https://api.github.com/repos/{repo_path}",
            cache_lifetime=cache_lifetime,
        )
        if branch:
            branch2use = branch
        else:
            branch2use = _master_branch_name(repo_path)

        if branch2use is None:
            if fail_on_issue:
                raise ValueError(
                    f"Unable to identify the right branch on {_GITHUB_URL_BASE}{repo_path}"
                )
            last_commit = None
        else:
            # If ever getting issues with the size here, "?per_page=10" can be added to the URL
            #  (just need to ensure that all latest commits are included)
            r_last_commit_to_master = _web_get(
                f"https://api.github.com/repos/{repo_path}/commits/{branch2use}",
                cache_lifetime=cache_lifetime,
            )
            last_commit = datetime.fromisoformat(
                r_last_commit_to_master["commit"]["author"]["date"]
            ).date()

        # Stats (for later)
        stars = r.get("stargazers_count")
        watchers = r.get("watchers_count")
        subscribers = r.get("subscribers_count")
        open_issues = r.get("open_issues_count")
        n_forks = r.get("forks")
        is_fork = r.get("fork")
        if is_fork:
            forked_from = r.get("parent").get("html_url")
        else:
            forked_from = None

        # Note: this does not work well as the limit is set to 30
        r_pull_requests = _web_get(
            f"https://api.github.com/repos/{repo_path}/pulls",
            cache_lifetime=cache_lifetime,
        )
        n_open_pull_requests = len([i for i in r_pull_requests if i["state"] == "open"])
        # TODO: fix this better
        if n_open_pull_requests == 30:
            n_open_pull_requests = None

        license = r["license"]
        if license is not None:
            license = license.get("name")

        license_url = self.fetch_license_url(
            repo_path,
            branch=branch2use,
            fail_on_issue=fail_on_issue,
        )

        readme, readme_type = self.fetch_repository_readme(
            repo_path,
            branch=branch2use,
            fail_on_issue=fail_on_issue,
        )

        raw_languages = self.fetch_repository_language_details(
            repo_path,
        )
        dominant_language = get_key_of_maximum_value(raw_languages)
        languages = list(raw_languages.keys())

        details = ProjectDetails(
            id=repo_path,
            name=r["name"],
            organisation=GithubScraper.extract_repository_organisation(repo_path),
            url=r["html_url"],
            website=r["homepage"],
            description=r["description"],
            license=license,
            license_url=license_url,
            language=dominant_language,
            all_languages=languages,
            latest_update=datetime.fromisoformat(r["updated_at"]).date(),
            last_commit=last_commit,
            open_pull_requests=n_open_pull_requests,
            raw_details=r,
            master_branch=branch2use,
            readme=readme,
            readme_type=readme_type,
            is_fork=is_fork,
            forked_from=forked_from,
        )
        return details

    def fetch_repository_language_details(
        self,
        repo_id: str,
    ) -> ProjectDetails:
        repo_path = _extract_organisation_and_repository_as_url_block(repo_id)
        r = _web_get(
            f"https://api.github.com/repos/{repo_path}/languages",
            cache_lifetime=self.cache_lifetime,
        )
        return r

    def fetch_repositories_in_organisation(
        self,
        organisation_name: str,
    ) -> dict[str, str]:
        cache_lifetime = self.cache_lifetime
        organisation_name = _extract_organisation_and_repository_as_url_block(
            organisation_name
        )

        get_more = True
        out = {}
        page = 1
        per_page = 100
        while get_more:
            try:
                res = _web_get(
                    f"https://api.github.com/orgs/{organisation_name}/repos?per_page={per_page}&page={page}",
                    cache_lifetime=cache_lifetime,
                )
                page += 1
            except requests.exceptions.HTTPError as e:
                if page > 1:
                    raise e
                # Where orgs do not work, one is potentially looking at a user instead (not supporting several pages on users)
                res = _web_get(
                    f"https://api.github.com/users/{organisation_name}/repos",
                    cache_lifetime=cache_lifetime,
                )

            out_i = {r["name"]: r["html_url"] for r in res}
            get_more = len(out_i) == per_page
            out = out | out_i
        return out

    def fetch_master_branch_name(
        self,
        repo_id: str,
    ) -> str | None:
        return _master_branch_name(
            cleaned_repo_path=repo_id,
            cache_lifetime=self.cache_lifetime,
        )

    def fetch_repository_file_tree(
        self,
        repo_id: str,
        fail_on_issue: bool = True,
    ) -> list[str] | str:
        repo_name = _extract_organisation_and_repository_as_url_block(repo_id)
        branch = _master_branch_name(repo_name)
        if branch is None:
            return "ERROR with file tree (unclear master branch)"
        try:
            r = _web_get(
                url=f"https://api.github.com/repos/{repo_name}/git/trees/{branch}?recursive=1",
                with_headers=True,
                is_json=True,
                cache_lifetime=self.cache_lifetime,
            )
            file_tree = [i["path"] for i in r["tree"]]
        except Exception as e:
            if fail_on_issue:
                raise e
            file_tree = f"ERROR with file tree ({e})"
        return file_tree

    # --------------------------------------------------------------------------------
    # Not part of the abstract class
    # --------------------------------------------------------------------------------
    def fetch_license_url(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
    ) -> str | None:
        cache_lifetime = self.cache_lifetime
        repo_id = _extract_organisation_and_repository_as_url_block(repo_id)

        if branch is None:
            branch = _master_branch_name(repo_id, cache_lifetime=cache_lifetime)

        license_url = None
        file_tree = self.fetch_repository_file_tree(
            repo_id,
            fail_on_issue=fail_on_issue,
        )
        for i in file_tree:
            lower_i = i.lower()
            if lower_i.startswith("license"):
                if branch == "main":
                    # Keeping what worked well so far
                    license_url = (
                        f"https://raw.githubusercontent.com/{repo_id}/main/{i}"
                    )
                else:
                    license_url = f"https://raw.githubusercontent.com/{repo_id}/refs/heads/{branch}/{i}"
        return license_url

    @classmethod
    def extract_repository_organisation(cls, repo_path: str) -> str:
        repo_path = _extract_organisation_and_repository_as_url_block(repo_path)
        organisation = repo_path.split("/")[0]
        return organisation

    @classmethod
    def minimalise_resource_url(cls, url) -> str:
        return _GITHUB_URL_BASE + _extract_organisation_and_repository_as_url_block(url)

    # --------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------

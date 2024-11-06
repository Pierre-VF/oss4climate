"""
This module takes care of scraping data from Github-hosted code

This implements:
- Fetching repositories in an organisation
- Fetching data in a repository (details in the ProjectDetails(...) return)
- Github URL identification and management (cleanup, type classification, ...)
"""

from datetime import datetime
from enum import Enum
from functools import lru_cache

import requests

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate.src.model import ProjectDetails
from oss4climate.src.parsers import (
    ParsingTargets,
    cached_web_get_json,
    cached_web_get_text,
)

GITHUB_URL_BASE = "https://github.com/"


def _extract_organisation_and_repository_as_url_block(x: str) -> str:
    # Cleaning up Github prefix
    if x.startswith(GITHUB_URL_BASE):
        x = x.replace(GITHUB_URL_BASE, "")
    # Removing eventual extra information in URL
    for i in ["#", "&"]:
        if i in x:
            x = x.split(i)[0]
    # Removing trailing "/", if any
    while x.endswith("/"):
        x = x[:-1]
    return x


def clean_github_repository_url(url: str) -> str:
    return GITHUB_URL_BASE + _extract_organisation_and_repository_as_url_block(url)


class GithubTargetType(Enum):
    ORGANISATION = "ORGANISATION"
    REPOSITORY = "REPOSITORY"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def identify(url: str) -> "GithubTargetType":
        processed = _extract_organisation_and_repository_as_url_block(url)
        n_slashes = processed.count("/")
        if n_slashes < 1:
            return GithubTargetType.ORGANISATION
        elif n_slashes == 1:
            return GithubTargetType.REPOSITORY
        else:
            return GithubTargetType.UNKNOWN


def split_across_target_sets(
    x: list[str],
) -> ParsingTargets:
    orgs = []
    repos = []
    others = []
    for i in x:
        tt_i = GithubTargetType.identify(i)
        if tt_i is GithubTargetType.ORGANISATION:
            orgs.append(i)
        elif tt_i is GithubTargetType.REPOSITORY:
            repos.append(i)
        else:
            others.append(i)
    return ParsingTargets(
        github_organisations=orgs, github_repositories=repos, unknown=others
    )


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
) -> dict:
    if with_headers:
        headers = _github_headers()
    else:
        headers = None
    if is_json:
        res = cached_web_get_json(
            url=url,
            headers=headers,
            raise_rate_limit_error_on_403=raise_rate_limit_error_on_403,
        )
    else:
        res = cached_web_get_text(
            url=url,
            headers=headers,
            raise_rate_limit_error_on_403=raise_rate_limit_error_on_403,
        )
    return res


def fetch_repositories_in_organisation(organisation_name: str) -> dict[str, str]:
    organisation_name = _extract_organisation_and_repository_as_url_block(
        organisation_name
    )

    try:
        res = _web_get(
            f"https://api.github.com/orgs/{organisation_name}/repos",
        )
    except requests.exceptions.HTTPError:
        # Where orgs do not work, one is potentially looking at a user instead
        res = _web_get(
            f"https://api.github.com/users/{organisation_name}/repos",
        )

    return {r["name"]: r["html_url"] for r in res}


def _master_branch_name(cleaned_repo_path: str) -> str | None:
    # Gather extra metadata
    r_branches = _web_get(f"https://api.github.com/repos/{cleaned_repo_path}/branches")
    branches_names = [i["name"] for i in r_branches]
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


def fetch_repository_details(
    repo_path: str,
    fail_on_issue: bool = True,
) -> ProjectDetails:
    repo_path = _extract_organisation_and_repository_as_url_block(repo_path)

    r = _web_get(f"https://api.github.com/repos/{repo_path}")
    branch2use = _master_branch_name(repo_path)

    if branch2use is None:
        if fail_on_issue:
            raise ValueError(
                f"Unable to identify the right branch on {GITHUB_URL_BASE}{repo_path}"
            )
        last_commit = None
    else:
        # If ever getting issues with the size here, "?per_page=10" can be added to the URL
        #  (just need to ensure that all latest commits are included)
        r_last_commit_to_master = _web_get(
            f"https://api.github.com/repos/{repo_path}/commits/{branch2use}"
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
    r_pull_requests = _web_get(f"https://api.github.com/repos/{repo_path}/pulls")
    n_open_pull_requests = len([i for i in r_pull_requests if i["state"] == "open"])
    # TODO: fix this better
    if n_open_pull_requests == 30:
        n_open_pull_requests = None

    license = r["license"]
    if license is not None:
        license = license["name"]

    details = ProjectDetails(
        id=repo_path,
        name=r["name"],
        organisation=extract_repository_organisation(repo_path),
        url=r["html_url"],
        website=r["homepage"],
        description=r["description"],
        license=license,
        language=r["language"],
        latest_update=datetime.fromisoformat(r["updated_at"]).date(),
        last_commit=last_commit,
        open_pull_requests=n_open_pull_requests,
        raw_details=r,
        master_branch=branch2use,
        readme=fetch_repository_readme(
            repo_path, branch=branch2use, fail_on_issue=fail_on_issue
        ),
        is_fork=is_fork,
        forked_from=forked_from,
    )
    return details


def fetch_repository_readme(
    repo_name: str,
    branch: str | None = None,
    fail_on_issue: bool = True,
) -> str | None:
    repo_name = _extract_organisation_and_repository_as_url_block(repo_name)

    if branch is None:
        branch = _master_branch_name(repo_name)

    md_content = None

    file_tree = fetch_repository_file_tree(repo_name, fail_on_issue=fail_on_issue)
    for i in file_tree:
        if i.lower().startswith("readme."):
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
                )
            except Exception as e:
                md_content = f"ERROR with {i} ({e})"

            # Only using the first file matching
            break

    if md_content is None:
        if fail_on_issue:
            raise ValueError(
                f"Unable to identify a README on the repository: {GITHUB_URL_BASE}{repo_name}"
            )
        else:
            md_content = "(NO README)"

    return md_content


def fetch_repository_file_tree(
    repository_url: str,
    fail_on_issue: bool = True,
) -> list[str] | str:
    repo_name = _extract_organisation_and_repository_as_url_block(repository_url)
    branch = _master_branch_name(repo_name)
    if branch is None:
        return "ERROR with file tree (unclear master branch)"
    try:
        r = _web_get(
            url=f"https://api.github.com/repos/{repo_name}/git/trees/{branch}?recursive=1",
            with_headers=True,
            is_json=True,
        )
        file_tree = [i["path"] for i in r["tree"]]
    except Exception as e:
        if fail_on_issue:
            raise e
        file_tree = f"ERROR with file tree ({e})"
    return file_tree

"""
Module to manage parsing of Gitlab data

Note:
- Doc: https://docs.gitlab.com/ee/api/projects.html#get-a-single-project
- Personal access token: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html
"""

from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus, urlparse

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate.src.model import ProjectDetails
from oss4climate.src.parsers import (
    ParsingTargets,
    cached_web_get_json,
    cached_web_get_text,
)

GITLAB_ANY_URL_PREFIX = (
    "https://gitlab."  # Since Gitlabs can be self-hosted on another domain
)
GITLAB_URL_BASE = "https://gitlab.com/"


class GitlabTargetType(Enum):
    GROUP = "GROUP"
    PROJECT = "PROJECT"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def identify(url: str) -> "GitlabTargetType":
        if not url.startswith(GITLAB_ANY_URL_PREFIX):
            return GitlabTargetType.UNKNOWN
        processed = _extract_organisation_and_repository_as_url_block(url)
        n_slashes = processed.count("/")
        if n_slashes < 1:
            return GitlabTargetType.GROUP
        elif n_slashes >= 1:
            # TODO : this is not good enough for sub-projects (but best quick fix for now)
            return GitlabTargetType.PROJECT
        else:
            return GitlabTargetType.UNKNOWN


def split_across_target_sets(
    x: list[str],
) -> ParsingTargets:
    groups = []
    projects = []
    others = []
    for i in x:
        tt_i = GitlabTargetType.identify(i)
        if tt_i is GitlabTargetType.GROUP:
            groups.append(i)
        elif tt_i is GitlabTargetType.PROJECT:
            projects.append(i)
        else:
            others.append(i)
    return ParsingTargets(
        gitlab_groups=groups, gitlab_projects=projects, unknown=others
    )


def _extract_gitlab_host(url: str) -> str:
    parsed_url = urlparse(url)
    return parsed_url.hostname


def _extract_organisation_and_repository_as_url_block(x: str) -> str:
    # Cleaning up Gitlab prefix
    if x.startswith(GITLAB_URL_BASE):
        x = x.replace(GITLAB_URL_BASE, "")
    else:
        h = _extract_gitlab_host(url=x)
        x = x.replace(f"https://{h}/", "")
    # Removing eventual extra information in URL
    for i in ["#", "&"]:
        if i in x:
            x = x.split(i)[0]
    # Removing trailing "/", if any
    while x.endswith("/"):
        x = x[:-1]
    return x


@lru_cache(maxsize=1)
def _gitlab_headers() -> dict[str, str]:
    if SETTINGS.GITLAB_ACCESS_TOKEN is None:
        log_info("Gitlab running in PUBLIC mode")
        headers = {}
    else:
        log_info("Gitlab running in AUTHENTICATED mode")
        headers = {
            "PRIVATE-TOKEN": SETTINGS.GITLAB_ACCESS_TOKEN,
        }
    return headers


def _web_get(url: str, with_headers: bool = True, is_json: bool = True) -> dict:
    if with_headers and url.startswith(GITLAB_URL_BASE):
        # Only using the headers with the actual gitlab.com calls
        headers = _gitlab_headers()
    else:
        headers = None
    if is_json:
        res = cached_web_get_json(url=url, headers=headers)
    else:
        res = cached_web_get_text(url=url, headers=headers)
    return res


def fetch_repositories_in_group(organisation_name: str) -> dict[str, str]:
    gitlab_host = _extract_gitlab_host(url=organisation_name)
    group_id = _extract_organisation_and_repository_as_url_block(organisation_name)
    res = _web_get(
        f"https://{gitlab_host}/api/v4/groups/{group_id}/projects",
    )
    return {r["name"]: r["web_url"] for r in res}


def _get_from_dict_with_default(d: dict, key: str, default: Any) -> Any:
    out = d.get(key)
    if out is None:
        return default
    else:
        return out


def fetch_repository_details(
    repo_path: str,
    fail_on_issue: bool = True,
) -> ProjectDetails:
    gitlab_host = _extract_gitlab_host(url=repo_path)
    repo_id = _extract_organisation_and_repository_as_url_block(repo_path)
    r = _web_get(
        f"https://{gitlab_host}/api/v4/projects/{quote_plus(repo_id)}?license=yes",
        is_json=True,
    )
    # organisation_url = f"https://{gitlab_host}/{repo_id.split('/')[0]}"
    organisation = repo_id.split("/")[0]
    license = _get_from_dict_with_default(r, "license", {}).get("name")

    try:
        url_readme_file = r["readme_url"].replace("/blob/", "/raw/") + "?inline=false"
        readme = _web_get(url_readme_file, with_headers=False, is_json=False)
    except Exception as e:
        if fail_on_issue:
            raise e
        else:
            readme = "(NO README)"

    # Fields treated as optional or unstable across non-"gitlab.com" instances
    fork_details = _get_from_dict_with_default(r, "forked_from_project", {})
    if isinstance(fork_details, dict):
        forked_from = _get_from_dict_with_default(fork_details, "namespace", {}).get(
            "web_url"
        )
    else:
        forked_from = None
    if "updated_at" in r:
        latest_update = datetime.fromisoformat(r["updated_at"]).date()
    else:
        latest_update = None

    if "last_activity_at" in r:
        last_commit = datetime.fromisoformat(r["last_activity_at"]).date()
    else:
        last_commit = None

    n_open_prs = None
    url_open_pr_raw = _get_from_dict_with_default(r, "_links", {})
    if url_open_pr_raw:
        url_open_pr = url_open_pr_raw.get("merge_requests")
        if url_open_pr:
            r_open_pr = _web_get(url_open_pr, is_json=True)
            n_open_prs = len([i for i in r_open_pr if i.get("state") == "open"])

    details = ProjectDetails(
        id=repo_id,
        name=r["name"],
        organisation=organisation,
        url=r["web_url"],
        website=None,
        description=r["description"],
        license=license,
        language=None,  # Not available
        latest_update=latest_update,
        last_commit=last_commit,
        open_pull_requests=n_open_prs,
        raw_details=r,
        master_branch=r["default_branch"],  # Using default branch as master branch
        readme=readme,
        is_fork=(forked_from is not None),
        forked_from=forked_from,
    )
    return details


if __name__ == "__main__":
    r = fetch_repository_details("https://gitlab.com/aossie/CarbonFootprint")
    print(r)

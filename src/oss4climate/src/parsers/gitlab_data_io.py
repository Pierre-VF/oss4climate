"""
Module to manage parsing of Gitlab data

Note:
- Doc: https://docs.gitlab.com/ee/api/projects.html#get-a-single-project
- Personal access token: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html
"""

from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus, urlparse

from oss4climate.src.config import SETTINGS
from oss4climate.src.helpers import get_key_of_maximum_value, url_base_matches_domain
from oss4climate.src.log import log_info
from oss4climate.src.model import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.parsers import (
    ParsingTargets,
    cached_web_get_json,
    cached_web_get_text,
)

GITLAB_ANY_URL_PREFIX = (
    "https://gitlab."  # Since Gitlabs can be self-hosted on another domain
)
GITLAB_DOMAIN = "gitlab.com"
GITLAB_URL_BASE = f"https://{GITLAB_DOMAIN}/"


def is_gitlab_url(url: str, include_self_hosted: bool = True) -> bool:
    if include_self_hosted:
        if url.startswith(GITLAB_ANY_URL_PREFIX):
            return True
        elif url.startswith("https://git."):
            try:
                r = fetch_repository_language_details(url)
                return True
            except Exception:
                # Any failure to run the request means that it's not a Gitlab
                return False
        else:
            return False
    else:
        return url_base_matches_domain(url, GITLAB_DOMAIN)


def _clean_url(url: str) -> str:
    x = url.split("/-/")[0]  # To remove trees and the like
    # Removing eventual extra information in URL
    for i in ["#", "&"]:
        if i in x:
            x = x.split(i)[0]
    # Removing trailing "/", if any
    while x.endswith("/"):
        x = x[:-1]
    return x


class GitlabTargetType(Enum):
    GROUP = "GROUP"
    PROJECT = "PROJECT"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def identify(url: str) -> tuple["GitlabTargetType", str]:
        if not is_gitlab_url(url):
            return GitlabTargetType.UNKNOWN, url
        processed = _extract_organisation_and_repository_as_url_block(url)
        clean_url = _clean_url(url)  # To remove trees and the like
        n_slashes = processed.count("/")
        if n_slashes < 1:
            return GitlabTargetType.GROUP, clean_url
        elif n_slashes >= 1:
            # TODO : this is not good enough for sub-projects (but best quick fix for now)
            return GitlabTargetType.PROJECT, clean_url
        else:
            return GitlabTargetType.UNKNOWN, clean_url


def split_across_target_sets(
    x: list[str],
) -> ParsingTargets:
    groups = []
    projects = []
    others = []
    for i in x:
        tt_i, clean_url_i = GitlabTargetType.identify(i)
        if tt_i is GitlabTargetType.GROUP:
            groups.append(clean_url_i)
        elif tt_i is GitlabTargetType.PROJECT:
            projects.append(clean_url_i)
        else:
            others.append(i)
    return ParsingTargets(
        gitlab_groups=groups, gitlab_projects=projects, unknown=others
    )


def _extract_gitlab_host(url: str) -> str:
    parsed_url = urlparse(url)
    return parsed_url.hostname


def _extract_organisation_and_repository_as_url_block(x: str) -> str:
    x = _clean_url(x)

    # Cleaning up Gitlab prefix
    if is_gitlab_url(x, include_self_hosted=False):
        x = x.replace(GITLAB_URL_BASE, "")
    else:
        h = _extract_gitlab_host(url=x)
        x = x.replace(f"https://{h}/", "")

    fixed_x = "/".join(
        x.split("/")[:2]
    )  # For complex multiple projects nested, this might not work well

    return fixed_x


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


def _web_get(
    url: str,
    with_headers: bool = True,
    is_json: bool = True,
    cache_lifetime: timedelta | None = None,
) -> dict:
    if with_headers and is_gitlab_url(url, include_self_hosted=False):
        # Only using the headers with the actual gitlab.com calls
        headers = _gitlab_headers()
    else:
        headers = None
    if is_json:
        res = cached_web_get_json(
            url=url, headers=headers, cache_lifetime=cache_lifetime
        )
    else:
        res = cached_web_get_text(
            url=url, headers=headers, cache_lifetime=cache_lifetime
        )
    return res


def fetch_repositories_in_group(
    organisation_name: str,
    cache_lifetime: timedelta | None = None,
) -> dict[str, str]:
    gitlab_host = _extract_gitlab_host(url=organisation_name)
    group_id = _extract_organisation_and_repository_as_url_block(organisation_name)
    res = _web_get(
        f"https://{gitlab_host}/api/v4/groups/{group_id}/projects",
        cache_lifetime=cache_lifetime,
    )
    return {r["name"]: r["web_url"] for r in res}


def fetch_repository_language_details(
    repo_name: str,
    cache_lifetime: timedelta | None = None,
) -> dict[str, int]:
    gitlab_host = _extract_gitlab_host(url=repo_name)
    repo_id = _extract_organisation_and_repository_as_url_block(repo_name)
    r = _web_get(
        f"https://{gitlab_host}/api/v4/projects/{quote_plus(repo_id)}/languages",
        cache_lifetime=cache_lifetime,
    )
    return r


def fetch_repository_readme(
    repo_name: str,
    fail_on_issue: bool = True,
    cache_lifetime: timedelta | None = None,
) -> tuple[str | None, EnumDocumentationFileType]:
    gitlab_host = _extract_gitlab_host(url=repo_name)
    repo_id = _extract_organisation_and_repository_as_url_block(repo_name)
    r = _web_get(
        f"https://{gitlab_host}/api/v4/projects/{quote_plus(repo_id)}?license=yes",
        is_json=True,
        cache_lifetime=cache_lifetime,
    )
    try:
        url_readme_file = r["readme_url"].replace("/blob/", "/raw/")
        readme = _web_get(
            url_readme_file + "?inline=false", with_headers=False, is_json=False
        )
        readme_type = EnumDocumentationFileType.from_filename(url_readme_file)
    except Exception as e:
        if fail_on_issue:
            raise e
        else:
            readme = "(NO README)"
            readme_type = EnumDocumentationFileType.UNKNOWN
    return readme, readme_type


def _get_from_dict_with_default(d: dict, key: str, default: Any) -> Any:
    out = d.get(key)
    if out is None:
        return default
    else:
        return out


def fetch_repository_details(
    repo_path: str,
    fail_on_issue: bool = True,
    cache_lifetime: timedelta | None = None,
) -> ProjectDetails:
    gitlab_host = _extract_gitlab_host(url=repo_path)
    repo_id = _extract_organisation_and_repository_as_url_block(repo_path)
    r = _web_get(
        f"https://{gitlab_host}/api/v4/projects/{quote_plus(repo_id)}?license=yes",
        is_json=True,
        cache_lifetime=cache_lifetime,
    )
    # organisation_url = f"https://{gitlab_host}/{repo_id.split('/')[0]}"
    organisation = repo_id.split("/")[0]
    license = _get_from_dict_with_default(r, "license", {}).get("name")
    license_url = r.get("license_url")
    (
        readme,
        readme_type,
    ) = fetch_repository_readme(
        repo_path,
        fail_on_issue=fail_on_issue,
        cache_lifetime=cache_lifetime,
    )
    raw_languages = fetch_repository_language_details(
        repo_path, cache_lifetime=cache_lifetime
    )
    dominant_language = get_key_of_maximum_value(raw_languages)
    languages = list(raw_languages.keys())

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
            r_open_pr = _web_get(
                url_open_pr, is_json=True, cache_lifetime=cache_lifetime
            )
            n_open_prs = len([i for i in r_open_pr if i.get("state") == "open"])

    details = ProjectDetails(
        id=repo_id,
        name=r["name"],
        organisation=organisation,
        url=r["web_url"],
        website=None,
        description=r["description"],
        license=license,
        license_url=license_url,
        language=dominant_language,
        all_languages=languages,
        latest_update=latest_update,
        last_commit=last_commit,
        open_pull_requests=n_open_prs,
        raw_details=r,
        master_branch=r["default_branch"],  # Using default branch as master branch
        readme=readme,
        readme_type=readme_type,
        is_fork=(forked_from is not None),
        forked_from=forked_from,
    )
    return details


if __name__ == "__main__":
    r = fetch_repository_details("https://gitlab.com/aossie/CarbonFootprint")
    print(r)

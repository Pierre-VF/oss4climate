"""
This module takes care of scraping data from Bitbucket-hosted code

NOTE: at this stage there are too few repos to justify this implementation in details

This will implements:
- Fetching repositories in an project
- Fetching data in a repository (details in the ProjectDetails(...) return)
- Bitbucket URL identification and management (cleanup, type classification, ...)
"""

from enum import Enum

from oss4climate.src.helpers import url_base_matches_domain
from oss4climate.src.parsers import (
    ParsingTargets,
)

BITBUCKET_DOMAIN = "bitbucket.org"
BITBUCKET_URL_BASE = f"https://{BITBUCKET_DOMAIN}/"


def is_bitbucket_url(url: str) -> bool:
    return url_base_matches_domain(url, BITBUCKET_DOMAIN)


def _extract_organisation_and_repository_as_url_block(x: str) -> str:
    # Cleaning up Bitbucket prefix
    if is_bitbucket_url(x):
        x = x.replace(BITBUCKET_URL_BASE, "")
    # Not keeping more than 2 slashes
    fixed_x = "/".join(x.split("/")[:2])
    # Removing eventual extra information in URL
    for i in ["#", "&"]:
        if i in fixed_x:
            fixed_x = fixed_x.split(i)[0]
    # Removing trailing "/", if any
    while fixed_x.endswith("/"):
        fixed_x = fixed_x[:-1]
    return fixed_x


def clean_bitbucket_repository_url(url: str) -> str:
    return BITBUCKET_URL_BASE + _extract_organisation_and_repository_as_url_block(url)


class BitbucketTargetType(Enum):
    PROJECT = "PROJECT"
    REPOSITORY = "REPOSITORY"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def identify(url: str) -> "BitbucketTargetType":
        if not is_bitbucket_url(url):
            return BitbucketTargetType.UNKNOWN
        processed = _extract_organisation_and_repository_as_url_block(url)
        n_slashes = processed.count("/")
        if n_slashes < 1:
            return BitbucketTargetType.PROJECT
        elif n_slashes == 1:
            return BitbucketTargetType.REPOSITORY
        else:
            return BitbucketTargetType.UNKNOWN


def split_across_target_sets(
    x: list[str],
) -> ParsingTargets:
    projs = []
    repos = []
    others = []
    for i in x:
        tt_i = BitbucketTargetType.identify(i)
        if tt_i is BitbucketTargetType.PROJECT:
            projs.append(i)
        elif tt_i is BitbucketTargetType.REPOSITORY:
            repos.append(i)
        else:
            others.append(i)

    return ParsingTargets(
        bitbucket_projects=[clean_bitbucket_repository_url(i) for i in projs],
        bitbucket_repositories=[clean_bitbucket_repository_url(i) for i in repos],
        unknown=others,
    )


def extract_repository_organisation(repo_path: str) -> str:
    repo_path = _extract_organisation_and_repository_as_url_block(repo_path)
    organisation = repo_path.split("/")[0]
    return organisation


if __name__ == "__main__":
    pass

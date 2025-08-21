"""
This module takes care of scraping data from Bitbucket-hosted code

NOTE: at this stage there are too few repos to justify this implementation in details

This will implements:
- Fetching repositories in an project
- Fetching data in a repository (details in the ProjectDetails(...) return)
- Bitbucket URL identification and management (cleanup, type classification, ...)
"""

from datetime import timedelta
from enum import Enum

from oss4climate.src.helpers import url_base_matches_domain
from oss4climate.src.models import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.parsers import (
    ParsingTargets,
)
from oss4climate.src.parsers.git_platforms.common import (
    GitPlatformScraper as _GPScraper,
)

BITBUCKET_DOMAIN = "bitbucket.org"
BITBUCKET_URL_BASE = f"https://{BITBUCKET_DOMAIN}/"


class BitbucketTargetType(Enum):
    PROJECT = "PROJECT"
    REPOSITORY = "REPOSITORY"
    UNKNOWN = "UNKNOWN"


class BitbucketScraper(_GPScraper):
    """This is the basic structure of the scraper for a Git-hosting platform"""

    def __init__(
        self,
        cache_lifetime: timedelta | None = None,
    ):
        super().__init__(cache_lifetime=cache_lifetime)

    def _extract_organisation_and_repository_as_url_block(self, x: str) -> str:
        # Cleaning up Bitbucket prefix
        if self.is_relevant_url(x):
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

    def is_relevant_url(
        self,
        url: str,
        **kwargs,
    ) -> bool:
        return url_base_matches_domain(url, BITBUCKET_DOMAIN)

    def minimalise_resource_url(self, url: str) -> str:
        return f"{BITBUCKET_URL_BASE}{self._extract_organisation_and_repository_as_url_block(url)}"

    def split_across_target_sets(
        self,
        x: list[str],
    ) -> ParsingTargets:
        projs = []
        repos = []
        others = []
        for i in x:
            tt_i = self.identify_target_type(i)
            if tt_i is BitbucketTargetType.PROJECT:
                projs.append(i)
            elif tt_i is BitbucketTargetType.REPOSITORY:
                repos.append(i)
            else:
                others.append(i)

        return ParsingTargets(
            bitbucket_projects=[self.minimalise_resource_url(i) for i in projs],
            bitbucket_repositories=[self.minimalise_resource_url(i) for i in repos],
            unknown=others,
        )

    def fetch_repository_readme(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
        cache_lifetime: timedelta | None = None,
    ) -> tuple[str | None, EnumDocumentationFileType]:
        pass

    def fetch_project_details(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
    ) -> ProjectDetails:
        pass

    def fetch_repository_language_details(
        self,
        repo_id: str,
    ) -> ProjectDetails:
        pass

    def fetch_repositories_in_organisation(
        self,
        organisation_name: str,
    ) -> dict[str, str]:
        pass

    def fetch_master_branch_name(
        self,
        repo_id: str,
    ) -> str | None:
        pass

    def fetch_repository_file_tree(
        self,
        repo_id: str,
        fail_on_issue: bool = True,
    ) -> list[str] | str:
        pass

    def extract_repository_organisation(self, repo_path: str) -> str:
        repo_path = self._extract_organisation_and_repository_as_url_block(repo_path)
        organisation = repo_path.split("/")[0]
        return organisation

    def identify_target_type(self, url: str) -> BitbucketTargetType:
        if not self.is_relevant_url(url):
            return BitbucketTargetType.UNKNOWN
        processed = self._extract_organisation_and_repository_as_url_block(url)
        n_slashes = processed.count("/")
        if n_slashes < 1:
            return BitbucketTargetType.PROJECT
        elif n_slashes == 1:
            return BitbucketTargetType.REPOSITORY
        else:
            return BitbucketTargetType.UNKNOWN

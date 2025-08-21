from abc import abstractmethod
from datetime import timedelta
from enum import Enum

from oss4climate.src.models import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.parsers import (
    ParsingTargets,
)


class GitPlatformScraper:
    """This is the basic structure of the scraper for a Git-hosting platform"""

    def __init__(
        self,
        cache_lifetime: timedelta | None = None,
    ):
        self.cache_lifetime = cache_lifetime

    @abstractmethod
    def is_relevant_url(
        self,
        url: str,
        **kwargs,
    ) -> bool:
        pass

    def minimalise_resource_url(self, url: str) -> str:
        pass

    @abstractmethod
    def split_across_target_sets(
        self,
        x: list[str],
    ) -> ParsingTargets:
        pass

    @abstractmethod
    def fetch_repository_readme(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
        cache_lifetime: timedelta | None = None,
    ) -> tuple[str | None, EnumDocumentationFileType]:
        pass

    @abstractmethod
    def fetch_project_details(
        self,
        repo_id: str,
        branch: str | None = None,
        fail_on_issue: bool = True,
    ) -> ProjectDetails:
        pass

    @abstractmethod
    def fetch_repository_language_details(
        self,
        repo_id: str,
    ) -> ProjectDetails:
        pass

    @abstractmethod
    def fetch_repositories_in_organisation(
        self,
        organisation_name: str,
    ) -> dict[str, str]:
        pass

    @abstractmethod
    def fetch_master_branch_name(
        self,
        repo_id: str,
    ) -> str | None:
        pass

    @abstractmethod
    def fetch_repository_file_tree(
        self,
        repo_id: str,
        fail_on_issue: bool = True,
    ) -> list[str] | str:
        pass

    @abstractmethod
    def extract_repository_organisation(self, repo_path: str) -> str:
        pass

    @abstractmethod
    def identify_target_type(self, url: str) -> Enum:
        pass

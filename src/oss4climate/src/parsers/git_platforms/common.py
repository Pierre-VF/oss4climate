import os
from abc import abstractmethod
from datetime import timedelta
from enum import Enum
from typing import Any, Callable

from oss4climate.src.log import log_info
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


def clone_git_repository(url: str, path: str) -> None:
    """Clones a Git repository in a given folder

    Note: this is a simple implementation assuming that Git is installed and configured on your system

    :param url: URL of the git (for git clone command)
    :param path: path of the directory in which the Git must be cloned
    """
    try:
        os.system(f"git clone {url} {path}")
    except Exception as e:
        raise RuntimeError(
            "Error running git clone (do you have Git installed in your environment?)"
        ) from e
    log_info(f"Cloned git in {path}")


def map_function_on_all_files_in_folder(
    f: Callable,
    path: str,
    apply_on_file_content: bool = True,
    include_subfolders: bool = True,
) -> dict[str, Any]:
    """
    Maps the results of calling a function on all the files of a given directory

    :param f: function to map
    :param path: path of the directory
    _param apply_on_file_content: if True, applies the function on the content (read in text mode) of the file,
        else applies the function on the file path
    :param include_subfolders: if True, maps the function to all files in sub-directories too, defaults to True
    :return: dictionary of results of calling the function f on all files
    """
    out = dict()
    for i in os.scandir(path):
        if i.name in [".git", ".github", ".devcontainer"]:
            # Ignore typically irrelevant folders
            pass
        else:
            path_i = i.path
            if i.is_file():
                if apply_on_file_content:
                    with open(path_i, "r") as f_i:
                        out[path_i] = f(f_i.read())
                else:
                    out[path_i] = f(path_i)
            elif i.is_dir():
                if include_subfolders:
                    out_sub = map_function_on_all_files_in_folder(
                        f,
                        path=path_i,
                        apply_on_file_content=apply_on_file_content,
                        include_subfolders=True,
                    )
                    out = out | out_sub
    return out

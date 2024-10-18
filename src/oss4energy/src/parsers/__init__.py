"""
Module for parsers and web I/O
"""

import time
from dataclasses import dataclass, field

import requests
import tomllib
from tomlkit import document, dump

from oss4energy.src.database import load_from_database, save_to_database
from oss4energy.src.helpers import sorted_list_of_unique_elements
from oss4energy.src.log import log_info

WEB_SESSION = requests.Session()


def _cached_web_get(
    url: str,
    headers: dict | None = None,
    wait_after_web_query: bool = True,
    is_json: bool = True,
) -> dict | str:
    # Uses the cache to ensure that requests are minimised
    out = load_from_database(url, is_json=is_json)
    if out is None:
        log_info(f"Web GET: {url}")
        r = WEB_SESSION.get(
            url=url,
            headers=headers,
        )
        if is_json:
            r.raise_for_status()
            out = r.json()
        else:
            if r.status_code == 404:
                log_info(f"> No resource found for: {url}")
                out = "(None)"
            else:
                r.raise_for_status()
                out = r.text
        save_to_database(url, out, is_json=is_json)
        if wait_after_web_query:
            time.sleep(
                0.1
            )  # To avoid triggering rate limits on APIs and be nice to servers
    else:
        log_info(f"Cache-loading: {url}")
    return out


def cached_web_get_json(
    url: str, headers: dict | None = None, wait_after_web_query: bool = True
) -> dict:
    return _cached_web_get(
        url=url,
        headers=headers,
        wait_after_web_query=wait_after_web_query,
        is_json=True,
    )


def cached_web_get_text(
    url: str, headers: dict | None = None, wait_after_web_query: bool = True
) -> str:
    return _cached_web_get(
        url=url,
        headers=headers,
        wait_after_web_query=wait_after_web_query,
        is_json=False,
    )


@dataclass
class ParsingTargets:
    """
    Class to make aggregation of parsings across targets easier to manage and work with
    """

    github_repositories: list[str] = field(default_factory=list)
    github_organisations: list[str] = field(default_factory=list)
    gitlab_repositories: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)

    def __add__(self, other: "ParsingTargets") -> "ParsingTargets":
        return ParsingTargets(
            github_organisations=self.github_organisations + other.github_organisations,
            github_repositories=self.github_repositories + other.github_repositories,
            gitlab_repositories=self.gitlab_repositories + other.gitlab_repositories,
            unknown=self.unknown + other.unknown,
            invalid=self.invalid + other.invalid,
        )

    def __iadd__(self, other: "ParsingTargets") -> "ParsingTargets":
        self.github_repositories += other.github_repositories
        self.github_organisations += other.github_organisations
        self.gitlab_repositories += other.gitlab_repositories
        self.unknown += other.unknown
        self.invalid += other.invalid
        return self

    def ensure_sorted_and_unique_elements(self) -> None:
        """
        Sorts all fields alphabetically and ensures that there is no redundancies in them
        """
        self.github_repositories = sorted_list_of_unique_elements(
            self.github_repositories
        )
        self.github_organisations = sorted_list_of_unique_elements(
            self.github_organisations
        )
        self.gitlab_repositories = sorted_list_of_unique_elements(
            self.gitlab_repositories
        )
        self.unknown = sorted_list_of_unique_elements(self.unknown)
        self.invalid = sorted_list_of_unique_elements(self.invalid)

    @staticmethod
    def from_toml(toml_file_path: str) -> "ParsingTargets":
        with open(toml_file_path, "rb") as f:
            x = tomllib.load(f)

        return ParsingTargets(
            github_organisations=x["github_hosted"].get("organisations", []),
            github_repositories=x["github_hosted"].get("repositories", []),
            gitlab_repositories=x["gitlab_hosted"].get("repositories", []),
            unknown=x["dropped_targets"].get("urls", []),
            invalid=x["dropped_targets"].get("invalid_urls", []),
        )

    def to_toml(self, toml_file_path: str) -> None:
        # Outputting to a new TOML
        doc = document()
        toml_ready_dict = {
            "github_hosted": {
                "organisations": self.github_organisations,
                "repositories": self.github_repositories,
            },
            "gitlab_hosted": {
                "repositories": self.gitlab_repositories,
            },
            "dropped_targets": {
                "urls": self.unknown,
                "invalid_urls": self.invalid,
            },
        }

        for k, v in toml_ready_dict.items():
            doc.add(k, v)

        log_info(f"Exporting new index to {toml_file_path}")
        with open(toml_file_path, "w") as fp:
            dump(doc, fp, sort_keys=True)


def identify_parsing_targets(x: list[str]) -> ParsingTargets:
    from oss4energy.src.parsers import github_data_io, gitlab_data_io

    out_github = github_data_io.split_across_target_sets(x)
    out_gitlab = gitlab_data_io.split_across_target_sets(out_github.unknown)
    out_github.unknown = []

    out = out_github + out_gitlab
    return out

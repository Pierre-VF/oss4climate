"""
Module for parsers and web I/O
"""

import time
from dataclasses import dataclass, field
from datetime import timedelta

import requests
import tomllib
from tomlkit import document, dump

from oss4climate.src.database import load_from_database, save_to_database
from oss4climate.src.helpers import (
    sorted_list_of_cleaned_urls,
    url_base_matches_domain,
)
from oss4climate.src.log import log_info
from oss4climate.src.nlp.html_io import find_all_links_in_html
from oss4climate.src.nlp.markdown_io import find_all_links_in_markdown
from oss4climate.src.nlp.rst_io import RstParsingError, find_all_links_in_rst


class RateLimitError(RuntimeError):
    pass


WEB_SESSION = requests.Session()
ERROR_404_MARKER = "404"


def _cached_web_get(
    url: str,
    headers: dict | None = None,
    wait_after_web_query: bool = True,
    is_json: bool = True,
    raise_rate_limit_error_on_403: bool = True,
    rate_limiting_wait_s: float = 0.1,
    cache_lifetime: timedelta | None = None,
) -> dict | str:
    # Uses the cache to ensure that requests are minimised
    out = load_from_database(url, is_json=is_json, cache_lifetime=cache_lifetime)

    if out is None:
        log_info(f"Web GET: {url}")
        r = WEB_SESSION.get(
            url=url,
            headers=headers,
        )
        if r.status_code == 404:
            save_to_database(url, ERROR_404_MARKER, is_json=is_json)
            raise requests.exceptions.HTTPError(
                f"404 Client Error: Not Found for url: {url}"
            )
        if r.status_code == 403 and raise_rate_limit_error_on_403:
            raise RateLimitError(f"Rate limit hit (url={url} // {r.text})")
        r.raise_for_status()
        if is_json:
            out = r.json()
        else:
            out = r.text
        save_to_database(url, out, is_json=is_json)
        if wait_after_web_query:
            # To avoid triggering rate limits on APIs and be nice to servers
            time.sleep(rate_limiting_wait_s)
    elif out == ERROR_404_MARKER:
        raise requests.exceptions.HTTPError(
            f"404 Client Error: Not Found for url: {url}"
        )
    else:
        log_info(f"Cache-loading: {url}")
    return out


def cached_web_get_json(
    url: str,
    headers: dict | None = None,
    wait_after_web_query: bool = True,
    raise_rate_limit_error_on_403: bool = False,
    rate_limiting_wait_s: float = 0.1,
    cache_lifetime: timedelta | None = None,
) -> dict:
    return _cached_web_get(
        url=url,
        headers=headers,
        wait_after_web_query=wait_after_web_query,
        is_json=True,
        raise_rate_limit_error_on_403=raise_rate_limit_error_on_403,
        rate_limiting_wait_s=rate_limiting_wait_s,
        cache_lifetime=cache_lifetime,
    )


def cached_web_get_text(
    url: str,
    headers: dict | None = None,
    wait_after_web_query: bool = True,
    raise_rate_limit_error_on_403: bool = False,
    rate_limiting_wait_s: float = 0.1,
    cache_lifetime: timedelta | None = None,
) -> str:
    return _cached_web_get(
        url=url,
        headers=headers,
        wait_after_web_query=wait_after_web_query,
        is_json=False,
        raise_rate_limit_error_on_403=raise_rate_limit_error_on_403,
        rate_limiting_wait_s=rate_limiting_wait_s,
        cache_lifetime=cache_lifetime,
    )


def url_qualifies(x: str) -> bool:
    if url_base_matches_domain(x, "github.com"):
        if (
            x.startswith("https://github.com/settings/")
            or x.startswith("https://github.com/user-attachments/")
            or x.startswith("https://github.com/sponsors/")
            or x.startswith("https://github.com/settings/")
        ):
            return False
        elif (
            x.endswith("/wiki")
            or ("/wiki/" in x)
            or x.endswith("/discussions")
            or ("/discussions/" in x)
            or x.endswith("/issues")
            or ("/issues/" in x)
            or x.endswith("/milestones")
            or ("/milestone/" in x)
            or x.endswith("/projects")
            or ("/projects/" in x)
            or x.endswith("/pulls")
            or ("/pull/" in x)
            or x.endswith("/releases")
            or ("/releases/" in x)
            or x.endswith("/tags")
            or ("/tag/" in x)
            # Specific endings
            or ("/actions" in x)
            or ("/security/policy" in x)
            # Specific sub-paths
            or ("/-/" in x)
            or ("/assets/" in x)
            or ("/badges/" in x)
            or ("/blob/" in x)
            or ("/commit/" in x)
            or ("/labels/" in x)
            or ("/graphs/" in x)
            or ("/public/" in x)
            or ("/raw/" in x)
            or ("/workflows/" in x)
        ):
            return False
        else:
            return True
    elif x.startswith("https://gitlab.com/"):
        if (
            ("/-/" in x)
            or ("/blob/" in x)
            or ("/badges/" in x)
            or x.endswith("/examples")
        ):
            return False
    # If hit nothing up thil here, then it's valid
    return True


@dataclass
class ParsingTargets:
    """
    Class to make aggregation of parsings across targets easier to manage and work with
    """

    github_repositories: list[str] = field(default_factory=list)
    github_organisations: list[str] = field(default_factory=list)
    gitlab_projects: list[str] = field(default_factory=list)
    gitlab_groups: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)

    def __add__(self, other: "ParsingTargets") -> "ParsingTargets":
        return ParsingTargets(
            github_organisations=self.github_organisations + other.github_organisations,
            github_repositories=self.github_repositories + other.github_repositories,
            gitlab_groups=self.gitlab_groups + other.gitlab_groups,
            gitlab_projects=self.gitlab_projects + other.gitlab_projects,
            unknown=self.unknown + other.unknown,
            invalid=self.invalid + other.invalid,
        )

    def __iadd__(self, other: "ParsingTargets") -> "ParsingTargets":
        self.github_repositories += other.github_repositories
        self.github_organisations += other.github_organisations
        self.gitlab_groups += other.gitlab_groups
        self.gitlab_projects += other.gitlab_projects
        self.unknown += other.unknown
        self.invalid += other.invalid
        return self

    def as_url_list(self, known_repositories_only: bool = True) -> list[str]:
        out = self.github_repositories + self.gitlab_projects
        if not known_repositories_only:
            out += (
                self.github_organisations
                + self.gitlab_groups
                + self.unknown
                + self.invalid
            )
        return out

    def ensure_sorted_cleaned_and_unique_elements(self) -> None:
        """
        Sorts all fields alphabetically and ensures that there is no redundancies in them
        """
        self.github_repositories = sorted_list_of_cleaned_urls(self.github_repositories)
        self.github_organisations = sorted_list_of_cleaned_urls(
            self.github_organisations
        )
        self.gitlab_groups = sorted_list_of_cleaned_urls(self.gitlab_groups)
        self.gitlab_projects = sorted_list_of_cleaned_urls(self.gitlab_projects)
        self.unknown = sorted_list_of_cleaned_urls(self.unknown)
        self.invalid = sorted_list_of_cleaned_urls(self.invalid)

    def __included_in_valid_targets(self, url: str) -> bool:
        return (
            url
            in self.github_organisations
            + self.github_repositories
            + self.gitlab_groups
            + self.gitlab_projects
        )

    def _target_is_valid(self, url: str) -> bool:
        if '"LINK"' in url:
            return False
        else:
            return url_qualifies(url)

    def _check_targets_validity(self, x: list[str]) -> list[str]:
        out = []
        for i in x:
            if self._target_is_valid(i):
                out.append(i)
            else:
                self.invalid.append(i)
        return out

    def ensure_targets_validity(self) -> None:
        self.github_organisations = self._check_targets_validity(
            self.github_organisations
        )
        self.github_repositories = self._check_targets_validity(
            self.github_repositories
        )
        self.gitlab_groups = self._check_targets_validity(self.gitlab_groups)
        self.gitlab_projects = self._check_targets_validity(self.gitlab_projects)

    def cleanup(self) -> None:
        """
        Method to cleanup the object (removing obsolete entries and redundancies)
        """
        self.ensure_sorted_cleaned_and_unique_elements()
        # Ensuring that only valid targets are used
        self.ensure_targets_validity()
        # Removing all repos that are listed in organisations/groups
        self.github_repositories = [
            i for i in self.github_repositories if i not in self.github_organisations
        ]
        self.gitlab_projects = [
            i for i in self.gitlab_projects if i not in self.gitlab_groups
        ]
        # Removing unknown repos
        self.unknown = [
            i for i in self.unknown if not self.__included_in_valid_targets(i)
        ]
        self.invalid = [
            i for i in self.invalid if not self.__included_in_valid_targets(i)
        ]

    @staticmethod
    def from_toml(toml_file_path: str) -> "ParsingTargets":
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Input must be a TOML file")

        with open(toml_file_path, "rb") as f:
            x = tomllib.load(f)

        return ParsingTargets(
            github_organisations=x["github_hosted"].get("organisations", []),
            github_repositories=x["github_hosted"].get("repositories", []),
            gitlab_groups=x["gitlab_hosted"].get("groups", []),
            gitlab_projects=x["gitlab_hosted"].get("projects", []),
            unknown=x["dropped_targets"].get("urls", []),
            invalid=x["dropped_targets"].get("invalid_urls", []),
        )

    def to_toml(self, toml_file_path: str) -> None:
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Output must be a TOML file")

        # Outputting to a new TOML
        doc = document()
        toml_ready_dict = {
            "github_hosted": {
                "organisations": self.github_organisations,
                "repositories": self.github_repositories,
            },
            "gitlab_hosted": {
                "groups": self.gitlab_groups,
                "projects": self.gitlab_projects,
            },
            "dropped_targets": {
                "urls": self.unknown,
                "invalid_urls": self.invalid,
            },
        }

        for k, v in toml_ready_dict.items():
            doc.add(k, v)

        with open(toml_file_path, "w") as fp:
            dump(doc, fp, sort_keys=True)


def identify_parsing_targets(x: list[str]) -> ParsingTargets:
    from oss4climate.src.parsers import github_data_io, gitlab_data_io

    out_github = github_data_io.split_across_target_sets(x)
    out_gitlab = gitlab_data_io.split_across_target_sets(out_github.unknown)
    out_github.unknown = []

    out = out_github + out_gitlab
    return out


def isolate_relevant_urls(urls: list[str]) -> list[str]:
    from oss4climate.src.parsers.github_data_io import GITHUB_URL_BASE
    from oss4climate.src.parsers.gitlab_data_io import GITLAB_ANY_URL_PREFIX

    def __f(i) -> bool:
        if i.startswith(GITHUB_URL_BASE):
            if (
                ("/tree/" in i)
                or ("/blob/" in i)
                or ("/actions/workflows/" in i)
                or i.endswith("/releases")
                or i.endswith("/issues")
            ):  # To avoid file detection leading to clutter
                return False
            else:
                return True
        elif i.startswith(GITLAB_ANY_URL_PREFIX):
            return True
        else:
            return False

    return [x for x in urls if __f(x)]


# For listings
@dataclass
class ResourceListing:
    """
    Class to make listings easier to work with
    """

    # For compatibility, all these repo must have data in the README
    github_readme_listings: list[str] = field(default_factory=list)

    # For compatibility, all these repo must have data in the README
    gitlab_readme_listings: list[str] = field(default_factory=list)

    # For the links must be given as hrefs in "a" tags
    webpage_html: list[str] = field(default_factory=list)

    # Faults
    fault_urls: list[str] = field(default_factory=list)
    fault_invalid_urls: list[str] = field(default_factory=list)

    def __add__(self, other: "ResourceListing") -> "ResourceListing":
        return ResourceListing(
            github_readme_listings=self.github_readme_listings
            + other.github_readme_listings,
            gitlab_readme_listings=self.gitlab_readme_listings
            + other.gitlab_readme_listings,
            webpage_html=self.webpage_html + other.webpage_html,
            fault_urls=self.fault_urls + other.fault_urls,
            fault_invalid_urls=self.fault_invalid_urls + other.fault_invalid_urls,
        )

    def __iadd__(self, other: "ResourceListing") -> "ResourceListing":
        self.github_readme_listings += other.github_readme_listings
        self.gitlab_readme_listings += other.gitlab_readme_listings
        self.webpage_html += other.webpage_html
        self.fault_urls += other.fault_urls
        self.fault_invalid_urls += other.fault_invalid_urls
        return self

    def ensure_sorted_cleaned_and_unique_elements(self) -> None:
        """
        Sorts all fields alphabetically and ensures that there is no redundancies in them
        """
        self.github_readme_listings = sorted_list_of_cleaned_urls(
            self.github_readme_listings
        )
        self.gitlab_readme_listings = sorted_list_of_cleaned_urls(
            self.gitlab_readme_listings
        )
        self.webpage_html = sorted_list_of_cleaned_urls(self.webpage_html)
        self.fault_urls = sorted_list_of_cleaned_urls(self.fault_urls)
        self.fault_invalid_urls = sorted_list_of_cleaned_urls(self.fault_invalid_urls)

    @staticmethod
    def from_toml(toml_file_path: str) -> "ResourceListing":
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Input must be a TOML file")

        with open(toml_file_path, "rb") as f:
            x = tomllib.load(f)

        return ResourceListing(
            github_readme_listings=x["github_hosted"].get("readme_listings", []),
            gitlab_readme_listings=x["gitlab_hosted"].get("readme_listings", []),
            webpage_html=x["webpages"].get("html", []),
            fault_urls=x["faults"].get("urls", []),
            fault_invalid_urls=x["faults"].get("invalid_urls", []),
        )

    def to_toml(self, toml_file_path: str) -> None:
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Output must be a TOML file")

        # Outputting to a new TOML
        doc = document()
        toml_ready_dict = {
            "github_hosted": {
                "readme_listings": self.github_readme_listings,
            },
            "gitlab_hosted": {
                "readme_listings": self.gitlab_readme_listings,
            },
            "webpages": {
                "html": self.webpage_html,
            },
            "faults": {
                "urls": self.fault_urls,
                "invalid_urls": self.fault_invalid_urls,
            },
        }

        for k, v in toml_ready_dict.items():
            doc.add(k, v)

        with open(toml_file_path, "w") as fp:
            dump(doc, fp, sort_keys=True)


def fetch_all_project_urls_from_html_webpage(
    url: str,
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    r_text = cached_web_get_text(url, cache_lifetime=cache_lifetime)
    rs = find_all_links_in_html(r_text)
    shortlisted_urls = isolate_relevant_urls(rs)
    return identify_parsing_targets(shortlisted_urls)


def fetch_all_project_urls_from_markdown_str(markdown_text: str) -> ParsingTargets:
    r = find_all_links_in_markdown(markdown_text)
    shortlisted_urls = isolate_relevant_urls(r)
    return identify_parsing_targets(shortlisted_urls)


def fetch_all_project_urls_from_rst_str(rst_text: str) -> ParsingTargets:
    try:
        r = find_all_links_in_rst(rst_text)
    except RstParsingError:
        r = []
    shortlisted_urls = isolate_relevant_urls(r)
    return identify_parsing_targets(shortlisted_urls)

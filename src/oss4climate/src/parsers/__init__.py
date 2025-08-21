"""
Module for parsers and web I/O
"""

import json
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pandas as pd
import requests
import tomllib
from tomlkit import document, dump

from oss4climate.src.database import load_from_database, save_to_database
from oss4climate.src.helpers import (
    cleaned_url,
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
    elif x.startswith("https://gitlab.com"):
        if (
            ("/-/" in x)
            or ("/blob/" in x)
            or ("/badges/" in x)
            or x.endswith("/examples")
        ):
            return False
        # Else ensure that there's at least an organisation or project in the URL
        return len(x.replace("https://gitlab.com", "")) > 1
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
    bitbucket_projects: list[str] = field(default_factory=list)
    bitbucket_repositories: list[str] = field(default_factory=list)
    codeberg_organisations: list[str] = field(default_factory=list)
    codeberg_repositories: list[str] = field(default_factory=list)

    unknown: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)

    def __add__(self, other: "ParsingTargets") -> "ParsingTargets":
        return ParsingTargets(
            github_organisations=self.github_organisations + other.github_organisations,
            github_repositories=self.github_repositories + other.github_repositories,
            bitbucket_projects=self.bitbucket_projects + other.bitbucket_projects,
            bitbucket_repositories=self.bitbucket_repositories
            + other.bitbucket_repositories,
            gitlab_groups=self.gitlab_groups + other.gitlab_groups,
            gitlab_projects=self.gitlab_projects + other.gitlab_projects,
            unknown=self.unknown + other.unknown,
            invalid=self.invalid + other.invalid,
            codeberg_organisations=self.codeberg_organisations
            + other.codeberg_organisations,
            codeberg_repositories=self.codeberg_repositories
            + other.codeberg_repositories,
        )

    def __iadd__(self, other: "ParsingTargets") -> "ParsingTargets":
        self.github_repositories += other.github_repositories
        self.github_organisations += other.github_organisations
        self.gitlab_groups += other.gitlab_groups
        self.gitlab_projects += other.gitlab_projects
        self.bitbucket_projects += other.bitbucket_projects
        self.bitbucket_repositories += other.bitbucket_repositories
        self.unknown += other.unknown
        self.invalid += other.invalid
        self.codeberg_organisations += other.codeberg_organisations
        self.codeberg_repositories += other.codeberg_repositories
        return self

    def __len__(self) -> int:
        return (
            len(self.github_repositories)
            + len(self.github_organisations)
            + len(self.gitlab_projects)
            + len(self.gitlab_groups)
            + len(self.bitbucket_projects)
            + len(self.bitbucket_repositories)
            + len(self.codeberg_organisations)
            + len(self.codeberg_repositories)
            + len(self.unknown)
            + len(self.invalid)
        )

    def as_url_list(self, known_repositories_only: bool = True) -> list[str]:
        out = (
            self.github_repositories
            + self.gitlab_projects
            + self.bitbucket_repositories
            + self.codeberg_repositories
        )
        if not known_repositories_only:
            out += (
                self.github_organisations
                + self.gitlab_groups
                + self.bitbucket_projects
                + self.codeberg_organisations
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
        self.bitbucket_projects = sorted_list_of_cleaned_urls(self.bitbucket_projects)
        self.bitbucket_repositories = sorted_list_of_cleaned_urls(
            self.bitbucket_repositories
        )
        self.codeberg_organisations = sorted_list_of_cleaned_urls(
            self.codeberg_organisations
        )
        self.codeberg_repositories = sorted_list_of_cleaned_urls(
            self.codeberg_repositories
        )
        self.unknown = sorted_list_of_cleaned_urls(self.unknown)
        self.invalid = sorted_list_of_cleaned_urls(self.invalid)

    def __included_in_valid_targets(self, url: str) -> bool:
        return (
            url
            in self.github_organisations
            + self.github_repositories
            + self.gitlab_groups
            + self.gitlab_projects
            + self.bitbucket_projects
            + self.bitbucket_repositories
            + self.codeberg_organisations
            + self.codeberg_repositories
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
        self.bitbucket_projects = self._check_targets_validity(self.bitbucket_projects)
        self.bitbucket_repositories = self._check_targets_validity(
            self.bitbucket_repositories
        )
        self.codeberg_organisations = self._check_targets_validity(
            self.codeberg_organisations
        )
        self.codeberg_repositories = self._check_targets_validity(
            self.codeberg_repositories
        )

    def cleanup(self, drop_invalid: bool = False, drop_unknown: bool = False) -> None:
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
        self.bitbucket_repositories = [
            i for i in self.bitbucket_repositories if i not in self.bitbucket_projects
        ]
        self.codeberg_repositories = [
            i
            for i in self.codeberg_repositories
            if i not in self.codeberg_organisations
        ]
        if drop_invalid:
            self.invalid = []
        else:
            self.invalid = [
                i for i in self.invalid if not self.__included_in_valid_targets(i)
            ]
        if drop_unknown:
            self.unknown = []
        else:
            # Removing unknown repos
            self.unknown = [
                i for i in self.unknown if not self.__included_in_valid_targets(i)
            ]

    @staticmethod
    def from_toml(toml_file_path: str) -> "ParsingTargets":
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Input must be a TOML file")

        with open(toml_file_path, "rb") as f:
            x = tomllib.load(f)

        for i in [
            "github_hosted",
            "gitlab_hosted",
            "bitbucket_hosted",
            "codeberg_hosted",
        ]:
            if x.get(i) is None:
                x[i] = {}

        return ParsingTargets(
            github_organisations=x["github_hosted"].get("organisations", []),
            github_repositories=x["github_hosted"].get("repositories", []),
            gitlab_groups=x["gitlab_hosted"].get("groups", []),
            gitlab_projects=x["gitlab_hosted"].get("projects", []),
            bitbucket_projects=x["bitbucket_hosted"].get("projects", []),
            bitbucket_repositories=x["bitbucket_hosted"].get("repositories", []),
            codeberg_organisations=x["codeberg_hosted"].get("organisations", []),
            codeberg_repositories=x["codeberg_hosted"].get("repositories", []),
            unknown=x["dropped_targets"].get("urls", []),
            invalid=x["dropped_targets"].get("invalid_urls", []),
        )

    def to_toml(self, toml_file_path: str) -> None:
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Output must be a TOML file")

        # Outputting to a new TOML
        doc = document()
        toml_ready_dict = {
            "bitbucket_hosted": {
                "projects": self.bitbucket_projects,
                "repositories": self.bitbucket_repositories,
            },
            "codeberg_hosted": {
                "organisations": self.codeberg_organisations,
                "repositories": self.codeberg_repositories,
            },
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
    from oss4climate.src.parsers.git_platforms.bitbucket_io import BitbucketScraper
    from oss4climate.src.parsers.git_platforms.codeberg_io import CodebergScraper
    from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
    from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper

    out_github = GithubScraper().split_across_target_sets(x)
    out_gitlab = GitlabScraper().split_across_target_sets(out_github.unknown)
    out_github.unknown = []
    out_bitbucket = BitbucketScraper().split_across_target_sets(out_gitlab.unknown)
    out_gitlab.unknown = []
    out_codeberg = CodebergScraper().split_across_target_sets(out_bitbucket.unknown)
    out_bitbucket.unknown = []

    out = out_bitbucket + out_github + out_gitlab + out_codeberg
    return out


def isolate_relevant_urls(urls: list[str]) -> list[str]:
    from oss4climate.src.parsers.git_platforms.bitbucket_io import BitbucketScraper
    from oss4climate.src.parsers.git_platforms.codeberg_io import CodebergScraper
    from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
    from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper

    ghs = GithubScraper()
    gls = GitlabScraper()
    cbs = CodebergScraper()
    bbs = BitbucketScraper()

    def __f(i) -> bool:
        if ghs.is_relevant_url(i):
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
        elif gls.is_relevant_url(i):
            return True
        elif bbs.is_relevant_url(i):
            return True
        elif cbs.is_relevant_url(i):
            return True
        else:
            return False

    return [x for x in urls if __f(x)]


# For listings
_type_listing_entry = str | dict[str, str]


def _flexible_sorted_list_of_targets(x: _type_listing_entry) -> list[dict[str, str]]:
    urls = []
    urls_with_licenses = dict()
    for i in x:
        if isinstance(i, dict):
            if "url" in i:
                cleaned_url_i = cleaned_url(i["url"])
                urls.append(cleaned_url_i)
                urls_with_licenses[cleaned_url_i] = i
            else:
                raise ValueError(f"Entry does not have a 'url' field ({i})")

        elif isinstance(i, str):
            urls.append(i)

        else:
            raise TypeError()

    out = []
    for i in sorted_list_of_cleaned_urls(urls):
        if i in urls_with_licenses:
            out.append(urls_with_licenses[i])
        else:
            out.append({"url": i, "license": "?"})
    return out


@dataclass
class ResourceListing:
    """
    Class to make listings easier to work with
    """

    # For compatibility, all these repo must have data in the README
    github_readme_listings: list[_type_listing_entry] = field(default_factory=list)

    # For compatibility, all these repo must have data in the README
    gitlab_readme_listings: list[_type_listing_entry] = field(default_factory=list)

    # For where the links must be given as hrefs in "a" tags
    webpage_html: list[_type_listing_entry] = field(default_factory=list)

    # For the websites to be scraped fully
    website: list[_type_listing_entry] = field(default_factory=list)

    # Faults
    fault_urls: list[_type_listing_entry] = field(default_factory=list)
    fault_invalid_urls: list[_type_listing_entry] = field(default_factory=list)

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
        self.github_readme_listings = _flexible_sorted_list_of_targets(
            self.github_readme_listings
        )
        self.gitlab_readme_listings = _flexible_sorted_list_of_targets(
            self.gitlab_readme_listings
        )
        self.webpage_html = _flexible_sorted_list_of_targets(self.webpage_html)
        self.fault_urls = _flexible_sorted_list_of_targets(self.fault_urls)
        self.fault_invalid_urls = _flexible_sorted_list_of_targets(
            self.fault_invalid_urls
        )

    def all_targets(self) -> list[dict[str, str]]:
        return (
            self.fault_invalid_urls
            + self.fault_urls
            + self.webpage_html
            + self.github_readme_listings
            + self.gitlab_readme_listings
        )

    def targets_by_license(self) -> dict[list[str, Any]]:
        r_by_license = dict()
        for res in self.all_targets():
            i = res["license"]
            if i not in r_by_license:
                r_by_license[i] = []

            r_by_license[i].append(res["url"])
        return r_by_license

    @staticmethod
    def from_toml(toml_file_path: str) -> "ResourceListing":
        if not toml_file_path.endswith(".toml"):
            raise ValueError("Input must be a TOML file")

        with open(toml_file_path, "rb") as f:
            x = tomllib.load(f)

        return ResourceListing(
            github_readme_listings=x.get("github_hosted", {}).get(
                "readme_listings", []
            ),
            gitlab_readme_listings=x.get("gitlab_hosted", {}).get(
                "readme_listings", []
            ),
            webpage_html=x.get("webpages", {}).get("html", []),
            website=x.get("websites", {}).get("html", []),
            fault_urls=x.get("faults", {}).get("urls", []),
            fault_invalid_urls=x.get("faults", {}).get("invalid_urls", []),
        )

    @staticmethod
    def from_json(json_file_path: str) -> "ResourceListing":
        if not json_file_path.endswith(".json"):
            raise ValueError("Input must be a JSON file")

        with open(json_file_path, "r") as f:
            x = json.load(f)

        return ResourceListing(
            github_readme_listings=x.get("github_hosted", {}).get(
                "readme_listings", []
            ),
            gitlab_readme_listings=x.get("gitlab_hosted", {}).get(
                "readme_listings", []
            ),
            webpage_html=x.get("webpages", {}).get("html", []),
            website=x.get("websites", {}).get("html", []),
            fault_urls=x.get("faults", {}).get("urls", []),
            fault_invalid_urls=x.get("faults", {}).get("invalid_urls", []),
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
            "websites": {
                "html": self.website,
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

    def to_json(self, json_file_path: str) -> None:
        if not json_file_path.endswith(".json"):
            raise ValueError("Output must be a JSON file")

        # Outputting to a new JSON
        json_ready_dict = {
            "github_hosted": {
                "readme_listings": self.github_readme_listings,
            },
            "gitlab_hosted": {
                "readme_listings": self.gitlab_readme_listings,
            },
            "webpages": {
                "html": self.webpage_html,
            },
            "websites": {
                "html": self.website,
            },
            "faults": {
                "urls": self.fault_urls,
                "invalid_urls": self.fault_invalid_urls,
            },
        }

        with open(json_file_path, "w") as fp:
            json.dump(json_ready_dict, fp, indent=4, sort_keys=True)

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.concat(
            [
                pd.DataFrame(data=self.github_readme_listings),
                pd.DataFrame(data=self.gitlab_readme_listings),
                pd.DataFrame(data=self.webpage_html),
            ]
        )
        return df

    def fetch_all_licenses(self, force_update: bool = False) -> None:
        from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
        from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper

        gitlab_s = GitlabScraper()
        github_s = GithubScraper()

        def _f_license_missing(i):
            return i.get("license") in ["?", None] or (i.get("license_url") is None)

        for i in self.github_readme_listings:
            if isinstance(i, dict):
                if force_update or _f_license_missing(i):
                    try:
                        x = github_s.fetch_project_details(i["url"])
                        if x.license:
                            i["license"] = x.license
                        if x.license_url:
                            i["license_url"] = x.license_url
                    except Exception:
                        pass

        for i in self.gitlab_readme_listings:
            if isinstance(i, dict):
                if force_update or _f_license_missing(i):
                    try:
                        x = gitlab_s.fetch_project_details(i["url"])
                        if x.license:
                            i["license"] = x.license
                        if x.license_url:
                            i["license_url"] = x.license_url
                    except Exception:
                        pass

    def fetch_all_target_counts(self, force_update: bool = False) -> None:
        from oss4climate.src.parsers import listings

        def f_get_target_counts(
            i, listing_type: listings.EnumListingType
        ) -> int | ModuleNotFoundError:
            if force_update or (i.get("target_count") is None):
                try:
                    out = len(
                        listings.parse_listing(
                            i["url"],
                            listing_type=listing_type,
                        )
                    )
                except Exception:
                    out = None
            else:
                out = i.get("target_count")
            return out

        for i in self.github_readme_listings:
            if isinstance(i, dict):
                x = f_get_target_counts(
                    i,
                    listing_type=listings.EnumListingType.GITHUB,
                )
                if x:
                    i["target_count"] = x

        for i in self.gitlab_readme_listings:
            if isinstance(i, dict):
                x = f_get_target_counts(
                    i,
                    listing_type=listings.EnumListingType.GITLAB,
                )
                if x:
                    i["target_count"] = x

        for i in self.webpage_html:
            if isinstance(i, dict):
                x = f_get_target_counts(
                    i,
                    listing_type=listings.EnumListingType.HTML,
                )
                if x:
                    i["target_count"] = x


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

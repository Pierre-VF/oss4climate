"""
Module parsing https://github.com/github/GreenSoftwareDirectory
"""

from datetime import timedelta
from enum import Enum

from oss4climate.src.log import log_warning
from oss4climate.src.models import EnumDocumentationFileType
from oss4climate.src.parsers import (
    ParsingTargets,
    ResourceListing,
)
from oss4climate.src.parsers import (
    fetch_all_project_urls_from_html_webpage as __fetch_from_webpage,
)
from oss4climate.src.parsers import (
    fetch_all_project_urls_from_markdown_str as __fetch_from_markdown_str,
)
from oss4climate.src.parsers import (
    fetch_all_project_urls_from_rst_str as __fetch_from_rst_str,
)
from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper


def _parse_readme(readme: str, readme_type: EnumDocumentationFileType) -> str | None:
    if readme_type == EnumDocumentationFileType.MARKDOWN:
        return __fetch_from_markdown_str(readme)
    elif readme_type == EnumDocumentationFileType.RESTRUCTURED_TEXT:
        return __fetch_from_rst_str(readme)
    elif readme_type == EnumDocumentationFileType.HTML:
        return __fetch_from_webpage(readme)
    else:
        return None


def _flexible_url_parse(i: str | dict[str, str]) -> str:
    if isinstance(i, str):
        out = i
    elif isinstance(i, dict) and "url" in i:
        out = i["url"]
    else:
        raise ValueError(f"Unable to parse {i}")
    return out


class EnumListingType(Enum):
    GITLAB = "GITLAB"
    GITHUB = "GITHUB"
    HTML = "HTML"


def parse_listing(
    url: str | dict,
    listing_type: EnumListingType,
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    i = _flexible_url_parse(url)
    if listing_type == EnumListingType.GITHUB:
        readme_i, readme_type_i = GithubScraper(
            cache_lifetime=cache_lifetime
        ).fetch_repository_readme(i)
        out = _parse_readme(readme_i, readme_type_i)
    elif listing_type == EnumListingType.GITLAB:
        readme_i, readme_type_i = GitlabScraper(
            cache_lifetime=cache_lifetime
        ).fetch_repository_readme(i)
        out = _parse_readme(readme_i, readme_type_i)
    elif listing_type == EnumListingType.HTML:
        out = __fetch_from_webpage(i, cache_lifetime=cache_lifetime)
    else:
        raise ValueError(f"Unsupported listing type ({listing_type})")
    if out is None:
        return ParsingTargets()
    else:
        return out


def fetch_all(
    listings_file: str,
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    """
    Fetches data for all of the listings in a TOML file

    :return: sum of all listings targets (sorted and unique)
    """
    if listings_file.endswith(".toml"):
        listing = ResourceListing.from_toml(listings_file)
    elif listings_file.endswith(".json"):
        listing = ResourceListing.from_json(listings_file)
    else:
        raise ValueError(f"Only supporting TOML and JSON files (not {listings_file})")

    res = ParsingTargets()
    failed_github_readme_listings = []
    failed_gitlab_readme_listings = []
    failed_webpage_listings = []
    for i in listing.github_readme_listings:
        try:
            res += parse_listing(
                i, listing_type=EnumListingType.GITHUB, cache_lifetime=cache_lifetime
            )
        except Exception as e:
            log_warning(f"Failed fetching listing README from {i} (details: {e})")
            failed_github_readme_listings.append(i)

    for i in listing.gitlab_readme_listings:
        try:
            res += parse_listing(
                i, listing_type=EnumListingType.GITLAB, cache_lifetime=cache_lifetime
            )
        except Exception as e:
            log_warning(f"Failed fetching listing README from {i} (details: {e})")
            failed_gitlab_readme_listings.append(i)

    for i in listing.webpage_html:
        try:
            res += parse_listing(
                i, listing_type=EnumListingType.HTML, cache_lifetime=cache_lifetime
            )
        except Exception as e:
            log_warning(f"Failed fetching listing webpage from {i} (details: {e})")
            failed_webpage_listings.append(i)

    # Marking the invalid listings input for tracing
    res += ParsingTargets(
        unknown=[_flexible_url_parse(i) for i in listing.fault_urls],
        invalid=[
            _flexible_url_parse(i)
            for i in (
                listing.fault_invalid_urls
                + failed_github_readme_listings
                + failed_gitlab_readme_listings
                + failed_webpage_listings
            )
        ],
    )

    res.ensure_sorted_cleaned_and_unique_elements()
    return res

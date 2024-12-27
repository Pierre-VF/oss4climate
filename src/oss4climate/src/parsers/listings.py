"""
Module parsing https://github.com/github/GreenSoftwareDirectory
"""

from datetime import timedelta

from oss4climate.src.log import log_warning
from oss4climate.src.model import EnumDocumentationFileType
from oss4climate.src.parsers import (
    ParsingTargets,
    ResourceListing,
    github_data_io,
    gitlab_data_io,
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


def fetch_all(
    listings_toml_file: str,
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    """
    Fetches data for all of the listings in a TOML file

    :return: sum of all listings targets (sorted and unique)
    """
    listing = ResourceListing.from_toml(listings_toml_file)

    res = ParsingTargets()
    failed_github_readme_listings = []
    failed_gitlab_readme_listings = []
    failed_webpage_listings = []
    for i in listing.github_readme_listings:
        i = _flexible_url_parse(i)
        try:
            readme_i, readme_type_i = github_data_io.fetch_repository_readme(
                i, cache_lifetime=cache_lifetime
            )
            r_i = _parse_readme(readme_i, readme_type_i)
            if r_i is not None:
                res += r_i
        except Exception:
            log_warning(f"Failed fetching listing README from {i}")
            failed_github_readme_listings.append(i)

    for i in listing.gitlab_readme_listings:
        i = _flexible_url_parse(i)
        try:
            readme_i, readme_type_i = gitlab_data_io.fetch_repository_readme(
                i, cache_lifetime=cache_lifetime
            )
            r_i = _parse_readme(readme_i, readme_type_i)
            if r_i is not None:
                res += r_i
        except Exception:
            log_warning(f"Failed fetching listing README from {i}")
            failed_gitlab_readme_listings.append(i)

    for i in listing.webpage_html:
        i = _flexible_url_parse(i)
        try:
            res += __fetch_from_webpage(i, cache_lifetime=cache_lifetime)
        except Exception:
            log_warning(f"Failed fetching listing webpage from {i}")
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

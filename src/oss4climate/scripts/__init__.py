"""
Module containing methods to be run in scripts
"""

import os
from datetime import timedelta

from oss4climate.src.config import (
    FILE_INPUT_INDEX,
    FILE_INPUT_LISTINGS_INDEX,
    FILE_OUTPUT_SUMMARY_TOML,
)
from oss4climate.src.log import log_info
from oss4climate.src.parsers import (
    ParsingTargets,
    ResourceListing,
    github_data_io,
    identify_parsing_targets,
    listings,
)
from oss4climate.src.parsers.lfenergy import (
    fetch_all_project_urls_from_lfe_webpage,
    fetch_project_github_urls_from_lfe_energy_project_webpage,
    get_open_source_energy_projects_from_landscape,
)
from oss4climate.src.parsers.opensustain_tech import (
    fetch_all_project_urls_from_opensustain_webpage,
    fetch_listing_of_listings_from_opensustain_webpage,
)


def format_individual_file(file_path: str) -> None:
    os.system(f"black {file_path}")


def format_all_files():
    format_individual_file(FILE_INPUT_INDEX)
    format_individual_file(FILE_INPUT_LISTINGS_INDEX)
    format_individual_file(FILE_OUTPUT_SUMMARY_TOML)


def _add_projects_to_listing_file(
    parsing_targets: ParsingTargets,
    file_path: str = FILE_INPUT_INDEX,
) -> None:
    log_info(f"Adding projects to {file_path}")
    existing_targets = ParsingTargets.from_toml(file_path)
    new_targets = existing_targets + parsing_targets

    # Cleaning Github repositories links
    new_targets.github_repositories = [
        github_data_io.clean_github_repository_url(i)
        for i in new_targets.github_repositories
    ]

    # Ensuring uniqueness in new targets and cleaning up redundancies
    new_targets.cleanup()

    # Outputting to a new TOML
    log_info(f"Exporting new index to {file_path}")
    new_targets.to_toml(file_path)

    # Format the file for human readability
    format_individual_file(file_path)


def discover_projects(
    file_path: str = FILE_INPUT_INDEX,
    listings_file_path: str = FILE_INPUT_LISTINGS_INDEX,
    cache_lifetime: timedelta | None = None,
):
    log_info("Indexing LF Energy projects")

    # From webpage
    new_targets = ParsingTargets()
    dropped_urls = []
    rs0 = fetch_all_project_urls_from_lfe_webpage(cache_lifetime=cache_lifetime)
    for r in rs0:
        new_targets += fetch_project_github_urls_from_lfe_energy_project_webpage(
            r, cache_lifetime=cache_lifetime
        )

    # From landscape
    new_targets += get_open_source_energy_projects_from_landscape(
        cache_lifetime=cache_lifetime
    )

    # Adding from OpenSustainTech
    new_targets += fetch_all_project_urls_from_opensustain_webpage(
        cache_lifetime=cache_lifetime
    )

    # From different listings
    new_targets += listings.fetch_all(listings_file_path, cache_lifetime=cache_lifetime)

    [log_info(f"DROPPING {i} (target is unclear)") for i in dropped_urls]

    _add_projects_to_listing_file(
        new_targets,
        file_path=file_path,
    )
    log_info("Done!")


def add_projects_to_listing(
    project_urls: list[str],
    file_path: str = FILE_INPUT_INDEX,
) -> None:
    """Adds projects from a list into the index file

    :param project_urls: list of URLs to be added
    :param file_path: TOML file link to be updated, defaults to FILE_INPUT_INDEX
    """
    # Splitting URLs into targets
    new_targets = identify_parsing_targets(project_urls)

    _add_projects_to_listing_file(
        new_targets,
        file_path=file_path,
    )
    log_info("Done!")


def update_listing_of_listings(
    target_output_file: str = FILE_INPUT_LISTINGS_INDEX,
) -> None:
    list_of_listings = ResourceListing.from_toml(FILE_INPUT_LISTINGS_INDEX)

    # Add data from listings of listings
    listings_open_sustain = fetch_listing_of_listings_from_opensustain_webpage()

    list_of_listings += listings_open_sustain
    list_of_listings.ensure_sorted_cleaned_and_unique_elements()

    # Fetch licenses
    list_of_listings.fetch_all_licenses()
    list_of_listings.fetch_all_target_counts()

    list_of_listings.to_toml(target_output_file)

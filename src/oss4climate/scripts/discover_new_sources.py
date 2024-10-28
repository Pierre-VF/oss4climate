"""
This module contains methods to discover new sources of code
"""

import os

from tqdm import tqdm

from oss4climate.scripts import (
    FILE_INPUT_INDEX,
    FILE_OUTPUT_LISTING_FEATHER,
    log_info,
)
from oss4climate.src.nlp.search import SearchResults
from oss4climate.src.parsers import (
    ParsingTargets,
    fetch_all_project_urls_from_markdown_str,
)
from oss4climate.src.parsers.github_data_io import extract_repository_organisation


def discover_repositories_in_existing_organisations(output_file: str) -> None:
    log_info("Loading organisations and repositories to be indexed")
    targets = ParsingTargets.from_toml(FILE_INPUT_INDEX)

    # Extract organisation to screen for new repositories
    orgs = [extract_repository_organisation(i) for i in targets.github_repositories]

    extended_targets = ParsingTargets(
        github_organisations=orgs,
    )

    # Cleaning up and exporting to TOML file
    log_info("Cleaning up targets")
    extended_targets.cleanup()
    log_info(f"Exporting to {output_file}")
    extended_targets.to_toml(output_file)


def discover_repositories_in_existing_readmes(output_file: str) -> None:
    log_info("Searching for relevant resource URLs in READMEs of known repositories")
    if not os.path.exists(FILE_OUTPUT_LISTING_FEATHER):
        raise RuntimeError(
            "The dataset is not available locally - make sure to download it prior to running this"
        )

    dfs = SearchResults(FILE_OUTPUT_LISTING_FEATHER).documents

    full_targets = ParsingTargets.from_toml(FILE_INPUT_INDEX)
    for i, r in tqdm(dfs.iterrows()):
        try:
            if isinstance(r["readme"], str):
                full_targets += fetch_all_project_urls_from_markdown_str(r["readme"])
        except Exception as e:
            print(f"Error with {r} // e={e}")

    def _url_cleanup(x: str) -> str:
        x = x.split("?")[0]
        x = x.split("#")[0]
        if x.endswith("/"):
            x = x[:-1]
        return x

    def _url_qualifies(x: str) -> bool:
        if x.startswith("https://github.com/"):
            if (
                x.startswith("https://github.com/settings/")
                or x.startswith("https://github.com/user-attachments/")
                or x.startswith("https://github.com/sponsors/")
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

    # Removing problematic resources
    full_targets.github_organisations = [
        i for i in full_targets.github_organisations if "?" not in i
    ]
    full_targets.github_repositories = [
        _url_cleanup(i) for i in full_targets.github_repositories if _url_qualifies(i)
    ]
    full_targets.gitlab_projects = [
        _url_cleanup(i) for i in full_targets.gitlab_projects if _url_qualifies(i)
    ]
    full_targets.unknown = [
        _url_cleanup(i) for i in full_targets.unknown if _url_qualifies(i)
    ]
    full_targets.invalid = [
        _url_cleanup(i) for i in full_targets.invalid if _url_qualifies(i)
    ]

    # Cleaning up and exporting to TOML file
    log_info("Cleaning up targets")
    full_targets.cleanup()
    log_info(f"Exporting to {output_file}")
    full_targets.to_toml(output_file)

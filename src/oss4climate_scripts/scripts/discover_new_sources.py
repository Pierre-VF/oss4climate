"""
This module contains methods to discover new sources of code
"""

import os

from tqdm import tqdm

from oss4climate.src.config import (
    FILE_INPUT_INDEX,
    FILE_OUTPUT_LISTING_FEATHER,
)
from oss4climate.src.log import (
    log_info,
)
from oss4climate.src.models import EnumDocumentationFileType
from oss4climate.src.nlp.search import SearchResults
from oss4climate.src.parsers import (
    ParsingTargets,
    fetch_all_project_urls_from_markdown_str,
    fetch_all_project_urls_from_rst_str,
    url_qualifies,
)
from oss4climate.src.parsers.git_platforms.github_io import GithubScraper


def discover_repositories_in_existing_organisations(output_file: str) -> None:
    log_info("Loading organisations and repositories to be indexed")
    targets = ParsingTargets.from_toml(FILE_INPUT_INDEX)

    # Extract organisation to screen for new repositories
    ghs = GithubScraper()
    orgs = [ghs.extract_repository_organisation(i) for i in targets.github_repositories]

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
                readme_type = r["readme_type"]
                if readme_type == EnumDocumentationFileType.MARKDOWN:
                    full_targets += fetch_all_project_urls_from_markdown_str(
                        r["readme"]
                    )
                elif readme_type == EnumDocumentationFileType.RESTRUCTURED_TEXT:
                    full_targets += fetch_all_project_urls_from_rst_str(r["readme"])
        except Exception as e:
            print(f"Error with {r} // e={e}")

    def _url_cleanup(x: str) -> str:
        x = x.split("?")[0]
        x = x.split("#")[0]
        if x.endswith("/"):
            x = x[:-1]
        return x

    # Removing problematic resources
    full_targets.github_organisations = [
        i for i in full_targets.github_organisations if "?" not in i
    ]
    full_targets.github_repositories = [
        _url_cleanup(i) for i in full_targets.github_repositories if url_qualifies(i)
    ]
    full_targets.gitlab_projects = [
        _url_cleanup(i) for i in full_targets.gitlab_projects if url_qualifies(i)
    ]
    full_targets.unknown = [
        _url_cleanup(i) for i in full_targets.unknown if url_qualifies(i)
    ]
    full_targets.invalid = [
        _url_cleanup(i) for i in full_targets.invalid if url_qualifies(i)
    ]

    # Cleaning up and exporting to TOML file
    log_info("Cleaning up targets")
    full_targets.cleanup()
    log_info(f"Exporting to {output_file}")
    full_targets.to_toml(output_file)

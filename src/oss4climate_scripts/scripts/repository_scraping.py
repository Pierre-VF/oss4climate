"""
Script to run fetching of the data from the repositories.

This module provides the scrape_all function which orchestrates the full
scraping pipeline using the RepositoryScraper class. The scraper:
- Reads the TOML index as the source of truth for which orgs/repos to track
- Stores scraped data in a SQLModel-backed database
- Supports incremental re-scraping based on a refresh interval
- Exports results to feather file, summary TOML, and failures TOML

Warning: unauthenticated users have a rate limit of 60 calls per hour
(source: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28)
"""

from oss4climate_scripts import scripts
from oss4climate_scripts.src.config import (
    FILE_INPUT_INDEX,
    FILE_OUTPUT_DIR,
    FILE_OUTPUT_SUMMARY_TOML,
)


def scrape_all(
    target_output_file: str | None = None,
    fail_on_issue: bool = False,
    refresh_days: int = 28,
) -> None:
    """
    Script to run fetching of the data from the repositories.

    Uses the RepositoryScraper to sync from TOML, scrape active repos,
    and export results to database and files.

    :param target_output_file: name of file to output results to, defaults to FILE_OUTPUT_LISTING_FEATHER
    :param fail_on_issue: if True, raises a failure if encountering an issue
    :param refresh_days: number of days since last scrape before re-scraping (default: 28)
    :raises ValueError: if output file type is not supported (CSV, JSON)
    :return: /
    """
    from oss4climate.src.repository_scraper import RepositoryScraper

    if target_output_file is None:
        # This should only be needed when actually needed (as it's a side feature)
        from oss4climate_app.src.config import (
            FILE_OUTPUT_LISTING_FEATHER,
        )

        target_output_file = FILE_OUTPUT_LISTING_FEATHER

    # Determine binary output path (feather)
    binary_target_output_file = target_output_file
    for i in ["csv", "json"]:
        binary_target_output_file = binary_target_output_file.replace(
            f".{i}", ".feather"
        )

    # Initialize the repository scraper
    scraper = RepositoryScraper(refresh_days=refresh_days)

    # Run the full pipeline
    scraper.run(
        toml_path=FILE_INPUT_INDEX,
        feather_output=binary_target_output_file,
        summary_output=FILE_OUTPUT_SUMMARY_TOML,
        failures_output=f"{FILE_OUTPUT_DIR}/failures_scraping.toml",
    )

    print(
        f"""

    >>> Data was exported to: {target_output_file}

    """
    )

    print(
        f"""

    >>> Types were exported to: {FILE_OUTPUT_SUMMARY_TOML}

    """
    )

    scripts.format_all_files()

    file_failures_toml = f"{FILE_OUTPUT_DIR}/failures_scraping.toml"
    scripts.format_individual_file(file_failures_toml)


if __name__ == "__main__":
    scrape_all()

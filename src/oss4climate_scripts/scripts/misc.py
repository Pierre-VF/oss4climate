from oss4climate.src.config import FILE_INPUT_INDEX
from oss4climate.src.crawler import ParsingTargets, scrape_all_targets
from oss4climate.src.log import log_info
from oss4climate.src.parsers.opensustain_tech import (
    fetch_all_project_urls_from_opensustain_webpage,
    fetch_categorised_projects_from_opensustain_webpage,
)
from oss4climate.src.parsers.website import crawl_website
from oss4climate_scripts.scripts import format_individual_file

if __name__ == "__main__":
    ## -------------------------------------------------------------------------
    # OpenSustain CSV build
    ## -------------------------------------------------------------------------
    if True:
        categorised = fetch_categorised_projects_from_opensustain_webpage()
        all_projs = fetch_all_project_urls_from_opensustain_webpage()

        tgs = ParsingTargets(
            # github_repositories=all_projs.github_repositories[:5],
            # gitlab_projects=all_projs.gitlab_projects[:5],
            codeberg_repositories=all_projs.codeberg_repositories[:2],
            bitbucket_repositories=all_projs.bitbucket_repositories[:2],
        )

        res = scrape_all_targets(tgs)

        print("OK")

    ## -------------------------------------------------------------------------
    # Openmod target identification build
    ## -------------------------------------------------------------------------

    if True:
        log_info("Loading organisations and repositories to be indexed")
        targets = ParsingTargets.from_toml(FILE_INPUT_INDEX)

        new_targets = crawl_website(
            "https://wiki.openmod-initiative.org/", max_pages=20000
        )

        extended_targets = targets + new_targets

        # Cleaning up and exporting to TOML file
        log_info("Cleaning up targets")
        extended_targets.cleanup()
        log_info(f"Exporting to {FILE_INPUT_INDEX}")
        extended_targets.to_toml(FILE_INPUT_INDEX)

        format_individual_file(FILE_INPUT_INDEX)

        print(f"{len(new_targets)} new targets scraped")

        print("Done")

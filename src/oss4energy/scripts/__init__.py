"""
Module containing methods to be run in scripts
"""

import os
from ftplib import FTP

import pandas as pd
import tomllib
from tomlkit import document, dump

from oss4energy.config import SETTINGS
from oss4energy.helpers import sorted_list_of_unique_elements
from oss4energy.log import log_info
from oss4energy.nlp.markdown_io import markdown_to_clean_plaintext
from oss4energy.parsers import ParsingTargets
from oss4energy.parsers.github_data_io import (
    GITHUB_URL_BASE,
    extract_organisation_and_repository_as_url_block,
    fetch_repositories_in_organisation,
    fetch_repository_details,
    fetch_repository_readme,
    split_across_target_sets,
)
from oss4energy.parsers.lfenergy import (
    fetch_all_project_urls_from_lfe_webpage,
    fetch_project_github_urls_from_lfe_energy_project_webpage,
    get_open_source_energy_projects_from_landscape,
)
from oss4energy.parsers.opensustain_tech import (
    fetch_all_project_urls_from_opensustain_webpage,
)

FILE_INPUT_INDEX = "repo_index.toml"
FILE_OUTPUT_LISTING_CSV = ".data/listing_data.csv"
FILE_OUTPUT_SUMMARY_TOML = ".data/summary.toml"


def _format_individual_file(file_path: str) -> None:
    os.system(f"black {file_path}")


def format_files():
    _format_individual_file(FILE_INPUT_INDEX)
    _format_individual_file(FILE_OUTPUT_SUMMARY_TOML)


def _add_projects_to_listing_file(
    parsing_targets: ParsingTargets,
    file_path: str = FILE_INPUT_INDEX,
) -> None:
    log_info(f"Adding projects to {file_path}")
    with open(file_path, "rb") as f:
        repos_from_toml = tomllib.load(f)

    existing_targets = ParsingTargets(
        github_organisations=repos_from_toml["github_hosted"]["organisations"],
        github_repositories=repos_from_toml["github_hosted"]["repositories"],
    )
    new_targets = existing_targets + parsing_targets

    # Cleaning Github repositories links
    new_targets.github_repositories = [
        GITHUB_URL_BASE + extract_organisation_and_repository_as_url_block(i)
        for i in new_targets.github_repositories
    ]

    # Ensuring uniqueness in new targets
    new_targets.ensure_sorted_and_unique_elements()

    # Adding new
    repos_from_toml["github_hosted"]["organisations"] = new_targets.github_organisations
    repos_from_toml["github_hosted"]["repositories"] = new_targets.github_repositories
    repos_from_toml["dropped_targets"]["urls"] = sorted_list_of_unique_elements(
        new_targets.unknown + repos_from_toml["dropped_targets"]["urls"]
    )

    # Outputting to a new TOML
    doc = document()
    for k, v in repos_from_toml.items():
        doc.add(k, v)

    log_info(f"Exporting new index to {file_path}")
    with open(file_path, "w") as fp:
        dump(doc, fp, sort_keys=True)

    # Format the file for human readability
    _format_individual_file(file_path)


def discover_projects(file_path: str = FILE_INPUT_INDEX):
    log_info("Indexing LF Energy projects")

    # From webpage
    new_targets = ParsingTargets()
    dropped_urls = []
    rs0 = fetch_all_project_urls_from_lfe_webpage()
    for r in rs0:
        new_targets += fetch_project_github_urls_from_lfe_energy_project_webpage(r)

    # From landscape
    new_targets += get_open_source_energy_projects_from_landscape()

    # Adding from OpenSustainTech
    new_targets += fetch_all_project_urls_from_opensustain_webpage()

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
    new_targets = split_across_target_sets(project_urls)

    _add_projects_to_listing_file(
        new_targets,
        file_path=file_path,
    )
    log_info("Done!")


def generate_listing(target_output_file: str = FILE_OUTPUT_LISTING_CSV) -> None:
    """
    Script to run fetching of the data from the repositories

    Warning: unauthenticated users have a rate limit of 60 calls per hour
    (source: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28)


    :param target_output_file: name of file to output results to, defaults to FILE_OUTPUT_LISTING_CSV
    :raises ValueError: if output file type is not supported (CSV, JSON)
    :return: /
    """

    log_info("Loading organisations and repositories to be indexed")
    with open(FILE_INPUT_INDEX, "rb") as f:
        repos_from_toml = tomllib.load(f)

    bad_organisations = []
    bad_repositories = []

    targets = ParsingTargets(
        github_organisations=repos_from_toml["github_hosted"]["organisations"],
        github_repositories=repos_from_toml["github_hosted"]["repositories"],
    )
    targets.ensure_sorted_and_unique_elements()

    log_info("Fetching data for all organisations in Github")
    for org_url in targets.github_organisations:
        url2check = org_url.replace("https://", "")
        if url2check.endswith("/"):
            url2check = url2check[:-1]
        if url2check.count("/") > 1:
            log_info(f"SKIPPING repo {org_url}")
            continue  # Skip

        try:
            x = fetch_repositories_in_organisation(org_url)
            [targets.github_repositories.append(i) for i in x.values()]
        except Exception as e:
            print(f" > Error with organisation ({e})")
            bad_organisations.append(org_url)

    log_info("Fetching data for all repositories in Github")
    targets.ensure_sorted_and_unique_elements()  # since elements were added
    screening_results = []
    for i in targets.github_repositories:
        try:
            if i.endswith("/.github"):
                continue
            screening_results.append(fetch_repository_details(i))
        except Exception as e:
            print(f" > Error with repo ({e})")
            bad_repositories.append(i)

    df = pd.DataFrame([i.__dict__ for i in screening_results])
    df.set_index("id", inplace=True)

    def _f_readme(x):
        y = fetch_repository_readme(x)
        return markdown_to_clean_plaintext(y)  # [:1000]

    log_info("Fetching READMEs for all repositories in Github")
    df["readme"] = df["url"].apply(_f_readme)

    df2export = df.drop(columns=["raw_details"])
    if target_output_file.endswith(".csv"):
        output_binary = target_output_file.replace(".csv", ".hdf")
        df2export.to_csv(target_output_file, sep=";")
    elif target_output_file.endswith(".json"):
        output_binary = target_output_file.replace(".csv", ".hdf")
        df2export.T.to_json(target_output_file)
    else:
        raise ValueError(f"Unsupported file type for export: {target_output_file}")

    # Exporting the file to HDF too (faster processing)
    df2export.to_hdf(output_binary)

    print(
        f"""
        
    >>> Data was exported to: {target_output_file}
        
    """
    )

    # Outputting details to a new TOML
    languages = sorted_list_of_unique_elements(df["language"])
    organisations = sorted_list_of_unique_elements(df["organisation"])
    licences = sorted_list_of_unique_elements(df["license"])

    stats = {
        "repositories": len(df),
        "organisations": len(organisations),
    }

    failed = dict(organisations=bad_organisations, repositories=bad_repositories)

    # TOML formatting
    doc = document()
    doc.add("statistics", stats)
    doc.add("failures", failed)
    doc.add("organisations", [str(i) for i in organisations])
    doc.add("language", [str(i) for i in languages])
    doc.add("licences", [str(i) for i in licences])
    log_info(f"Exporting new index to {FILE_OUTPUT_SUMMARY_TOML}")
    with open(FILE_OUTPUT_SUMMARY_TOML, "w") as fp:
        dump(doc, fp, sort_keys=True)

    print(
        f"""
        
    >>> Types were exported to: {FILE_OUTPUT_SUMMARY_TOML}
        
    """
    )
    format_files()


def publish_to_ftp() -> None:
    """Exports data generated to FTP (requires .env to be defined with credentials to the FTP)

    :raises EnvironmentError: when the FTP credentials are not given in environment
    """
    for i in [
        SETTINGS.EXPORT_FTP_URL,
        SETTINGS.EXPORT_FTP_USER,
        SETTINGS.EXPORT_FTP_PASSWORD,
    ]:
        if i is None:
            raise EnvironmentError(
                f"{i.__name__} must be defined for FTP export to work"
            )
        if len(i) == 0:
            raise EnvironmentError(
                f"{i.__name__} must have an adequate value for FTP export to work"
            )
    files_out = [
        FILE_OUTPUT_SUMMARY_TOML,
        FILE_OUTPUT_LISTING_CSV,
    ]

    with FTP(
        host=SETTINGS.EXPORT_FTP_URL,
        user=SETTINGS.EXPORT_FTP_USER,
        passwd=SETTINGS.EXPORT_FTP_PASSWORD,
    ) as ftp:
        try:
            ftp.mkd("oss4energy")
        except:
            pass
        ftp.cwd("oss4energy")
        for i in files_out:
            with open(i, "rb") as fp:
                log_info(f"Uploading {i}")
                ftp.storbinary("STOR %s" % os.path.basename(i), fp, blocksize=1024)

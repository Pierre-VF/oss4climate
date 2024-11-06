import pandas as pd
from tomlkit import document, dump

from oss4climate.scripts import (
    FILE_INPUT_INDEX,
    FILE_OUTPUT_DIR,
    FILE_OUTPUT_LISTING_CSV,
    FILE_OUTPUT_SUMMARY_TOML,
    format_all_files,
    format_individual_file,
)
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.nlp import markdown_io
from oss4climate.src.parsers import (
    ParsingTargets,
    RateLimitError,
    github_data_io,
    gitlab_data_io,
)


def scrape_all(
    target_output_file: str = FILE_OUTPUT_LISTING_CSV,
    fail_on_issue=False,
) -> None:
    """
    Script to run fetching of the data from the repositories

    Warning: unauthenticated users have a rate limit of 60 calls per hour
    (source: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28)


    :param target_output_file: name of file to output results to, defaults to FILE_OUTPUT_LISTING_CSV
    :raises ValueError: if output file type is not supported (CSV, JSON)
    :return: /
    """

    log_info("Loading organisations and repositories to be indexed")
    targets = ParsingTargets.from_toml(FILE_INPUT_INDEX)
    targets.ensure_sorted_and_unique_elements()

    failure_during_scraping = False

    scrape_failures = dict()

    bad_organisations = []
    bad_repositories = []

    log_info("Fetching data for all organisations in Github")
    for org_url in targets.github_organisations:
        url2check = org_url.replace("https://", "")
        if url2check.endswith("/"):
            url2check = url2check[:-1]
        if url2check.count("/") > 1:
            log_info(f"SKIPPING repo {org_url}")
            targets.github_repositories.append(org_url)  # Mapping it to repos instead
            continue  # Skip

        try:
            x = github_data_io.fetch_repositories_in_organisation(org_url)
            [targets.github_repositories.append(i) for i in x.values()]
        except Exception as e:
            scrape_failures["GITHUB_ORGANISATION:" + org_url] = e
            log_warning(f" > Error with organisation ({e})")
            bad_organisations.append(org_url)

    log_info("Fetching data for all groups in Gitlab")
    for org_url in targets.gitlab_groups:
        url2check = org_url.replace("https://", "")
        if url2check.endswith("/"):
            url2check = url2check[:-1]
        if url2check.count("/") > 1:
            log_info(f"SKIPPING repo {org_url}")
            targets.gitlab_projects.append(org_url)  # Mapping it to repos instead
            continue  # Skip

        try:
            x = gitlab_data_io.fetch_repositories_in_group(org_url)
            [targets.gitlab_projects.append(i) for i in x.values()]
        except Exception as e:
            scrape_failures["GITLAB_GROUP:" + org_url] = e
            log_warning(f" > Error with organisation ({e})")
            bad_organisations.append(org_url)

    targets.ensure_sorted_and_unique_elements()  # since elements were added
    screening_results = []

    log_info("Fetching data for all repositories in Gitlab")
    for i in targets.gitlab_projects:
        try:
            screening_results.append(
                gitlab_data_io.fetch_repository_details(i, fail_on_issue=fail_on_issue)
            )
        except Exception as e:
            scrape_failures["GITLAB_PROJECT:" + i] = e
            log_warning(f" > Error with repo ({e})")
            bad_repositories.append(i)

    log_info("Fetching data for all repositories in Github")
    try:
        forbidden_for_api_limit_counter = 0
        for i in targets.github_repositories:
            try:
                if i.endswith("/.github"):
                    continue
                screening_results.append(
                    github_data_io.fetch_repository_details(
                        i, fail_on_issue=fail_on_issue
                    )
                )
            except Exception as e:
                if isinstance(e, RateLimitError):
                    # Ensuring proper breaking on rate limits of the API
                    forbidden_for_api_limit_counter += 1
                    if forbidden_for_api_limit_counter > 10:
                        raise RateLimitError(
                            f"Github rate limiting hit ({forbidden_for_api_limit_counter} errors with 403 status)"
                        )

                scrape_failures["GITHUB_REPO:" + i] = e
                log_warning(f" > Error with repo ({e})")
                bad_repositories.append(i)
    except RateLimitError as e:
        failure_during_scraping = True
        scrape_failures["SCRAPING"] = e
        log_warning("Rate limit hit for Github - STOPPING Github scraping")

    df = pd.DataFrame([i.__dict__ for i in screening_results])
    df2export = df.set_index("id").drop(columns=["raw_details"])

    # Cleaning up markdown
    def _f_readme_cleanup(x):
        return markdown_io.markdown_to_clean_plaintext(
            x, remove_code=True, remove_linebreaks=True
        )

    df2export["readme"] = df2export["readme"].apply(_f_readme_cleanup)

    if target_output_file.endswith(".csv"):
        # Dropping READMEs for CSV to look reasonable
        df.drop(columns=["readme"]).to_csv(target_output_file, sep=";")
    elif target_output_file.endswith(".json"):
        df2export.T.to_json(target_output_file)
    else:
        raise ValueError(f"Unsupported file type for export: {target_output_file}")

    # Exporting the file to Feather too (faster processing)
    binary_target_output_file = target_output_file
    for i in ["csv", "json"]:
        binary_target_output_file = binary_target_output_file.replace(
            f".{i}", ".feather"
        )
    df2export.reset_index().to_feather(binary_target_output_file)

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
    format_all_files()

    file_failures_toml = f"{FILE_OUTPUT_DIR}/failures_scraping.toml"
    scrape_failures_as_jsonable_dict = {
        str(k): str(v) for k, v in scrape_failures.items()
    }
    doc_failures = document()
    doc_failures.add("failures", scrape_failures_as_jsonable_dict)
    log_info(f"Exporting failures to {file_failures_toml}")
    with open(file_failures_toml, "w") as fp:
        dump(doc_failures, fp, sort_keys=True)
    format_individual_file(file_failures_toml)

    if failure_during_scraping:
        log_warning("Failure(s) happened during the scraping!")

    log_info("Done")

import pandas as pd
from tomlkit import document, dump

from oss4climate import scripts
from oss4climate.src.config import (
    FILE_INPUT_INDEX,
    FILE_OUTPUT_DIR,
    FILE_OUTPUT_LISTING_CSV,
    FILE_OUTPUT_LISTING_FEATHER,
    FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
    FILE_OUTPUT_SUMMARY_TOML,
)
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.model import EnumDocumentationFileType
from oss4climate.src.nlp import html_io, markdown_io, rst_io
from oss4climate.src.nlp.plaintext import (
    get_spacy_english_model,
    reduce_to_informative_lemmas,
)
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
    targets.ensure_sorted_cleaned_and_unique_elements()

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

    targets.ensure_sorted_cleaned_and_unique_elements()  # since elements were added
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

    def _f_fix(x):
        out = x.__dict__
        if isinstance(out["readme_type"], EnumDocumentationFileType):
            out["readme_type"] = out["readme_type"].value
        else:
            out["readme_type"] = str(out["readme_type"])

        return out

    df = pd.DataFrame([_f_fix(i) for i in screening_results])
    df2export = df.set_index("id").drop(columns=["raw_details"])

    # Cleaning up markdown
    def _f_readme_cleanup(r):
        x = r["readme"]
        if x is None:
            return "(NO DATA)"
        elif not isinstance(x, str):
            return "(INVALID)"
        x_type = r["readme_type"]
        if x_type == EnumDocumentationFileType.MARKDOWN.value:
            out = markdown_io.markdown_to_search_plaintext(
                x,
                remove_code=True,
            )
        elif x_type == EnumDocumentationFileType.HTML.value:
            out = html_io.html_to_search_plaintext(
                x,
                remove_code=True,
            )
        elif x_type == EnumDocumentationFileType.RESTRUCTURED_TEXT.value:
            try:
                out = rst_io.rst_to_search_plaintext(
                    x,
                    remove_code=True,
                )
            except rst_io.RstParsingError as e:
                scrape_failures[f"RST_PARSING:{r['url']}"] = e
                # This is to avoid issues if the text is not markdown
                out = x
        else:
            # This is to avoid issues if the text is not markdown
            out = x
        return out

    df2export["readme"] = df2export.apply(_f_readme_cleanup, axis=1)

    # Dropping duplicates, if any
    df2export.drop_duplicates(subset=["url"], inplace=True)

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
    scripts.format_all_files()

    file_failures_toml = f"{FILE_OUTPUT_DIR}/failures_scraping.toml"
    scrape_failures_as_jsonable_dict = {
        str(k): str(v) for k, v in scrape_failures.items()
    }
    doc_failures = document()
    doc_failures.add("failures", scrape_failures_as_jsonable_dict)
    log_info(f"Exporting failures to {file_failures_toml}")
    with open(file_failures_toml, "w") as fp:
        dump(doc_failures, fp, sort_keys=True)
    scripts.format_individual_file(file_failures_toml)

    if failure_during_scraping:
        log_warning("Failure(s) happened during the scraping!")

    log_info("Done")


def optimise_scraped_data_for_search():
    log_info("Loading spaCy english model")
    nlp_model = get_spacy_english_model()
    log_info("- Loaded")

    log_info("Loading input listing")
    df = pd.read_feather(FILE_OUTPUT_LISTING_FEATHER)
    log_info("- Loaded")

    df_opt = df.copy()

    def _f_opt(x: str | None) -> str | None:
        if x is None:
            return None
        try:
            out = " ".join(reduce_to_informative_lemmas(x, nlp_model=nlp_model))
        except Exception as e:
            log_warning(f"Lemmatisation error: {e}")
            out = "(OPTIMISATION ERROR)"
        return out

    log_info("Optimising descriptions")
    df_opt["optimised_description"] = df_opt["description"].apply(_f_opt)
    log_info("Optimising readmes")
    df_opt["optimised_readme"] = df_opt["readme"].apply(_f_opt)

    log_info("Exporting input listing")
    df_opt.to_feather(FILE_OUTPUT_OPTIMISED_LISTING_FEATHER)
    log_info("- Exported")


if __name__ == "__main__":
    scrape_all()

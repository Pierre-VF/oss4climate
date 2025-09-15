import pandas as pd
from tomlkit import document, dump

from oss4climate.src.config import (
    FILE_INPUT_INDEX,
    FILE_OUTPUT_DIR,
    FILE_OUTPUT_LISTING_CSV,
    FILE_OUTPUT_LISTING_FEATHER,
    FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
    FILE_OUTPUT_SUMMARY_TOML,
)
from oss4climate.src.crawler import scrape_all_targets
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.nlp.plaintext import (
    get_spacy_english_model,
    reduce_to_informative_lemmas,
)
from oss4climate.src.parsers import (
    ParsingTargets,
)
from oss4climate_scripts import scripts


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

    scrape_result = scrape_all_targets(
        targets=targets,
        fail_on_issue=fail_on_issue,
    )
    df = scrape_result.results_as_df
    scrape_failures = scrape_result.errors

    failure_during_scraping = len(scrape_failures) > 1

    if target_output_file.endswith(".csv"):
        # Dropping READMEs for CSV to look reasonable
        df.drop(columns=["readme"]).to_csv(target_output_file, sep=";")
    elif target_output_file.endswith(".json"):
        df.T.to_json(target_output_file)
    else:
        raise ValueError(f"Unsupported file type for export: {target_output_file}")

    # Exporting the file to Feather too (faster processing)
    binary_target_output_file = target_output_file
    for i in ["csv", "json"]:
        binary_target_output_file = binary_target_output_file.replace(
            f".{i}", ".feather"
        )
    df.reset_index().to_feather(binary_target_output_file)

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

    failed = dict(
        organisations=scrape_result.failing_organisations,
        repositories=scrape_result.failing_repositories,
    )

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

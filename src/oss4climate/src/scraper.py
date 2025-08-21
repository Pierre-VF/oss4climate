"""
Module taking care of scraping a set of targets
"""

from dataclasses import dataclass

import pandas as pd

from oss4climate.src.log import log_info, log_warning
from oss4climate.src.models import EnumDocumentationFileType
from oss4climate.src.nlp import html_io, markdown_io, rst_io
from oss4climate.src.parsers import (
    ParsingTargets,
    RateLimitError,
)
from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper


@dataclass
class ScrapeResult:
    targets: ParsingTargets
    results_as_df: pd.DataFrame
    errors: dict
    failing_organisations: list[str]
    failing_repositories: list[str]


def scrape_all_targets(
    targets: ParsingTargets,
    fail_on_issue: bool = False,
) -> ScrapeResult:
    """
    Script to run fetching of the data from the repositories

    Warning: unauthenticated users have a rate limit of 60 calls per hour
    (source: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28)


    :param targets: set of ParsingTargets to run through
    :param fail_on_issue: if True, raises a failure if enountering an issue
    :raises ValueError: if output file type is not supported (CSV, JSON)
    :return: ScrapeResult containing all results
    """

    targets.ensure_sorted_cleaned_and_unique_elements()

    scrape_failures = dict()

    bad_organisations = []
    bad_repositories = []

    gitlab_s = GitlabScraper()
    github_s = GithubScraper()

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
            x = github_s.fetch_repositories_in_organisation(org_url)
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
            x = gitlab_s.fetch_repositories_in_group(org_url)
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
                gitlab_s.fetch_project_details(i, fail_on_issue=fail_on_issue)
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
                    github_s.fetch_project_details(i, fail_on_issue=fail_on_issue)
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

    return ScrapeResult(
        targets=targets,
        results_as_df=df2export,
        errors=scrape_failures,
        failing_organisations=bad_organisations,
        failing_repositories=bad_repositories,
    )

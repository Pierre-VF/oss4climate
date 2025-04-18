from oss4climate.src.parsers import ParsingTargets
from oss4climate.src.parsers.github_data_io import (
    ProjectDetails,
    fetch_repositories_in_organisation,
    fetch_repository_details,
)


def test_parsing_target_set(
    github_repo_url,
    github_repo_url_2,
    github_organisation_url,
    github_organisation_url_2,
    unknown_url,
    unknown_url_2,
):
    a = ParsingTargets(
        github_organisations=[github_organisation_url],
        github_repositories=[github_repo_url],
        unknown=[unknown_url],
    )
    b = ParsingTargets(
        github_organisations=[github_organisation_url_2],
        github_repositories=[github_repo_url_2],
        unknown=[unknown_url_2],
    )
    # Testing + operator
    c = a + b
    assert c.github_organisations == [
        github_organisation_url,
        github_organisation_url_2,
    ]
    assert c.github_repositories == [github_repo_url, github_repo_url_2]
    assert c.unknown == [unknown_url, unknown_url_2]

    # Testing += operator
    a += b
    assert a.github_organisations == [
        github_organisation_url,
        github_organisation_url_2,
    ]
    assert a.github_repositories == [github_repo_url, github_repo_url_2]
    assert a.unknown == [unknown_url, unknown_url_2]

    # Testing cleanup of redundancies
    x = ParsingTargets(
        github_organisations=[github_organisation_url, github_organisation_url_2],
        github_repositories=[github_repo_url, github_repo_url_2],
        unknown=[unknown_url_2, unknown_url],
    )
    x += x
    x.ensure_sorted_cleaned_and_unique_elements()
    assert x.github_organisations == [
        github_organisation_url,
        github_organisation_url_2,
    ]
    assert x.github_repositories == [github_repo_url, github_repo_url_2]
    assert x.unknown == [unknown_url, unknown_url_2]


def test_fetch_functions(github_repo_url, github_organisation_url):
    res_repo = fetch_repository_details(github_repo_url)
    assert isinstance(res_repo, ProjectDetails)

    res_org = fetch_repositories_in_organisation(github_organisation_url)
    assert isinstance(res_org, dict)

    print("ok")

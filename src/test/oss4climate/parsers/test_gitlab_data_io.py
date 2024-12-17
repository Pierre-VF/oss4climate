from oss4climate.src.parsers import ParsingTargets
from oss4climate.src.parsers.gitlab_data_io import (
    ProjectDetails,
    fetch_repositories_in_group,
    fetch_repository_details,
)


def test_parsing_target_set():
    a = ParsingTargets(
        github_organisations=["org1"],
        github_repositories=["repo1"],
        unknown=["u1"],
    )
    b = ParsingTargets(
        github_organisations=["org2"],
        github_repositories=["repo2"],
        unknown=["u2"],
    )
    # Testing + operator
    c = a + b
    assert c.github_organisations == ["org1", "org2"]
    assert c.github_repositories == ["repo1", "repo2"]
    assert c.unknown == ["u1", "u2"]

    # Testing += operator
    a += b
    assert a.github_organisations == ["org1", "org2"]
    assert a.github_repositories == ["repo1", "repo2"]
    assert a.unknown == ["u1", "u2"]

    # Testing cleanup of redundancies
    x = ParsingTargets(
        github_organisations=["2", "1"],
        github_repositories=["4", "3"],
        unknown=["6", "5"],
    )
    x += x
    x.ensure_sorted_cleaned_and_unique_elements()
    assert x.github_organisations == ["1", "2"]
    assert x.github_repositories == ["3", "4"]
    assert x.unknown == ["5", "6"]


def test_fetch_functions(gitlab_repo_url, gitlab_group_url):
    res_repo = fetch_repository_details(gitlab_repo_url)
    assert isinstance(res_repo, ProjectDetails)

    res_org = fetch_repositories_in_group(gitlab_group_url)
    assert isinstance(res_org, dict)

    print("ok")

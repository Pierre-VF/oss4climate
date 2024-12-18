from oss4climate.src.parsers import ParsingTargets
from oss4climate.src.parsers.gitlab_data_io import (
    ProjectDetails,
    fetch_repositories_in_group,
    fetch_repository_details,
)


def test_parsing_target_set(
    gitlab_repo_url,
    gitlab_repo_url_2,
    gitlab_group_url,
    gitlab_group_url_2,
    unknown_url,
    unknown_url_2,
):
    a = ParsingTargets(
        github_organisations=[gitlab_group_url],
        github_repositories=[gitlab_repo_url],
        unknown=[unknown_url],
    )
    b = ParsingTargets(
        github_organisations=[gitlab_group_url_2],
        github_repositories=[gitlab_repo_url_2],
        unknown=[unknown_url_2],
    )
    # Testing + operator
    c = a + b
    assert c.github_organisations == [
        gitlab_group_url,
        gitlab_group_url_2,
    ]
    assert c.github_repositories == [gitlab_repo_url, gitlab_repo_url_2]
    assert c.unknown == [unknown_url, unknown_url_2]

    # Testing += operator
    a += b
    assert a.github_organisations == [
        gitlab_group_url,
        gitlab_group_url_2,
    ]
    assert a.github_repositories == [gitlab_repo_url, gitlab_repo_url_2]
    assert a.unknown == [unknown_url, unknown_url_2]

    # Testing cleanup of redundancies
    x = ParsingTargets(
        github_organisations=[gitlab_group_url_2, gitlab_group_url],
        github_repositories=[gitlab_repo_url_2, gitlab_repo_url],
        unknown=[unknown_url_2, unknown_url],
    )
    x += x
    x.ensure_sorted_cleaned_and_unique_elements()
    assert x.github_organisations == [
        gitlab_group_url,
        gitlab_group_url_2,
    ]
    assert x.github_repositories == [gitlab_repo_url, gitlab_repo_url_2]
    assert x.unknown == [unknown_url, unknown_url_2]


def test_fetch_functions(gitlab_repo_url, gitlab_group_url):
    res_repo = fetch_repository_details(gitlab_repo_url)
    assert isinstance(res_repo, ProjectDetails)

    res_org = fetch_repositories_in_group(gitlab_group_url)
    assert isinstance(res_org, dict)

    print("ok")

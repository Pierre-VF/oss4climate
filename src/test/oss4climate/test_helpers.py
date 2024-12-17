from oss4climate.src.helpers import (
    cleaned_url,
    sorted_list_of_unique_elements,
    url_base_matches_domain,
)


def test_f(github_repo_url):
    assert url_base_matches_domain(github_repo_url, "github.com")

    assert cleaned_url(github_repo_url + "#content") == github_repo_url

    # Ensuring robustness against spaces
    assert cleaned_url(github_repo_url + " abc#content") == github_repo_url

    assert sorted_list_of_unique_elements([2, 1, 2, 4, 3, 4]) == [1, 2, 3, 4]

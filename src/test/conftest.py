import pytest


# Github fixtures
@pytest.fixture
def github_repo_url() -> str:
    return "https://github.com/Pierre-VF/oss4climate"


@pytest.fixture
def github_repo_url_2() -> str:
    return "https://github.com/Pierre-VF/oss4climate2"


@pytest.fixture
def github_organisation_url() -> str:
    return "https://github.com/carbon-data-specification"


@pytest.fixture
def github_organisation_url_2() -> str:
    return "https://github.com/carbon-data-specification2"


# Gitlab fixtures
@pytest.fixture
def gitlab_repo_url() -> str:
    return "https://gitlab.com/polito-edyce-prelude/predyce"


@pytest.fixture
def gitlab_repo_url_2() -> str:
    return "https://gitlab.com/polito-edyce-prelude/predyce2"


@pytest.fixture
def gitlab_group_url() -> str:
    return "https://gitlab.com/polito-edyce-prelude"


@pytest.fixture
def gitlab_group_url_2() -> str:
    return "https://gitlab.com/polito-edyce-prelude2"


@pytest.fixture
def unknown_url() -> str:
    return "https://badlab.com/"


@pytest.fixture
def unknown_url_2() -> str:
    return "https://badlab.com/2"

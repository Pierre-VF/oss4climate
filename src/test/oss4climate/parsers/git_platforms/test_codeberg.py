import pytest

from oss4climate.src.parsers.git_platforms.codeberg_io import CodebergScraper


@pytest.fixture
def url_codeberg_repository():
    return "https://codeberg.org/LibreWater/Acraea-Prototype"


@pytest.fixture
def url_codeberg_organisation():
    return "https://codeberg.org/LibreWater"


def test_codeberg_scraper(url_codeberg_repository, url_codeberg_organisation):
    cbs = CodebergScraper()

    assert cbs.is_relevant_url(url_codeberg_repository)
    assert cbs.is_relevant_url(url_codeberg_organisation)

    assert (
        cbs.extract_repository_organisation(url_codeberg_repository)
        == url_codeberg_organisation.split("/")[-1]
    )

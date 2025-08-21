import pytest

from oss4climate.src.parsers.git_platforms.bitbucket_io import BitbucketScraper


@pytest.fixture
def url_bitbucket_repository():
    return "https://bitbucket.org/Xeelk/pymfa2"


@pytest.fixture
def url_bitbucket_organisation():
    return "https://bitbucket.org/Xeelk"


def test_codeberg_scraper(url_bitbucket_repository, url_bitbucket_organisation):
    bbs = BitbucketScraper()

    assert bbs.is_relevant_url(url_bitbucket_repository)
    assert bbs.is_relevant_url(url_bitbucket_organisation)

    assert (
        bbs.extract_repository_organisation(url_bitbucket_repository)
        == url_bitbucket_organisation.split("/")[-1]
    )

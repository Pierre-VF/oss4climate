"""
Tests for the RepositoryScraper class (oss4climate.src.repository_scraper).

Tests URL parsing, ProjectDetails conversion, and the scraper initialization.
"""

from datetime import date

from oss4climate.src.models import EnumDocumentationFileType, ProjectDetails
from oss4climate.src.repository_scraper import RepositoryScraper

# ---------------------------------------------------------------------------
# RepositoryScraper initialization tests
# ---------------------------------------------------------------------------


def test_scraper_default_refresh_days():
    scraper = RepositoryScraper()
    assert scraper.refresh_days == 28


def test_scraper_custom_refresh_days():
    scraper = RepositoryScraper(refresh_days=7)
    assert scraper.refresh_days == 7


def test_scraper_cache_lifetime():
    from datetime import timedelta

    scraper = RepositoryScraper(cache_lifetime=timedelta(hours=1))
    assert scraper.cache_lifetime == timedelta(hours=1)


# ---------------------------------------------------------------------------
# URL parsing tests
# ---------------------------------------------------------------------------


class TestGetPlatformFromURL:
    """Tests for _get_platform_from_url method."""

    def test_github_https(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "https://github.com/oss4climate/oss4climate"
        )
        assert platform == "github"
        assert path == "oss4climate/oss4climate"

    def test_github_http(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "http://github.com/oss4climate/oss4climate"
        )
        assert platform == "github"
        assert path == "oss4climate/oss4climate"

    def test_github_lowercase(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "https://GITHUB.COM/oss4climate/oss4climate"
        )
        assert platform == "github"
        assert path == "oss4climate/oss4climate"

    def test_gitlab_com(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "https://gitlab.com/polito-edyce-prelude/predyce"
        )
        assert platform == "gitlab"
        assert path == "gitlab.com/polito-edyce-prelude/predyce"

    def test_gitlab_self_hosted(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "https://git.example.com/group/subgroup/repo"
        )
        assert platform == "gitlab"
        assert path == "git.example.com/group/subgroup/repo"

    def test_codeberg(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "https://codeberg.org/oss4climate/oss4climate"
        )
        assert platform == "codeberg"
        assert path == "oss4climate/oss4climate"

    def test_bitbucket(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url(
            "https://bitbucket.org/oss4climate/oss4climate"
        )
        assert platform == "bitbucket"
        assert path == "oss4climate/oss4climate"

    def test_unknown_platform(self):
        scraper = RepositoryScraper()
        platform, path = scraper._get_platform_from_url("https://badlab.com/repo")
        assert platform == "unknown"
        assert path == "https://badlab.com/repo"


class TestGetRepoID:
    """Tests for _get_repo_id method."""

    def test_github_repo_id(self):
        scraper = RepositoryScraper()
        repo_id = scraper._get_repo_id("https://github.com/oss4climate/oss4climate")
        assert repo_id == "github.com/oss4climate/oss4climate"

    def test_gitlab_repo_id(self):
        scraper = RepositoryScraper()
        repo_id = scraper._get_repo_id(
            "https://gitlab.com/polito-edyce-prelude/predyce"
        )
        # GitLab repo_id includes the host prefix for gitlab.com
        assert repo_id == "gitlab.com/polito-edyce-prelude/predyce"

    def test_gitlab_self_hosted_repo_id(self):
        scraper = RepositoryScraper()
        repo_id = scraper._get_repo_id("https://git.example.com/group/subgroup/repo")
        assert repo_id == "git.example.com/group/subgroup/repo"

    def test_codeberg_repo_id(self):
        scraper = RepositoryScraper()
        repo_id = scraper._get_repo_id("https://codeberg.org/oss4climate/oss4climate")
        # Codeberg uses .com in repo_id
        assert repo_id == "codeberg.org/oss4climate/oss4climate"

    def test_bitbucket_repo_id(self):
        scraper = RepositoryScraper()
        repo_id = scraper._get_repo_id("https://bitbucket.org/oss4climate/oss4climate")
        # Bitbucket uses .com in repo_id
        assert repo_id == "bitbucket.org/oss4climate/oss4climate"


class TestGetOrgID:
    """Tests for _get_org_id method."""

    def test_github_org_id(self):
        scraper = RepositoryScraper()
        org_id = scraper._get_org_id("https://github.com/oss4climate")
        assert org_id == "github.com/oss4climate"

    def test_github_org_id_with_path(self):
        scraper = RepositoryScraper()
        org_id = scraper._get_org_id("https://github.com/oss4climate/something")
        assert org_id == "github.com/oss4climate"

    def test_gitlab_org_id(self):
        scraper = RepositoryScraper()
        org_id = scraper._get_org_id("https://gitlab.com/polito-edyce-prelude")
        # GitLab org_id for gitlab.com is just the host
        assert org_id == "gitlab.com"

    def test_gitlab_self_hosted_org_id(self):
        scraper = RepositoryScraper()
        org_id = scraper._get_org_id("https://git.example.com/group/subgroup")
        # Self-hosted GitLab org_id includes host + first path segment
        assert org_id == "git.example.com"

    def test_codeberg_org_id(self):
        scraper = RepositoryScraper()
        org_id = scraper._get_org_id("https://codeberg.org/oss4climate")
        assert org_id == "codeberg.org/oss4climate"

    def test_bitbucket_org_id(self):
        scraper = RepositoryScraper()
        org_id = scraper._get_org_id("https://bitbucket.org/oss4climate")
        assert org_id == "bitbucket.org/oss4climate"


class TestExtractHostAndPath:
    """Tests for _extract_host_and_path method."""

    def test_github(self):
        scraper = RepositoryScraper()
        host, path = scraper._extract_host_and_path(
            "https://github.com/oss4climate/oss4climate"
        )
        assert host == "github.com"
        assert path == "oss4climate/oss4climate"

    def test_gitlab_self_hosted(self):
        scraper = RepositoryScraper()
        host, path = scraper._extract_host_and_path(
            "https://git.example.com/group/subgroup"
        )
        assert host == "git.example.com"
        assert path == "group/subgroup"

    def test_no_protocol(self):
        scraper = RepositoryScraper()
        host, path = scraper._extract_host_and_path("github.com/oss4climate")
        assert host == "github.com"
        assert path == "oss4climate"


# ---------------------------------------------------------------------------
# ProjectDetails to dict conversion tests
# ---------------------------------------------------------------------------


def _make_project_details(**overrides):
    """Helper to create a ProjectDetails with sensible defaults."""
    defaults = {
        "id": "github.com/test/repo",
        "name": "Test Repo",
        "organisation_id": "https://github.com/test",
        "url": "https://github.com/test/repo",
        "website": None,
        "description": "A test repo",
        "licence": "MIT",
        "licence_url": None,
        "latest_update": date(2025, 1, 15),
        "language": "Python",
        "all_languages": ["Python"],
        "last_commit": date(2025, 1, 10),
        "open_pull_requests": 0,
        "raw_details": {},
        "master_branch": "main",
        "readme": "# Hello",
        "is_fork": False,
        "forked_from": None,
        "readme_type": EnumDocumentationFileType.MARKDOWN,
    }
    defaults.update(overrides)
    return ProjectDetails(**defaults)


class TestProjectDetailsToDict:
    """Tests for _project_details_to_dict method."""

    def test_project_details_to_dict_from_object(self):
        scraper = RepositoryScraper()
        details = _make_project_details(
            all_languages=["Python", "JavaScript"],
        )

        result = scraper._project_details_to_dict(details)

        assert result["id"] == "github.com/test/repo"
        assert result["name"] == "Test Repo"
        assert result["description"] == "A test repo"
        assert result["licence"] == "MIT"
        assert result["language"] == "Python"
        assert result["all_languages"] == '["Python", "JavaScript"]'
        assert result["master_branch"] == "main"
        assert result["readme"] == "# Hello"
        assert result["readme_type"] == "md"
        assert result["is_fork"] is False
        assert result["latest_update"] == date(2025, 1, 15)
        assert result["last_commit"] == date(2025, 1, 10)
        assert "raw_details" not in result

    def test_project_details_to_dict_from_dataframe_row(self):
        import pandas as pd

        scraper = RepositoryScraper()
        # Simulate a pandas DataFrame row via itertuples (how scraper uses it)
        df = pd.DataFrame(
            [
                {
                    "id": "github.com/df/repo",
                    "name": "DF Repo",
                    "organisation_id": "github.com/df",
                    "url": "https://github.com/df/repo",
                    "description": "DataFrame repo",
                    "licence": "Apache",
                    "language": "Java",
                    "all_languages": ["Java", "XML"],
                    "master_branch": "master",
                    "readme": "# DF",
                    "readme_type": EnumDocumentationFileType.MARKDOWN,
                    "is_fork": True,
                    "latest_update": date(2025, 2, 1),
                    "last_commit": date(2025, 2, 1),
                }
            ]
        )
        row = list(df.itertuples())[0]

        result = scraper._project_details_to_dict(row)

        assert result["id"] == "github.com/df/repo"
        assert result["name"] == "DF Repo"
        assert result["all_languages"] == '["Java", "XML"]'
        assert result["readme_type"] == "md"
        assert result["is_fork"] is True

    def test_project_details_to_dict_handles_none_all_languages(self):
        scraper = RepositoryScraper()
        details = _make_project_details(all_languages=None)

        result = scraper._project_details_to_dict(details)
        assert result["all_languages"] is None

    def test_project_details_to_dict_handles_empty_list_all_languages(self):
        scraper = RepositoryScraper()
        details = _make_project_details(all_languages=[])

        result = scraper._project_details_to_dict(details)
        assert result["all_languages"] == "[]"

    def test_project_details_to_dict_removes_raw_details(self):
        scraper = RepositoryScraper()
        details = _make_project_details(raw_details={"some": "data"})

        result = scraper._project_details_to_dict(details)
        assert "raw_details" not in result

    def test_project_details_to_dict_enum_readme_type(self):
        scraper = RepositoryScraper()
        details = _make_project_details(
            readme_type=EnumDocumentationFileType.RESTRUCTURED_TEXT
        )

        result = scraper._project_details_to_dict(details)
        assert result["readme_type"] == "rst"

    def test_project_details_to_dict_unknown_readme_type(self):
        scraper = RepositoryScraper()
        details = _make_project_details(readme_type=EnumDocumentationFileType.UNKNOWN)

        result = scraper._project_details_to_dict(details)
        assert result["readme_type"] == "?"

    def test_project_details_to_dict_html_readme_type(self):
        scraper = RepositoryScraper()
        details = _make_project_details(readme_type=EnumDocumentationFileType.HTML)

        result = scraper._project_details_to_dict(details)
        assert result["readme_type"] == "html"

    def test_project_details_to_dict_all_fields(self):
        """Test that all ProjectDetails fields are preserved."""
        scraper = RepositoryScraper()
        details = _make_project_details(
            forked_from="https://github.com/original/repo",
            open_pull_requests=10,
        )

        result = scraper._project_details_to_dict(details)

        expected_fields = {
            "id",
            "name",
            "organisation_id",
            "url",
            "website",
            "description",
            "licence",
            "licence_url",
            "latest_update",
            "last_commit",
            "language",
            "all_languages",
            "open_pull_requests",
            "master_branch",
            "readme",
            "readme_type",
            "is_fork",
            "forked_from",
        }
        assert set(result.keys()) == expected_fields
        assert result["forked_from"] == "https://github.com/original/repo"
        assert result["open_pull_requests"] == 10


# ---------------------------------------------------------------------------
# _now method tests
# ---------------------------------------------------------------------------


def test_now_returns_iso_string():
    scraper = RepositoryScraper()
    now_str = scraper._now()
    # Should be a valid ISO format string
    parsed = scraper._now()
    assert isinstance(parsed, str)
    assert "T" in parsed  # ISO format contains 'T'

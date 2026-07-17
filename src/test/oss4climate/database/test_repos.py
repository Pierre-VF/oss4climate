"""
Tests for the repository database module (oss4climate.src.database.repos).

Uses in-memory SQLite databases to avoid polluting the real DB during tests.
"""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from oss4climate.src.database.repos import (
    Organisation,
    Repository,
    get_active_repos_to_scrape,
    get_all_active_repos,
    get_all_organisations,
    get_repos_for_typesense,
    mark_repos_inactive,
    reset_repo_error,
    set_repo_error,
    upsert_organisation,
    upsert_repository,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    """Create an in-memory SQLite engine with fresh tables."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Provide a session bound to the in-memory engine."""
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# Organisation model tests
# ---------------------------------------------------------------------------


def test_organisation_model_defaults(session):
    org = Organisation(id="github.com/test-org")
    session.add(org)
    session.commit()
    session.refresh(org)

    assert org.id == "github.com/test-org"
    assert org.name is None
    assert org.description is None
    assert org.last_error is None
    assert org.error_count is None


def test_organisation_model_full(session):
    now = datetime.now(tz=UTC)
    org = Organisation(
        id="github.com/full-org",
        name="Full Org",
        description="A test organisation",
        url="https://github.com/full-org",
        created_at=now,
        updated_at=now,
        public_repos=42,
        total_private_repos=10,
        has_organization_projects=True,
        blog="https://example.com",
        location="Worldwide",
        email="test@example.com",
        last_scraped_at=now,
        last_error=None,
        error_count=None,
    )
    session.add(org)
    session.commit()
    session.refresh(org)

    assert org.name == "Full Org"
    assert org.public_repos == 42
    assert org.total_private_repos == 10
    assert org.has_organization_projects is True


# ---------------------------------------------------------------------------
# Repository model tests
# ---------------------------------------------------------------------------


def test_repository_model_defaults(session):
    repo = Repository(id="github.com/test/repo")
    session.add(repo)
    session.commit()
    session.refresh(repo)

    assert repo.id == "github.com/test/repo"
    assert repo.active is True
    assert repo.last_error is None
    assert repo.error_count is None
    assert repo.disappeared_on is None


def test_repository_model_full(session):
    now = datetime.now(tz=UTC)
    repo = Repository(
        id="github.com/full/repo",
        organisation_id="github.com/full",
        name="Full Repo",
        url="https://github.com/full/repo",
        website="https://full.example.com",
        description="A test repository",
        licence="MIT",
        licence_url="https://opensource.org/licenses/MIT",
        latest_update=date(2025, 1, 15),
        last_commit=date(2025, 1, 10),
        language="Python",
        all_languages=json.dumps(["Python", "JavaScript"]),
        open_pull_requests=5,
        master_branch="main",
        readme="# Hello world",
        readme_type="md",
        is_fork=False,
        forked_from=None,
        last_scraped_at=now,
        last_error=None,
        error_count=None,
        disappeared_on=None,
        active=True,
    )
    session.add(repo)
    session.commit()
    session.refresh(repo)

    assert repo.name == "Full Repo"
    assert repo.organisation_id == "github.com/full"
    assert repo.language == "Python"
    assert repo.readme_type == "md"
    assert repo.is_fork is False


# ---------------------------------------------------------------------------
# Upsert tests
# ---------------------------------------------------------------------------


def test_upsert_organisation_create(session):
    org_data = {
        "id": "github.com/new-org",
        "name": "New Org",
        "description": "Just created",
    }
    result = upsert_organisation(session, org_data)

    assert result.id == "github.com/new-org"
    assert result.name == "New Org"
    assert result.description == "Just created"

    # Verify it's in the DB
    stored = session.exec(
        select(Organisation).where(Organisation.id == "github.com/new-org")
    ).first()
    assert stored is not None
    assert stored.name == "New Org"


def test_upsert_organisation_update(session):
    # Create initial org
    upsert_organisation(session, {"id": "github.com/upd-org", "name": "Original"})

    # Upsert with partial update
    result = upsert_organisation(
        session, {"id": "github.com/upd-org", "description": "Updated"}
    )

    assert result.name == "Original"  # preserved
    assert result.description == "Updated"  # updated


def test_upsert_organisation_skips_none_values(session):
    upsert_organisation(session, {"id": "github.com/skip-org", "name": "Has name"})

    # Upsert with None value should not overwrite existing
    upsert_organisation(session, {"id": "github.com/skip-org", "name": None})

    stored = session.exec(
        select(Organisation).where(Organisation.id == "github.com/skip-org")
    ).first()
    assert stored.name == "Has name"  # preserved, not overwritten by None


def test_upsert_organisation_raises_without_id(session):
    with pytest.raises(ValueError, match="'id'"):
        upsert_organisation(session, {"name": "No ID"})


def test_upsert_repository_create(session):
    repo_data = {
        "id": "github.com/new/repo",
        "name": "New Repo",
        "url": "https://github.com/new/repo",
    }
    result = upsert_repository(session, repo_data)

    assert result.id == "github.com/new/repo"
    assert result.name == "New Repo"


def test_upsert_repository_update(session):
    upsert_repository(session, {"id": "github.com/upd/repo", "name": "Original"})

    result = upsert_repository(
        session, {"id": "github.com/upd/repo", "language": "Python"}
    )

    assert result.name == "Original"  # preserved
    assert result.language == "Python"  # updated


def test_upsert_repository_raises_without_id(session):
    with pytest.raises(ValueError, match="'id'"):
        upsert_repository(session, {"name": "No ID"})


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------


def test_get_all_active_repos(session):
    # Create active repos
    upsert_repository(session, {"id": "github.com/active1/repo", "active": True})
    upsert_repository(session, {"id": "github.com/active2/repo", "active": True})
    upsert_repository(session, {"id": "github.com/inactive/repo", "active": False})

    active = get_all_active_repos(session)
    assert len(active) == 2
    ids = {r.id for r in active}
    assert "github.com/active1/repo" in ids
    assert "github.com/active2/repo" in ids
    assert "github.com/inactive/repo" not in ids


def test_get_all_organisations(session):
    upsert_organisation(session, {"id": "github.com/org1", "name": "Org 1"})
    upsert_organisation(session, {"id": "github.com/org2", "name": "Org 2"})

    orgs = get_all_organisations(session)
    assert len(orgs) == 2
    ids = {o.id for o in orgs}
    assert "github.com/org1" in ids
    assert "github.com/org2" in ids


def test_get_active_repos_to_scrape_never_scraped(session):
    upsert_repository(session, {"id": "github.com/new/repo", "active": True})

    result = get_active_repos_to_scrape(session, refresh_days=28)
    assert len(result) == 1
    assert result[0].id == "github.com/new/repo"


def test_get_active_repos_to_scrape_past_threshold(session):
    old_time = datetime.now(tz=UTC) - timedelta(days=30)
    upsert_repository(
        session,
        {
            "id": "github.com/old/repo",
            "active": True,
            "last_scraped_at": old_time,
        },
    )

    result = get_active_repos_to_scrape(session, refresh_days=28)
    assert len(result) == 1
    assert result[0].id == "github.com/old/repo"


def test_get_active_repos_to_scrape_recently_scraped(session):
    recent_time = datetime.now(tz=UTC) - timedelta(days=7)
    upsert_repository(
        session,
        {
            "id": "github.com/recent/repo",
            "active": True,
            "last_scraped_at": recent_time,
        },
    )

    result = get_active_repos_to_scrape(session, refresh_days=28)
    assert len(result) == 0


def test_get_active_repos_to_scrape_inactive_repo(session):
    upsert_repository(
        session,
        {
            "id": "github.com/inactive/repo",
            "active": False,
            "last_scraped_at": None,
        },
    )

    result = get_active_repos_to_scrape(session, refresh_days=28)
    assert len(result) == 0


def test_get_active_repos_to_scrape_custom_threshold(session):
    old_time = datetime.now(tz=UTC) - timedelta(days=10)
    upsert_repository(
        session,
        {
            "id": "github.com/medium/repo",
            "active": True,
            "last_scraped_at": old_time,
        },
    )

    # With 5-day threshold, should be included (10 days > 5 days)
    result = get_active_repos_to_scrape(session, refresh_days=5)
    assert len(result) == 1

    # With 30-day threshold, should NOT be included (10 days < 30 days)
    result = get_active_repos_to_scrape(session, refresh_days=30)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Inactive marking tests
# ---------------------------------------------------------------------------


def test_mark_repos_inactive(session):
    upsert_repository(session, {"id": "github.com/keep/repo", "active": True})
    upsert_repository(session, {"id": "github.com/remove/repo", "active": True})

    count = mark_repos_inactive(session, {"github.com/keep/repo"})

    assert count == 1
    kept = session.exec(
        select(Repository).where(Repository.id == "github.com/keep/repo")
    ).first()
    removed = session.exec(
        select(Repository).where(Repository.id == "github.com/remove/repo")
    ).first()

    assert kept.active is True
    assert removed.active is False
    assert removed.disappeared_on == date.today()


def test_mark_repos_inactive_empty_set(session):
    upsert_repository(session, {"id": "github.com/all/remove/repo", "active": True})

    count = mark_repos_inactive(session, set())
    assert count == 1


def test_mark_repos_inactive_no_change(session):
    upsert_repository(session, {"id": "github.com/keep2/repo", "active": True})

    count = mark_repos_inactive(session, {"github.com/keep2/repo"})
    assert count == 0


def test_mark_repos_inactive_custom_date(session):
    upsert_repository(session, {"id": "github.com/custom/repo", "active": True})

    custom_date = date(2025, 6, 1)
    count = mark_repos_inactive(session, set(), disappeared_on=custom_date)

    assert count == 1
    repo = session.exec(
        select(Repository).where(Repository.id == "github.com/custom/repo")
    ).first()
    assert repo.disappeared_on == custom_date


# ---------------------------------------------------------------------------
# Error tracking tests
# ---------------------------------------------------------------------------


def test_set_repo_error(session):
    upsert_repository(session, {"id": "github.com/error/repo"})

    set_repo_error(session, "github.com/error/repo", "API timeout")

    repo = session.exec(
        select(Repository).where(Repository.id == "github.com/error/repo")
    ).first()
    assert repo.last_error == "API timeout"
    assert repo.error_count == 1


def test_set_repo_error_increment(session):
    upsert_repository(session, {"id": "github.com/multi-error/repo"})

    set_repo_error(session, "github.com/multi-error/repo", "Error 1")
    set_repo_error(session, "github.com/multi-error/repo", "Error 2")

    repo = session.exec(
        select(Repository).where(Repository.id == "github.com/multi-error/repo")
    ).first()
    assert repo.last_error == "Error 2"
    assert repo.error_count == 2


def test_reset_repo_error(session):
    upsert_repository(session, {"id": "github.com/reset/repo"})
    set_repo_error(session, "github.com/reset/repo", "Previous error")

    reset_repo_error(session, "github.com/reset/repo")

    repo = session.exec(
        select(Repository).where(Repository.id == "github.com/reset/repo")
    ).first()
    assert repo.last_error is None
    assert repo.error_count is None


def test_reset_repo_error_no_error(session):
    upsert_repository(session, {"id": "github.com/no-error/repo"})

    # Should not raise
    reset_repo_error(session, "github.com/no-error/repo")


def test_reset_repo_error_nonexistent(session):
    # Should not raise for non-existent repo
    reset_repo_error(session, "github.com/nonexistent/repo")


# ---------------------------------------------------------------------------
# Typesense export tests
# ---------------------------------------------------------------------------


def test_get_repos_for_typesense_empty(session):
    result = get_repos_for_typesense(session)
    assert result == []


def test_get_repos_for_typesense_basic(session):
    upsert_repository(
        session,
        {
            "id": "github.com/ts/repo",
            "name": "TS Repo",
            "url": "https://github.com/ts/repo",
            "description": "A test repo",
            "language": "Python",
            "licence": "MIT",
            "readme": "# Hello",
            "is_fork": False,
            "active": True,
        },
    )

    result = get_repos_for_typesense(session)
    assert len(result) == 1

    record = result[0]
    assert record["id"] == "github.com/ts/repo"
    assert record["name"] == "TS Repo"
    assert record["description"] == "A test repo"
    assert record["language"] == "Python"
    assert record["licence"] == "MIT"
    assert record["readme"] == "# Hello"
    assert record["is_fork"] is False


def test_get_repos_for_typesense_excludes_inactive(session):
    upsert_repository(
        session,
        {
            "id": "github.com/active-ts/repo",
            "name": "Active",
            "active": True,
        },
    )
    upsert_repository(
        session,
        {
            "id": "github.com/inactive-ts/repo",
            "name": "Inactive",
            "active": False,
        },
    )

    result = get_repos_for_typesense(session)
    assert len(result) == 1
    assert result[0]["name"] == "Active"


def test_get_repos_for_typesense_null_defaults(session):
    upsert_repository(
        session,
        {
            "id": "github.com/nulls/repo",
            "name": None,
            "description": None,
            "language": None,
            "licence": None,
            "readme": None,
            "is_fork": None,
            "active": True,
        },
    )

    result = get_repos_for_typesense(session)
    record = result[0]
    assert record["name"] == ""
    assert record["description"] == ""
    assert record["language"] == ""
    assert record["licence"] == ""
    assert record["readme"] == ""
    assert record["is_fork"] is False

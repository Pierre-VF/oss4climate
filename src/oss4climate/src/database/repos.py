"""
Module to manage the repository and organisation database tables.

This module provides SQLModel-based tables for storing scraped repository
and organisation metadata, along with engine initialization and helper
functions for database access.
"""

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import model_validator
from sqlmodel import Field, Session, SQLModel, select

from oss4climate.src.helpers import now
from oss4climate.src.log import log_info

# -------------------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------------------


class Organisation(SQLModel, table=True):
    """
    Organisation/group metadata from a Git hosting platform.

    Each row represents an organisation or group that may own multiple repositories.
    """

    __tablename__ = "organisations"

    id: str = Field(default=None, primary_key=True, nullable=False)
    name: str | None = None
    description: str | None = None
    url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    public_repos: int | None = None
    total_private_repos: int | None = None
    has_organization_projects: bool | None = None
    blog: str | None = None
    location: str | None = None
    email: str | None = None
    last_scraped_at: datetime | None = None
    last_error: str | None = None
    error_count: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _validate_model_before(cls, d: Any):
        if isinstance(d, dict):
            for i in ["created_at", "updated_at", "last_scraped_at"]:
                if isinstance(d.get(i), str):
                    d[i] = datetime.fromisoformat(d[i])
        return d


class Repository(SQLModel, table=True):
    """
    Repository metadata scraped from a Git hosting platform.

    Each row represents a single repository with its full scraped metadata.
    """

    __tablename__ = "repositories"

    id: str = Field(default=None, primary_key=True, nullable=False)
    organisation_id: str | None = Field(
        default=None,
        foreign_key="organisations.id",
    )
    name: str | None = None
    url: str | None = None
    website: str | None = None
    description: str | None = None
    licence: str | None = None
    licence_url: str | None = None
    latest_update: date | None = None
    last_commit: date | None = None
    language: str | None = None
    all_languages: str | None = None  # JSON array of strings
    open_pull_requests: int | None = None
    master_branch: str | None = None
    readme: str | None = None
    readme_type: str | None = None  # "md", "rst", "html", "?"
    is_fork: bool | None = None
    forked_from: str | None = None
    last_scraped_at: datetime | None = None
    last_error: str | None = None
    error_count: int | None = None
    disappeared_on: date | None = None
    active: bool = Field(default=True)

    @model_validator(mode="before")
    @classmethod
    def _validate(cls, d: dict):
        for i in ["last_scraped_at"]:
            if isinstance(d.get(i), str):
                d[i] = datetime.fromisoformat(d[i])
        return d


# -------------------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------------------


def upsert_organisation(
    session: Session,
    org_data: dict,
    commit: bool = False,
    update_scraped_at: bool = False,
) -> Organisation:
    """
    Upsert an organisation into the database.

    :param session: Database session
    :param org_data: Dictionary of organisation fields (id, name, description, etc.)
    :param commit: bool, where True means commit the session (Default is False)
    :param update_scraped_at: bool, where True means update the scraped_at field to now time (Default is False)
    :return: The upserted Organisation object
    """
    org_id = org_data.get("id")
    if org_id is None:
        raise ValueError("Organisation data must include 'id'")

    existing = session.exec(
        select(Organisation).where(Organisation.id == org_id)
    ).first()

    if update_scraped_at:
        org_data["last_scraped_at"] = now()

    if existing is None:
        org = Organisation.model_validate(org_data)
        session.add(org)
    else:
        new_org = Organisation.model_validate(org_data)  # For datetime fix
        for key, value in org_data.items():
            if hasattr(existing, key) and value is not None:
                setattr(existing, key, getattr(new_org, key))
    if commit:
        session.commit()
    return existing if existing else org


def upsert_repository(
    session: Session,
    repo_data: dict,
    commit: bool = False,
) -> Repository:
    """
    Upsert a repository into the database.

    :param session: Database session
    :param repo_data: Dictionary of repository fields (id, name, url, etc.)
    :param commit: bool, where True means commit the session (Default is False)
    :return: The upserted Repository object
    """
    repo_id = repo_data.get("id")
    if repo_id is None:
        raise ValueError("Repository data must include 'id'")

    existing = session.exec(select(Repository).where(Repository.id == repo_id)).first()

    if existing is None:
        repo = Repository.model_validate(repo_data)
        session.add(repo)
    else:
        new_repo = Repository.model_validate(repo_data)
        for key, value in repo_data.items():
            if hasattr(existing, key) and value is not None:
                setattr(existing, key, getattr(new_repo, key))
        session.add(existing)

    if commit:
        session.commit()
    return existing if existing else repo


def get_active_repos_to_scrape(
    session: Session,
    refresh_days: int = 28,
) -> list[Repository]:
    """
    Get all active repositories that need scraping.

    A repository needs scraping if:
    - It is active (active=True)
    - It has never been scraped (last_scraped_at IS NULL)
    - OR its last scrape was more than refresh_days ago

    :param session: Database session
    :param refresh_days: Number of days since last scrape before re-scraping
    :return: List of Repository objects that need scraping
    """
    threshold = now() - timedelta(days=refresh_days)
    result = session.exec(
        select(Repository).where(
            Repository.active == True,  # noqa: E712
            (Repository.last_scraped_at == None)
            | (Repository.last_scraped_at < threshold),  # noqa: E711
        )
    ).all()
    return list(result)


def mark_repos_inactive(
    session: Session,
    repo_ids_to_keep: set[str],
    disappeared_on: date | None = None,
) -> int:
    """
    Mark repositories as inactive if they are not in the keep set.

    :param session: Database session
    :param repo_ids_to_keep: Set of repository IDs that should remain active
    :param disappeared_on: Date to set as disappeared_on (defaults to today)
    :return: Number of repos marked inactive
    """
    if disappeared_on is None:
        disappeared_on = date.today()

    result = session.exec(
        select(Repository).where(
            Repository.active == True,  # noqa: E712
            Repository.id.not_in(repo_ids_to_keep),
        )
    ).all()

    count = 0
    for repo in result:
        repo.active = False
        repo.disappeared_on = disappeared_on
        count += 1

    if count > 0:
        session.commit()
        log_info(f"Marked {count} repositories as inactive")

    return count


def get_all_active_repos(session: Session) -> list[Repository]:
    """
    Get all active repositories from the database.

    :param session: Database session
    :return: List of all active Repository objects
    """
    result = session.exec(
        select(Repository).where(Repository.active == True)  # noqa: E712
    ).all()
    return list(result)


def get_all_organisations(session: Session) -> list[Organisation]:
    """
    Get all organisations from the database.

    :param session: Database session
    :return: List of all Organisation objects
    """
    result = session.exec(select(Organisation)).all()
    return list(result)


def reset_repo_error(session: Session, repo_id: str) -> None:
    """
    Reset error tracking for a successfully scraped repository.

    :param session: Database session
    :param repo_id: Repository ID
    """
    repo = session.exec(select(Repository).where(Repository.id == repo_id)).first()
    if repo:
        repo.last_error = None
        repo.error_count = None
        session.commit()


def set_repo_error(session: Session, repo_id: str, error: str) -> None:
    """
    Set error tracking for a failed repository scrape.

    :param session: Database session
    :param repo_id: Repository ID
    :param error: Error message
    """
    repo = session.exec(select(Repository).where(Repository.id == repo_id)).first()
    if repo:
        repo.last_error = error
        repo.error_count = (repo.error_count or 0) + 1
        session.commit()


def get_repos_for_typesense(session: Session) -> list[dict]:
    """
    Get all active repositories in a format suitable for Typesense indexing.

    :param session: Database session
    :return: List of dictionaries with Typesense-compatible fields
    """
    repos = get_all_active_repos(session)
    results = []
    for repo in repos:
        record = {
            "id": repo.id,
            "name": repo.name or "",
            "description": repo.description or "",
            "readme": repo.readme or "",
            "organisation_id": repo.organisation_id or "",
            "licence": repo.licence or "",
            "language": repo.language or "",
            "url": repo.url or "",
            "last_commit": repo.last_commit,
            "is_fork": repo.is_fork or False,
        }
        results.append(record)
    return results

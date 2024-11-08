"""
Module for local logging and tracking of activity
"""

from datetime import UTC, datetime

from fastapi import Request

from oss4climate_app.src.database import RequestLog, SearchLog, open_database_session


def log_search(
    search_term: str | None, number_of_results: int, view_offset: int | None = None
) -> None:
    with open_database_session() as session:
        session.add(
            SearchLog(
                search_term=search_term,
                timestamp=datetime.now(tz=UTC),
                number_of_results=number_of_results,
                view_offset=view_offset,
            )
        )
        session.commit()


def log_landing(request: Request) -> None:
    with open_database_session() as session:
        session.add(
            RequestLog(
                referer=request.headers.get("referer"),
                timestamp=datetime.now(tz=UTC),
            )
        )
        session.commit()

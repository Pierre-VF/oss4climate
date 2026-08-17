from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from oss4climate.src.config import SETTINGS


def _open_engine_and_create_database_if_missing():
    # Ensuring that all models are loaded
    from oss4climate.src.database.repos import Repository, Organisation  # noqa
    from oss4climate_app.src.database import SearchLog, RequestLog  # noqa

    x = create_engine(
        SETTINGS.database_connection_string,
        echo=False,
    )
    # TODO : this currently also creates empty tables for the "oss4climate" part of the code,
    #   this is likely avoidable and could be removed in a later version
    SQLModel.metadata.create_all(x)
    return x


global _ENGINE
_ENGINE = None


def get_engine() -> Engine:
    """
    Get the database engine.

    :return: SQLAlchemy engine
    """
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _open_engine_and_create_database_if_missing()
    return _ENGINE


def open_database_session() -> Session:
    return Session(get_engine())

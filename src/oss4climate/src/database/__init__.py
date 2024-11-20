"""
Module to manage a database input
"""

import json
import os
from datetime import UTC, datetime, timedelta

from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info


# -------------------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------------------
class Cache(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True, nullable=False)
    value: str
    fetched_at: datetime


# -------------------------------------------------------------------------------------
# Engine
# -------------------------------------------------------------------------------------


def _open_engine_and_create_database_if_missing():
    db_folder, __ = os.path.split(SETTINGS.SQLITE_DB)
    os.makedirs(db_folder, exist_ok=True)
    x = create_engine(
        f"sqlite:///{SETTINGS.SQLITE_DB}",
        echo=False,
    )
    SQLModel.metadata.create_all(x)
    return x


_ENGINE = _open_engine_and_create_database_if_missing()


# -------------------------------------------------------------------------------------
# Actual methods
# -------------------------------------------------------------------------------------
def __now() -> datetime:
    return datetime.now(tz=UTC)


def load_from_database(
    key: str,
    is_json: bool,
    cache_lifetime: timedelta | None = None,
) -> dict | None:
    with Session(_ENGINE) as session:
        res = session.exec(select(Cache).where(Cache.id == key)).first()
        if res is None:
            return None
        else:
            if cache_lifetime is not None:
                # Shortcircuit in case cache is too old
                if res.fetched_at.astimezone(UTC) <= __now() - cache_lifetime:
                    session.exec(delete(Cache).where(Cache.id == key))
                    session.commit()
                    log_info(f"Dropped expired cache for {key}")
                    return None

            if is_json:
                return json.loads(res.value)
            else:
                return res.value


def save_to_database(key: str, value: dict, is_json: bool) -> None:
    if is_json:
        value_to_write = json.dumps(value)
    else:
        value_to_write = value

    with Session(_ENGINE) as session:
        session.add(Cache(id=key, value=value_to_write, fetched_at=__now()))
        session.commit()

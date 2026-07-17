from pathlib import Path

import pandas as pd
import pytest
import typesense

from oss4climate.src.config import SETTINGS
from oss4climate.src.database.repos import Repository
from oss4climate_app.src.search.typesense_io import (
    index_data_in_typesense,
    reset_typesense_schema,
)


# Test data path
@pytest.fixture(scope="session")
def csv_data_for_seeding(path_data_for_tests) -> Path:
    return path_data_for_tests / "listing.csv"


@pytest.fixture(scope="session")
def initialised_typesense_client(filled_database_engine, csv_data_for_seeding):
    client = typesense.Client(
        {
            "nodes": [SETTINGS.typesense_config],
            "api_key": SETTINGS.TYPESENSE_API_KEY,
            "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
        }
    )
    # From CSV
    reset_typesense_schema(client)
    df = pd.read_csv(csv_data_for_seeding)
    df["last_commit"] = pd.to_datetime(df["last_commit"])
    df["latest_update"] = pd.to_datetime(df["latest_update"])
    index_data_in_typesense(client, df)
    # From DB
    df_db = pd.read_sql(
        f"SELECT * FROM {Repository.__tablename__}", filled_database_engine
    )
    index_data_in_typesense(client, df_db)

    return client

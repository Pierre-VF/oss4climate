from pathlib import Path

import pandas as pd
import pytest
import typesense
import typesense.exceptions
from oss4climate.src.config import SETTINGS
from oss4climate_app.src.search.typesense_io import index_data_in_typesense


# Test data path
@pytest.fixture
def csv_data_for_seeding(path_data_for_tests) -> Path:
    return path_data_for_tests / "listing.csv"


@pytest.fixture
def typesense_client(csv_data_for_seeding):
    client = typesense.Client(
        {
            "nodes": [SETTINGS.typesense_config],
            "api_key": SETTINGS.TYPESENSE_API_KEY,
            "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
        }
    )
    df = pd.read_csv(csv_data_for_seeding)
    df["last_commit"] = pd.to_datetime(df["last_commit"])
    df["latest_update"] = pd.to_datetime(df["latest_update"])
    index_data_in_typesense(client, df)
    return client

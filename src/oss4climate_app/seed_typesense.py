from datetime import timedelta

import pandas as pd
import typesense
import typesense.exceptions
from sqlmodel import Session

from oss4climate.src.config import SETTINGS
from oss4climate.src.database.repos import get_engine, get_repos_for_typesense
from oss4climate.src.log import log_info
from oss4climate.src.parsers.listings import opensustain_tech
from oss4climate_app.src.search.typesense_io import (
    generate_client,
    index_data_in_typesense,
    reset_typesense_schema,
)


def seed():
    client = typesense.Client(
        {
            "nodes": [SETTINGS.typesense_config],
            "api_key": SETTINGS.TYPESENSE_API_KEY,
            "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
        }
    )

    log_info("Starting seeding of Typesense")

    # ==============================================================================
    # Seeding the search engine
    # ==============================================================================

    # Load repos from database
    with Session(get_engine()) as session:
        repo_dicts = get_repos_for_typesense(session)

    # Convert to DataFrame (matching the expected schema from the old feather-based pipeline)
    df = pd.DataFrame(repo_dicts)
    # Remove all the ones that aren't properly scraped yet (proxy = name is not available)
    df.dropna(subset=["name"])
    # Then check for emptiness
    if df.empty:
        raise ValueError("No data to index")

    # ==============================================================================
    # Mark the OSSTech repos
    # ==============================================================================

    osst_targets = opensustain_tech.fetch_all_project_urls_from_opensustain_webpage(
        cache_lifetime=timedelta(hours=6)
    )
    df["high_quality"] = df["url"].apply(lambda i: i in osst_targets)
    log_info(osst_targets)

    # ==============================================================================
    # Proceed with seeding
    # ==============================================================================
    ts_client = generate_client()
    reset_typesense_schema(ts_client)

    index_data_in_typesense(ts_client, df.rename(columns={"id": "idx"}))

    log_info("DONE")


if __name__ == "__main__":
    seed()

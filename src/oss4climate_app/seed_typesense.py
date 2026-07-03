import typesense
import typesense.exceptions

from oss4climate.src.config import SETTINGS
from oss4climate_app.src.config import FILE_OUTPUT_LISTING_FEATHER

client = typesense.Client(
    {
        "nodes": [SETTINGS.typesense_config],
        "api_key": SETTINGS.TYPESENSE_API_KEY,
        "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
    }
)

print("Starting seeding of Typesense")

# ==============================================================================
# Seeding the search engine
# ==============================================================================

from datetime import date

import pandas as pd

from oss4climate.src.database.repos import get_engine, get_repos_for_typesense
from oss4climate_app.src.search.typesense_io import (
    generate_client,
    index_data_in_typesense,
    reset_typesense_schema,
)
from sqlmodel import Session

# Load repos from database
with Session(get_engine()) as session:
    repo_dicts = get_repos_for_typesense(session)

# Convert to DataFrame (matching the expected schema from the old feather-based pipeline)
df = pd.DataFrame(repo_dicts)

# ==============================================================================
# Mark the OSSTech repos
# ==============================================================================
from datetime import timedelta

from oss4climate.src.parsers.listings import opensustain_tech

osst_targets = opensustain_tech.fetch_all_project_urls_from_opensustain_webpage(
    cache_lifetime=timedelta(hours=6)
)

df["high_quality"] = df["url"].apply(lambda i: i in osst_targets)

print(osst_targets)

# ==============================================================================
# Proceed with seeding
# ==============================================================================
ts_client = generate_client()
reset_typesense_schema(ts_client)
df["idx"] = df.index.to_series().astype(int)

index_data_in_typesense(ts_client, df)

print("DONE")

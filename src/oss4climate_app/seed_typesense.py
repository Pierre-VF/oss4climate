import pandas as pd
import typesense
import typesense.exceptions

from oss4climate.src.config import SETTINGS

client = typesense.Client(
    {
        "nodes": [
            {
                "host": SETTINGS.TYPESENSE_HOST,
                "port": SETTINGS.TYPESENSE_PORT,
                "protocol": SETTINGS.TYPESENSE_PROTOCOL,
            }
        ],
        "api_key": SETTINGS.TYPESENSE_API_KEY,
        "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
    }
)


# ==============================================================================
# Seeding the search engine
# ==============================================================================

from oss4climate_app.src.search.typesense_io import (
    index_data_in_typesense,
    reset_typesense_schema,
)

reset_typesense_schema()


# Full indexing of the files
df = pd.read_feather(
    SETTINGS.get_listing_file_with_readme_and_description_file_columns()[0]
)
df["idx"] = df.index.to_series().astype(int)

index_data_in_typesense(df.head(5))

print("DONE")

import typesense
import typesense.exceptions

from oss4climate.src.config import FILE_OUTPUT_LISTING_FEATHER, SETTINGS

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

from oss4climate.src.database.projects import project_dataframe_loader
from oss4climate_app.src.search.typesense_io import (
    index_data_in_typesense,
    reset_typesense_schema,
)

reset_typesense_schema()


# Full indexing of the files
df = project_dataframe_loader(FILE_OUTPUT_LISTING_FEATHER)
df["idx"] = df.index.to_series().astype(int)

index_data_in_typesense(df.head(200))

print("DONE")

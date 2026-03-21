import typesense
import typesense.exceptions
from oss4climate.src.config import SETTINGS

from oss4climate_app.config import FILE_OUTPUT_LISTING_FEATHER

client = typesense.Client(
    {
        "nodes": [SETTINGS.typesense_config],
        "api_key": SETTINGS.TYPESENSE_API_KEY,
        "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
    }
)


# ==============================================================================
# Seeding the search engine
# ==============================================================================

from oss4climate.src.database.projects import project_dataframe_loader

from oss4climate_app.src.search.typesense_io import (
    generate_client,
    index_data_in_typesense,
    reset_typesense_schema,
)

# Full indexing of the files
df = project_dataframe_loader(FILE_OUTPUT_LISTING_FEATHER)


ts_client = generate_client()
reset_typesense_schema(ts_client)
df["idx"] = df.index.to_series().astype(int)

index_data_in_typesense(ts_client, df)

print("DONE")

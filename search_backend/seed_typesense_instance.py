import pandas as pd
import typesense
import typesense.exceptions
from oss4climate.src.config import SETTINGS
from tqdm import tqdm

API_KEY = "12345"

client = typesense.Client(
    {
        "nodes": [
            {
                "host": "localhost",
                "port": "8108",
                "protocol": "http",
            }
        ],
        "api_key": API_KEY,
        "connection_timeout_seconds": 2,
    }
)


# ==============================================================================
# Seeding the search engine
# ==============================================================================

# see https://typesense.org/docs/guide/semantic-search.html#step-1-create-a-collection
EMBEDDING_MODEL = "ts/all-MiniLM-L12-v2"

repo_schemas = {
    "name": "projects",
    "fields": [
        {"name": "idx", "type": "int32"},
        {"name": "name", "type": "string"},
        {"name": "description", "type": "string"},
        {
            "name": "embedding_description",
            "type": "float[]",
            "embed": {
                "from": ["description"],
                "model_config": {"model_name": EMBEDDING_MODEL},
            },
        },
        {"name": "language", "type": "string"},
        {"name": "url", "type": "string"},
        # TODO : add hints from the README files (just need to compress key information well enough there)
    ],
    "default_sorting_field": "idx",
}

# Delete the collection
try:
    print("First deleting all projects")
    client.collections["projects"].delete()
    print("Delete completed")
except typesense.exceptions.ObjectNotFound:
    print("No projects defined")
print(" ")
print("Then recreating collections")
try:
    client.collections.create(repo_schemas)

except typesense.exceptions.ObjectAlreadyExists:
    pass

# Full indexing of the files
df = pd.read_feather(
    SETTINGS.get_listing_file_with_readme_and_description_file_columns()[0]
)
df["idx"] = df.index.to_series().astype(int)

for __, r in tqdm(df.iterrows()):
    client.collections["projects"].documents.import_(
        [{k: r[k] for k in ["idx", "name", "description", "language", "url"]}]
    )

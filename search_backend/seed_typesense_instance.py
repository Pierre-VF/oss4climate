import pandas as pd
import typesense
import typesense.exceptions
from tqdm import tqdm

from oss4climate.src.config import SETTINGS

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

try:
    client.collections.create(repo_schemas)

except typesense.exceptions.ObjectAlreadyExists:
    pass

if False:
    df = pd.read_feather(
        SETTINGS.get_listing_file_with_readme_and_description_file_columns()[0]
    )
    df["idx"] = df.index.to_series().astype(int)

    for __, r in tqdm(df.iterrows()):
        client.collections["projects"].documents.import_(
            [{k: r[k] for k in ["idx", "name", "description", "language", "url"]}]
        )

# ==============================================================================
# Search examples
# ==============================================================================
from typesense.types.document import (
    SearchParameters,
)

QUERY = "forecast of solar PV production"

results = client.collections[
    "projects"
].documents.search(
    SearchParameters(
        q=QUERY,
        query_by="embedding_description, name",
        # For hybrid search
        # rerank_hybrid_matches=True,
        vector_query="embedding_description:([], k: 200)",  # Here, reduce the relevant fields
        # sort_by="idx:asc",
        exclude_fields="embedding_description",
        per_page=20,
        page=1,
    )
)


for r in results["hits"]:
    print(r["document"])

print(
    f"""Found {len(results["hits"])} / {results["found"]} relevant //  out of {results["out_of"]}"""
)

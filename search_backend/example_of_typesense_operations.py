import typesense
import typesense.exceptions

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

# Just checking that
try:
    from httpx import get

    x = get("http://localhost:8108/debug", headers={"X-TYPESENSE-API-KEY": API_KEY})
    x.raise_for_status()
except Exception:
    raise RuntimeError("Typesense isn't running as intended")

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

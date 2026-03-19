import pandas as pd
import typesense
import typesense.exceptions
from pydantic import BaseModel
from tqdm import tqdm
from typesense.types.document import (
    SearchParameters,
)

from oss4climate.src.config import SETTINGS

_TYPESENSE_EMBEDDING_MODEL = "ts/all-MiniLM-L12-v2"

_TYPESENSE_REPO_SCHEMA = {
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
                "model_config": {"model_name": _TYPESENSE_EMBEDDING_MODEL},
            },
        },
        {"name": "readme", "type": "string"},
        {
            "name": "embedding_readme",
            "type": "float[]",
            "embed": {
                "from": ["readme"],
                "model_config": {"model_name": _TYPESENSE_EMBEDDING_MODEL},
            },
        },
        {"name": "language", "type": "string"},
        {"name": "url", "type": "string"},
        # TODO : add hints from the README files (just need to compress key information well enough there)
    ],
    "default_sorting_field": "idx",
}


_TYPESENSE_CLIENT = typesense.Client(
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


def reset_typesense_schema():
    # Delete the collection
    try:
        print("First deleting all projects")
        _TYPESENSE_CLIENT.collections["projects"].delete()
        print("Delete completed")
    except typesense.exceptions.ObjectNotFound:
        print("No projects defined")
    print(" ")
    print("Then recreating collections")
    try:
        _TYPESENSE_CLIENT.collections.create(_TYPESENSE_REPO_SCHEMA)

    except typesense.exceptions.ObjectAlreadyExists:
        pass


def index_data_in_typesense(df: pd.DataFrame) -> None:
    [
        _TYPESENSE_CLIENT.collections["projects"].documents.import_(
            [
                {
                    k: r[k]
                    for k in ["idx", "name", "description", "language", "url", "readme"]
                }
            ]
        )
        for __, r in tqdm(df.iterrows())
    ]


class _ResultItem(BaseModel):
    name: str
    description: str
    language: str | None = None
    url: str
    readme: str


class SearchResult(BaseModel):
    page: int
    total_results: int
    results: list[_ResultItem]


def search_in_typesense(
    query: str, results_per_page: int = 50, page: int = 1
) -> SearchResult:
    r = _TYPESENSE_CLIENT.collections[
        "projects"
    ].documents.search(
        SearchParameters(
            q=query,
            query_by="description, embedding_readme, name",
            # For hybrid search
            # rerank_hybrid_matches=True,
            vector_query="embedding_readme:([], k: 200)",  # Here, reduce the relevant fields
            # sort_by="idx:asc",
            exclude_fields=["embedding_description", "embedding_readme"],
            per_page=results_per_page,
            page=page,
        )
    )
    return SearchResult(
        page=r["page"],
        total_results=r["found"],
        results=[_ResultItem(**i["document"]) for i in r["hits"]],
    )


if __name__ == "__main__":
    r = search_in_typesense("wind power")
    print(r)

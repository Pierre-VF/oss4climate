from datetime import date, datetime

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


class ResultItem(BaseModel):
    name: str
    organisation: str
    license: str = "?"
    description: str
    language: str | None = None
    url: str
    readme: str
    _last_commit: int
    is_fork: bool = False

    @property
    def last_commit(self) -> date:
        return datetime.fromtimestamp(self._last_commit).date()

    # Remaining options: id;website;license_url;latest_update;all_languages;open_pull_requests;master_branch;is_fork;forked_from;readme_type


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
        {"name": "organisation", "type": "string"},
        {"name": "license", "type": "string"},
        {"name": "language", "type": "string"},
        {"name": "url", "type": "string"},
        {"name": "_last_commit", "type": "int64"},  # date is not supported by TypeSense
        {"name": "is_fork", "type": "bool"},
        # TODO : add hints from the README files (just need to compress key information well enough there)
    ],
    "default_sorting_field": "idx",
}
_TYPESENSE_REPO_SCHEMA_FIELDS = [
    i["name"]
    for i in _TYPESENSE_REPO_SCHEMA["fields"]
    if not i["name"].startswith("embedding_")
]


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


def _date_to_timestamp(x: date | None) -> int:
    if x is None:
        return 0  # TODO: find a better placeholder
    return int(datetime(x.year, x.month, x.day).timestamp())


def index_data_in_typesense(df: pd.DataFrame) -> None:
    if "_last_commit" not in df.columns:
        df["_last_commit"] = df["last_commit"].apply(_date_to_timestamp)

    [
        _TYPESENSE_CLIENT.collections["projects"].documents.import_(
            [
                {k: r[k] for k in _TYPESENSE_REPO_SCHEMA_FIELDS}
                | {
                    "readme": r["readme"][:3000]
                }  # Cutting the readme for RAM preservation
            ]
        )
        for __, r in tqdm(df.iterrows())
    ]


class SearchResult(BaseModel):
    page: int
    total_results: int
    results: list[ResultItem]


def search_in_typesense(
    query: str | None,
    results_per_page: int = 50,
    page: int = 1,
    languages: list[str] | str | None = None,
) -> SearchResult:
    if query is None:
        query = " "  # TODO: make this better

    kwargs_search = dict()
    if languages:
        if isinstance(languages, str):
            languages = [languages]
        kwargs_search["filter_by"] = f"language: [{','.join(languages)}]"

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
            **kwargs_search,
        )
    )
    return SearchResult(
        page=r["page"],
        total_results=r["found"],
        results=[ResultItem(**i["document"]) for i in r["hits"]],
    )


if __name__ == "__main__":
    r = search_in_typesense("wind power")
    print(r)

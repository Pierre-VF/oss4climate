from datetime import date, datetime
from enum import Enum

import pandas as pd
import typesense
import typesense.exceptions
from oss4climate.src.config import SETTINGS
from pydantic import BaseModel
from tqdm import tqdm
from typesense.types.document import (
    SearchParameters,
)

_TYPESENSE_EMBEDDING_MODEL = "ts/all-MiniLM-L12-v2"


class ResultItem(BaseModel):
    name: str
    organisation: str
    license: str = "?"
    description: str
    language: str | None = None
    url: str
    readme: str
    last_commit_timestamp: int
    is_fork: bool = False

    def last_commit_as_date(self) -> date:
        return datetime.fromtimestamp(self.last_commit_timestamp).date()

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
        {"name": "organisation", "type": "string", "facet": True},
        {"name": "license", "type": "string", "facet": True},
        {"name": "language", "type": "string", "facet": True},
        {"name": "url", "type": "string"},
        {
            "name": "last_commit_timestamp",
            "type": "int64",
        },  # date is not supported by TypeSense
        {"name": "is_fork", "type": "bool", "facet": True},
        # TODO : add hints from the README files (just need to compress key information well enough there)
    ],
    "default_sorting_field": "idx",
}
_TYPESENSE_REPO_SCHEMA_FIELDS = [
    i["name"]
    for i in _TYPESENSE_REPO_SCHEMA["fields"]
    if not i["name"].startswith("embedding_")
]


def generate_client() -> typesense.Client:
    return typesense.Client(
        {
            "nodes": [SETTINGS.typesense_config],
            "api_key": SETTINGS.TYPESENSE_API_KEY,
            "connection_timeout_seconds": SETTINGS.TYPESENSE_CONNECTION_TIMEOUT,
        }
    )


def reset_typesense_schema(ts_client: typesense.Client):
    # Delete the collection
    try:
        print("First deleting all projects")
        ts_client.collections["projects"].delete()
        print("Delete completed")
    except typesense.exceptions.ObjectNotFound:
        print("No projects defined")
    print(" ")
    print("Then recreating collections")
    try:
        ts_client.collections.create(_TYPESENSE_REPO_SCHEMA)

    except typesense.exceptions.ObjectAlreadyExists:
        pass


def _date_to_timestamp(x: date | None) -> int:
    if x is None:
        return 0  # TODO: find a better placeholder
    return int(datetime(x.year, x.month, x.day).timestamp())


def index_data_in_typesense(ts_client: typesense.Client, df: pd.DataFrame) -> None:
    if "last_commit_timestamp" not in df.columns:
        df["last_commit_timestamp"] = df["last_commit"].apply(_date_to_timestamp)

    [
        ts_client.collections["projects"].documents.import_(
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


def search_for_url(ts_client: typesense.Client, url: str) -> SearchResult:
    results_per_page = 5  # Just to highlight that several results are found
    page = 1
    r = ts_client.collections["projects"].documents.search(
        SearchParameters(
            q=url,
            query_by="url",
            # For hybrid search
            # rerank_hybrid_matches=True,
            # vector_query="embedding_readme:([], k: 200)",  # Here, reduce the relevant fields
            # sort_by="idx:asc",
            exclude_fields=["embedding_description", "embedding_readme"],
            per_page=results_per_page,
            page=page,
        )
    )
    return SearchResult(
        page=r["page"],
        total_results=r["found"],
        results=[ResultItem(**i["document"]) for i in r["hits"]],
    )


def search_with_query(
    ts_client: typesense.Client,
    query: str | None,
    results_per_page: int = 50,
    page: int = 1,
    languages: list[str] | str | None = None,
) -> SearchResult:
    if query is None:
        query = " "  # TODO: make this better

    # Handling wildcards
    if languages == "*":
        languages = None

    kwargs_search = dict()
    if languages:
        if isinstance(languages, str):
            languages = [languages]
        kwargs_search["filter_by"] = f"language: [{','.join(languages)}]"

    # Enable hybrid search only if used in settings
    query_by = "name, organisation, description, readme"
    if SETTINGS.ENABLE_HYBRID_SEARCH:
        query_by = f"{query_by}, embedding_readme"

    r = ts_client.collections["projects"].documents.search(
        SearchParameters(
            q=query,
            query_by=query_by,
            # For hybrid search
            # rerank_hybrid_matches=True,
            # vector_query="embedding_readme:([], k: 200)",  # Here, reduce the relevant fields
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


class CountableFieldsEnum(Enum):
    license = "license"
    language = "language"
    organisation = "organisation"


def count_values(ts_client: typesense.Client, field: CountableFieldsEnum) -> pd.Series:
    x_field = field.value
    # Facet on "type_id" with a wildcard query
    search_params = {
        "q": "*",  # Match all documents
        "facet_by": x_field,  # Facet on the field you want
        "max_facet_values": 250,  # Increase if you expect many unique values
    }
    results = ts_client.collections["projects"].documents.search(search_params)
    d = {
        facet["value"]: facet["count"] for facet in results["facet_counts"][0]["counts"]
    }
    return pd.Series(d)


def list_values(ts_client: typesense.Client, field: CountableFieldsEnum) -> list[str]:
    return count_values(ts_client, field).index.to_list()


if __name__ == "__main__":
    ts_client = generate_client()
    c1 = list_values(ts_client, CountableFieldsEnum.license)
    c2 = list_values(ts_client, CountableFieldsEnum.language)

    r = search_with_query(ts_client, "wind power")  # , languages="C++")
    print(r)

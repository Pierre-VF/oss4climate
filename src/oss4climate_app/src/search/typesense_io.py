from datetime import date, datetime
from enum import Enum

import numpy as np
import pandas as pd
import typesense
import typesense.exceptions
from pydantic import BaseModel
from typesense.types.document import (
    SearchParameters,
)

from oss4climate.src.config import SETTINGS
from oss4climate.src.helpers import split_list_in_list_of_batches
from oss4climate.src.log import log_info

_TYPESENSE_EMBEDDING_MODEL = "ts/all-MiniLM-L12-v2"


class ResultItem(BaseModel):
    name: str
    organisation_id: str | None = None
    licence: str = "?"
    description: str
    language: str | None = None
    url: str
    readme: str
    last_commit_timestamp: int | None
    is_fork: bool | None = None

    def last_commit_as_date(self) -> date | None:
        if self.last_commit_timestamp is None:
            return None
        return datetime.fromtimestamp(self.last_commit_timestamp).date()

    # Remaining options: id;website;licence_url;latest_update;all_languages;open_pull_requests;master_branch;is_fork;forked_from;readme_type


_TYPESENSE_REPO_SCHEMA = {
    "name": "projects",
    "fields": [
        {"name": "idx", "type": "string"},
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
        {"name": "readme", "type": "string", "optional": True},
        {
            "name": "embedding_readme",
            "type": "float[]",
            "embed": {
                "from": ["readme"],
                "model_config": {"model_name": _TYPESENSE_EMBEDDING_MODEL},
            },
            "optional": True,
        },
        {"name": "organisation_id", "type": "string", "facet": True, "optional": True},
        {"name": "licence", "type": "string", "facet": True, "optional": True},
        {"name": "language", "type": "string", "facet": True, "optional": True},
        {"name": "url", "type": "string", "optional": True},
        {
            "name": "last_commit_timestamp",
            "type": "int64",
            "optional": True,
        },  # date is not supported by TypeSense
        {"name": "is_fork", "type": "bool", "facet": True, "optional": True},
        {"name": "high_quality", "type": "bool", "facet": True, "optional": True},
        # TODO : add hints from the README files (just need to compress key information well enough there)
    ],
    # "default_sorting_field": "idx",
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
        log_info("First deleting all projects")
        ts_client.collections["projects"].delete()
        log_info("Delete completed")
    except typesense.exceptions.ObjectNotFound:
        log_info("No projects defined")
    log_info(" ")
    log_info("Then recreating collections")
    try:
        ts_client.collections.create(_TYPESENSE_REPO_SCHEMA)

    except typesense.exceptions.ObjectAlreadyExists:
        pass


def _date_to_timestamp(x: date | str | float | None) -> int | None:
    if x is None:
        return 0  # TODO: find a better placeholder
    if isinstance(x, float):
        try:
            return int(x)
        except ValueError:
            return 0
    if isinstance(x, str):
        x = datetime.fromisoformat(x)
    return int(datetime(x.year, x.month, x.day).timestamp())


def _boolean_fix(x):
    if isinstance(x, bool | None):
        return x
    elif isinstance(x, int | float):
        if x == 0:
            return False
        elif x == 1:
            return True
    return None


def _to_native_python(obj) -> object:
    """Recursively convert pandas/numpy NA and NaN to Python None."""

    def _convert(v):
        if pd.isna(v):
            return None
        if isinstance(v, (np.floating, np.integer)):
            return int(v) if isinstance(v, np.integer) else float(v)
        return v

    if isinstance(obj, dict):
        return {k: _convert(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        converted = [_convert(item) for item in obj]
        return type(obj)(converted)  # preserve tuple type
    return _convert(obj)


def index_data_in_typesense(
    ts_client: typesense.Client,
    df: pd.DataFrame,
    batch_size: int = 10,
) -> None:
    if "high_quality" not in df.columns:
        df["high_quality"] = True
    if "last_commit_timestamp" not in df.columns:
        df["last_commit_timestamp"] = df["last_commit"].apply(_date_to_timestamp)

    # Fix the booleans
    df["is_fork"] = df["is_fork"].apply(_boolean_fix)
    subset = ["description", "readme"]
    if "last_scraped_at" in df.columns:
        subset.append("last_scraped_at")
    df = df.dropna(
        subset=subset,
        how="all",
    )

    docs = [
        _to_native_python({k: r.get(k) for k in _TYPESENSE_REPO_SCHEMA_FIELDS})
        for __, r in df.iterrows()
    ]
    full_res = []
    for b in split_list_in_list_of_batches(docs, batch_size=batch_size):
        res = ts_client.collections["projects"].documents.import_(b)
        if all([not i.get("success") for i in res]):
            raise ValueError(
                f"Failed to index data in Typesense : issue example {res[0]}"
            )
        full_res += res

    log_info(
        f"Indexed {len([i for i in full_res if i.get('success')])} documents and failed on {len([i for i in full_res if not i.get('success')])}"
    )


class SearchResult(BaseModel):
    page: int
    total_results: int
    results: list[ResultItem]


def _search_kwargs(
    languages: list[str] | str | None = None,
    licence_category: str | None = None,
    high_quality_only: bool = True,
) -> dict[str, str]:
    kwargs_search = dict()
    filter_by = []
    if languages not in [None, "*"]:
        if isinstance(languages, str):
            languages = [languages]
        filter_by.append(f"language: [{','.join(languages)}]")
    if licence_category not in [None, "*"]:
        # TODO: this needs to be better aligned with actual usages
        licences = licence_category.split(",")
        filter_by.append(f"licence: [{','.join(licences)}]")
    if high_quality_only:
        filter_by.append("high_quality := true")

    if filter_by:
        kwargs_search["filter_by"] = " && ".join(filter_by)
    return kwargs_search


def search_for_url(
    ts_client: typesense.Client,
    url: str,
    high_quality_only: bool = True,
) -> SearchResult:
    results_per_page = 5  # Just to highlight that several results are found
    page = 1
    r = ts_client.collections["projects"].documents.search(
        SearchParameters(
            q=url,
            query_by="url",
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
    query: str = "*",
    results_per_page: int = 50,
    page: int = 1,
    languages: list[str] | str | None = None,
    licence_category: str | None = None,
    high_quality_only: bool = True,
) -> SearchResult:
    if query is None:
        query = " "

    # Keyword search with field weights: name > organisation_id > description > readme.
    # This ensures title matches rank highest, followed by organisation_id,
    # then description, and finally the full readme text.
    keyword_fields = "name, organisation_id, description, readme"
    keyword_weights = [5, 4, 3, 2]
    hybrid_params: dict[str, str | bool] = {}
    use_hybrid = SETTINGS.ENABLE_HYBRID_SEARCH
    if use_hybrid:
        keyword_fields = f"{keyword_fields}, embedding_readme"
        keyword_weights = [*keyword_weights, 1]
        hybrid_params = {
            "rerank_hybrid_matches": True,
            "vector_query": "embedding_description:([], k: 100)",
        }

    s_kwargs = _search_kwargs(
        languages=languages,
        licence_category=licence_category,
        high_quality_only=high_quality_only,
    )

    try:
        r = ts_client.collections["projects"].documents.search(
            SearchParameters(
                q=query,
                query_by=keyword_fields,
                query_by_weights=keyword_weights,
                prefix=True,
                typo_tolerance="true",
                exclude_fields=["embedding_description", "embedding_readme"],
                per_page=results_per_page,
                page=page,
                **s_kwargs,
                **hybrid_params,
            )
        )
    except typesense.exceptions.RequestMalformed as e:
        # Hybrid search failed (e.g. embeddings not yet generated).
        # Fall back to keyword-only search.
        if use_hybrid:
            keyword_fields = "name, organisation_id, description, readme"
            keyword_weights = [5, 4, 3, 2]
            hybrid_params = {}
            r = ts_client.collections["projects"].documents.search(
                SearchParameters(
                    q=query,
                    query_by=keyword_fields,
                    query_by_weights=keyword_weights,
                    prefix=True,
                    typo_tolerance="true",
                    exclude_fields=["embedding_description", "embedding_readme"],
                    per_page=results_per_page,
                    page=page,
                    **s_kwargs,
                )
            )
        else:
            raise RuntimeError("Failed Typesense query") from e

    return SearchResult(
        page=r["page"],
        total_results=r["found"],
        results=[ResultItem(**i["document"]) for i in r["hits"]],
    )


class CountableFieldsEnum(Enum):
    licence = "licence"
    language = "language"
    organisation = "organisation_id"


def count_values(
    ts_client: typesense.Client,
    field: CountableFieldsEnum,
    high_quality_only: bool = True,
) -> pd.Series:
    x_field = field.value
    # Facet on "type_id" with a wildcard query
    search_params = {
        "q": "*",  # Match all documents
        "facet_by": x_field,  # Facet on the field you want
        "max_facet_values": 250,  # Increase if you expect many unique values
    } | _search_kwargs(
        high_quality_only=high_quality_only,
    )
    results = ts_client.collections["projects"].documents.search(search_params)
    d = {
        facet["value"]: facet["count"] for facet in results["facet_counts"][0]["counts"]
    }
    return pd.Series(d)


def list_values(
    ts_client: typesense.Client,
    field: CountableFieldsEnum,
    high_quality_only: bool = True,
) -> list[str]:
    return count_values(
        ts_client, field, high_quality_only=high_quality_only
    ).index.to_list()


if __name__ == "__main__":
    ts_client = generate_client()
    c1 = list_values(ts_client, CountableFieldsEnum.licence)
    c2 = list_values(ts_client, CountableFieldsEnum.language)

    r = search_with_query(ts_client, "wind power")  # , languages="C++")
    log_info(r)

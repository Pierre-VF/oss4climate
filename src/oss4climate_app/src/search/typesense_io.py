from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

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
    last_commit_timestamp: int
    is_fork: bool = False
    website: str | None = None
    license_url: str | None = None
    latest_update: date | None = None
    open_pull_requests: int | None = None
    master_branch: str | None = None
    forked_from: str | None = None
    readme_type: str | None = None
    high_quality: bool = True

    def last_commit_as_date(self) -> date:
        return datetime.fromtimestamp(self.last_commit_timestamp).date()


# Enhanced Typesense schema with improved search capabilities
_TYPESENSE_REPO_SCHEMA = {
    "name": "projects",
    "fields": [
        {"name": "idx", "type": "int32"},
        {
            "name": "name",
            "type": "string",
            "index": True,
            "sort": True,
            "optional": False,
        },
        {
            "name": "organisation",
            "type": "string",
            "facet": True,
            "index": True,
            "sort": True,
        },
        {
            "name": "description",
            "type": "string",
            "index": True,
            "optional": True,
            "infix": True,  # Enable infix search for partial matches
            "min_infix_len": 3,  # Minimum length for infix matching
        },
        {
            "name": "embedding_description",
            "type": "float[]",
            "embed": {
                "from": ["description"],
                "model_config": {"model_name": _TYPESENSE_EMBEDDING_MODEL},
            },
        },
        {
            "name": "readme",
            "type": "string",
            "index": True,
            "optional": True,
            "infix": True,
            "min_infix_len": 3,
        },
        {
            "name": "embedding_readme",
            "type": "float[]",
            "embed": {
                "from": ["readme"],
                "model_config": {"model_name": _TYPESENSE_EMBEDDING_MODEL},
            },
        },
        {
            "name": "url",
            "type": "string",
            "index": True,
            "sort": True,
        },
        {
            "name": "website",
            "type": "string",
            "index": True,
            "optional": True,
        },
        {
            "name": "license",
            "type": "string",
            "facet": True,
            "index": True,
        },
        {
            "name": "license_url",
            "type": "string",
            "index": True,
            "optional": True,
        },
        {
            "name": "language",
            "type": "string",
            "facet": True,
            "index": True,
        },
        {
            "name": "all_languages",
            "type": "string[]",
            "facet": True,
            "index": True,
            "optional": True,
        },
        {
            "name": "last_commit_timestamp",
            "type": "int64",
        },
        {
            "name": "latest_update",
            "type": "int64",
            "index": True,
            "optional": True,
        },
        {"name": "is_fork", "type": "bool", "facet": True},
        {"name": "forked_from", "type": "string", "index": True, "optional": True},
        {"name": "high_quality", "type": "bool", "facet": True},
        {
            "name": "open_pull_requests",
            "type": "int32",
            "index": True,
            "optional": True,
        },
        {"name": "master_branch", "type": "string", "index": True, "optional": True},
        {
            "name": "readme_type",
            "type": "string",
            "facet": True,
            "index": True,
            "optional": True,
        },
        {
            "name": "search_text",
            "type": "string",
            "index": True,
            "optional": True,
            "infix": True,
            "min_infix_len": 2,
        },
    ],
    "default_sorting_field": "idx",
    "token_separators": [" ", "-", "_", ".", "/", "\\", "@"],
    "symbols_to_index": ["+", "#", "@", "$", "%", "&", "*", "=", "!", "?"],
    "symbols_to_skip": [
        "'",
        '"',
        ",",
        ";",
        ":",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        "<",
        ">",
    ],
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


def _create_search_text(row: pd.Series) -> str:
    """
    Create a combined search text field for better full-text search
    """
    parts = []

    # Add name and organisation (high weight)
    if pd.notna(row.get("name")):
        parts.append(
            f"{row['name']} {row['name']} {row['name']}"
        )  # Boost name importance
    if pd.notna(row.get("organisation")):
        parts.append(
            f"{row['organisation']} {row['organisation']}"
        )  # Boost organisation importance

    # Add description
    if pd.notna(row.get("description")):
        parts.append(row["description"])

    # Add readme (truncated)
    if pd.notna(row.get("readme")):
        readme = str(row["readme"])[:2000]  # Limit readme size
        parts.append(readme)

    # Add other text fields
    if pd.notna(row.get("license")):
        parts.append(row["license"])
    if pd.notna(row.get("language")):
        parts.append(row["language"])
    if pd.notna(row.get("website")):
        parts.append(row["website"])

    return " ".join(parts)


def _process_all_languages(languages_str: str | None) -> list[str] | None:
    """Convert language string to list of languages"""
    if pd.isna(languages_str) or not languages_str or languages_str == "?":
        return None
    # Handle comma-separated or space-separated languages
    languages = [
        lang.strip()
        for lang in str(languages_str).replace(",", " ").split()
        if lang.strip()
    ]
    return languages if languages else None


def index_data_in_typesense(ts_client: typesense.Client, df: pd.DataFrame) -> None:
    if "high_quality" not in df.columns:
        df["high_quality"] = True
    if "last_commit_timestamp" not in df.columns:
        df["last_commit_timestamp"] = df["last_commit"].apply(_date_to_timestamp)

    # Add latest_update timestamp if available
    if "latest_update" in df.columns and "latest_update_timestamp" not in df.columns:
        df["latest_update_timestamp"] = df["latest_update"].apply(_date_to_timestamp)

    # Create search_text field for better full-text search
    df["search_text"] = df.apply(_create_search_text, axis=1)

    # Process all_languages field
    if "all_languages" in df.columns:
        df["all_languages"] = df["all_languages"].apply(_process_all_languages)
    elif "language" in df.columns:
        # Create all_languages from language field
        df["all_languages"] = df["language"].apply(
            lambda x: [x] if pd.notna(x) and x != "?" else None
        )

    # Prepare documents for indexing
    documents = []
    for _, r in tqdm(df.iterrows(), desc="Indexing documents"):
        doc = {k: r[k] for k in _TYPESENSE_REPO_SCHEMA_FIELDS if k in r.index}

        # Handle readme truncation for RAM preservation
        if "readme" in doc:
            doc["readme"] = str(doc["readme"])[:3000]

        # Handle optional fields that might be NaN
        for field in [
            "website",
            "license_url",
            "forked_from",
            "master_branch",
            "readme_type",
        ]:
            if field in doc and pd.isna(doc[field]):
                doc[field] = None

        # Handle numeric fields that might be NaN
        for field in ["open_pull_requests", "latest_update_timestamp"]:
            if field in doc and pd.isna(doc[field]):
                doc[field] = None

        documents.append(doc)

    # Batch import for better performance
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        ts_client.collections["projects"].documents.import_(batch)


class SearchResult(BaseModel):
    page: int
    total_results: int
    results: list[ResultItem]
    facets: dict[str, Any] | None = None


class SearchOptions(BaseModel):
    """Advanced search options"""

    query: str = "*"
    results_per_page: int = 50
    page: int = 1
    languages: list[str] | str | None = None
    license_category: str | None = None
    high_quality_only: bool = True

    # Advanced search options
    use_fuzzy_search: bool = False
    fuzzy_prefix_length: int = 3
    max_edit_distance: int = 2  # For fuzzy search
    use_prefix_search: bool = True
    use_infix_search: bool = True
    use_hybrid_search: bool = False
    hybrid_alpha: float = 0.5  # Weight for vector search (0-1)
    sort_by: str | None = None
    sort_order: str = "desc"

    # Filter options
    exclude_forks: bool = False
    exclude_inactive: bool = False
    min_last_commit_days: int | None = None

    # Faceting options
    facet_by: list[str] | None = None
    max_facet_values: int = 100


def _search_kwargs(
    languages: list[str] | str | None = None,
    license_category: str | None = None,
    high_quality_only: bool = True,
    exclude_forks: bool = False,
    exclude_inactive: bool = False,
    min_last_commit_days: int | None = None,
) -> dict[str, str]:
    kwargs_search = dict()
    filter_by = []

    # Language filtering
    if languages not in [None, "*"]:
        if isinstance(languages, str):
            languages = [languages]
        # Support both single language and array of languages
        if len(languages) == 1:
            filter_by.append(f"language:={languages[0]}")
        else:
            filter_by.append(f"language: [{','.join(languages)}]")

        # Also filter by all_languages if it exists
        filter_by.append(f"all_languages: [{','.join(languages)}]")

    # License filtering
    if license_category not in [None, "*"]:
        # TODO: this needs to be better aligned with actual usages
        licenses = license_category.split(",")
        filter_by.append(f"license: [{','.join(licenses)}]")

    # Quality filtering
    if high_quality_only:
        filter_by.append("high_quality := true")

    # Exclude forks
    if exclude_forks:
        filter_by.append("is_fork := false")

    # Exclude inactive projects
    if exclude_inactive or min_last_commit_days is not None:
        if min_last_commit_days is None:
            min_last_commit_days = 365  # Default: 1 year
        min_timestamp = int(
            (datetime.now() - timedelta(days=min_last_commit_days)).timestamp()
        )
        filter_by.append(f"last_commit_timestamp:>={min_timestamp}")

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
    s_kwargs = _search_kwargs(high_quality_only=high_quality_only)

    r = ts_client.collections["projects"].documents.search(
        SearchParameters(
            q=url,
            query_by="url",
            exclude_fields=["embedding_description", "embedding_readme", "search_text"],
            per_page=results_per_page,
            page=page,
            **s_kwargs,
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
    license_category: str | None = None,
    high_quality_only: bool = True,
    use_fuzzy_search: bool = False,
    max_edit_distance: int = 2,
    use_hybrid_search: bool | None = None,
    hybrid_alpha: float = 0.5,
    sort_by: str | None = None,
    sort_order: str = "desc",
    exclude_forks: bool = False,
    exclude_inactive: bool = False,
    min_last_commit_days: int | None = None,
    facet_by: list[str] | None = None,
    max_facet_values: int = 100,
) -> SearchResult:
    """
    Perform a search with advanced options

    Args:
        ts_client: Typesense client
        query: Search query string
        results_per_page: Number of results per page
        page: Page number
        languages: Language filter
        license_category: License category filter
        high_quality_only: Only search high quality repositories
        use_fuzzy_search: Enable fuzzy search for typo tolerance
        max_edit_distance: Maximum edit distance for fuzzy search
        use_hybrid_search: Enable hybrid search (keyword + vector). If None, uses SETTINGS.ENABLE_HYBRID_SEARCH
        hybrid_alpha: Weight for vector search in hybrid mode (0-1)
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        exclude_forks: Exclude forked repositories
        exclude_inactive: Exclude inactive repositories
        min_last_commit_days: Minimum days since last commit
        facet_by: Fields to facet by
        max_facet_values: Maximum number of facet values to return

    Returns:
        SearchResult with results and optional facets
    """
    if query is None:
        query = " "

    # Use settings for hybrid search if not explicitly set
    if use_hybrid_search is None:
        use_hybrid_search = SETTINGS.ENABLE_HYBRID_SEARCH

    # Build query_by fields - prioritize name and organisation for better relevance
    query_by_fields = ["name", "organisation"]

    # Add description and readme for full-text search
    query_by_fields.extend(["description", "readme"])

    # Add search_text for comprehensive search
    query_by_fields.append("search_text")

    query_by = ", ".join(query_by_fields)

    # For hybrid search, add vector fields
    if use_hybrid_search:
        query_by += ", embedding_description, embedding_readme"

    s_kwargs = _search_kwargs(
        languages=languages,
        license_category=license_category,
        high_quality_only=high_quality_only,
        exclude_forks=exclude_forks,
        exclude_inactive=exclude_inactive,
        min_last_commit_days=min_last_commit_days,
    )

    # Add fuzzy search options
    if use_fuzzy_search:
        s_kwargs["fuzzy"] = True
        s_kwargs["max_edit_distance"] = max_edit_distance

    # Add prefix search for better partial matching
    s_kwargs["prefix"] = True

    # Add sorting
    if sort_by:
        sort_field = sort_by
        if sort_order == "desc":
            sort_field = f"{sort_by}:desc"
        else:
            sort_field = f"{sort_by}:asc"
        s_kwargs["sort_by"] = sort_field

    # Add faceting
    if facet_by:
        s_kwargs["facet_by"] = facet_by
        s_kwargs["max_facet_values"] = max_facet_values

    # Build search parameters
    search_params = {
        "q": query,
        "query_by": query_by,
        "exclude_fields": ["embedding_description", "embedding_readme"],
        "per_page": results_per_page,
        "page": page,
        **s_kwargs,
    }

    # For hybrid search, we need to use vector_query parameter
    if use_hybrid_search:
        search_params["vector_query"] = (
            f"embedding_readme:([{query}], k: {int(hybrid_alpha * 100)})"
        )
        # Enable hybrid reranking
        search_params["rerank_hybrid_matches"] = True
        # Adjust scoring to give more weight to exact matches
        search_params["score_fields"] = {
            "name": 3.0,  # Higher weight for name matches
            "organisation": 2.5,  # Higher weight for organisation matches
            "description": 1.5,
            "readme": 1.0,
            "search_text": 1.0,
        }
    else:
        # For non-hybrid search, use traditional scoring
        search_params["score_fields"] = {
            "name": 3.0,
            "organisation": 2.5,
            "description": 1.5,
            "readme": 1.0,
            "search_text": 1.0,
        }

    r = ts_client.collections["projects"].documents.search(search_params)

    # Extract facets if requested
    facets = None
    if facet_by and "facet_counts" in r:
        facets = {}
        for facet_result in r["facet_counts"]:
            field_name = facet_result["field_name"]
            facets[field_name] = {
                "counts": [
                    {"value": count["value"], "count": count["count"]}
                    for count in facet_result["counts"]
                ]
            }

    return SearchResult(
        page=r["page"],
        total_results=r["found"],
        results=[ResultItem(**i["document"]) for i in r["hits"]],
        facets=facets,
    )


class CountableFieldsEnum(Enum):
    license = "license"
    language = "language"
    organisation = "organisation"


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


def autocomplete(
    ts_client: typesense.Client,
    query: str,
    query_by: list[str] = ["name", "organisation", "description"],
    limit: int = 10,
    high_quality_only: bool = True,
) -> list[str]:
    """
    Get autocomplete suggestions for a search query

    Args:
        ts_client: Typesense client
        query: Partial query string
        query_by: Fields to search for autocomplete
        limit: Maximum number of suggestions to return
        high_quality_only: Only suggest from high quality repositories

    Returns:
        List of autocomplete suggestions
    """
    if not query or query.strip() == "":
        return []

    query = query.strip()

    s_kwargs = _search_kwargs(high_quality_only=high_quality_only)

    r = ts_client.collections["projects"].documents.search(
        {
            "q": query,
            "query_by": ", ".join(query_by),
            "per_page": limit,
            "prefix": True,  # Enable prefix matching for autocomplete
            "drop_tokens_threshold": 1,  # Drop tokens to get more results
            **s_kwargs,
        }
    )

    suggestions = []
    for hit in r["hits"]:
        doc = hit["document"]
        # Extract the most relevant field that matched
        if "name" in doc and query.lower() in doc["name"].lower():
            suggestions.append(doc["name"])
        elif "organisation" in doc and query.lower() in doc["organisation"].lower():
            suggestions.append(doc["organisation"])
        elif "description" in doc and query.lower() in doc["description"].lower():
            # Extract a relevant snippet from description
            desc = doc["description"]
            idx = desc.lower().find(query.lower())
            if idx != -1:
                start = max(0, idx - 20)
                end = min(len(desc), idx + len(query) + 20)
                suggestions.append(desc[start:end] + "...")

    # Remove duplicates and limit
    suggestions = list(dict.fromkeys(suggestions))[:limit]
    return suggestions


def get_search_suggestions(
    ts_client: typesense.Client,
    query: str,
    limit: int = 5,
    high_quality_only: bool = True,
) -> list[dict[str, str]]:
    """
    Get search suggestions with more context

    Args:
        ts_client: Typesense client
        query: Search query
        limit: Maximum number of suggestions
        high_quality_only: Only suggest from high quality repositories

    Returns:
        List of suggestion dictionaries with name, organisation, and url
    """
    if not query or query.strip() == "":
        return []

    query = query.strip()

    s_kwargs = _search_kwargs(high_quality_only=high_quality_only)

    r = ts_client.collections["projects"].documents.search(
        {
            "q": query,
            "query_by": "name,organisation,search_text",
            "per_page": limit,
            "prefix": True,
            "include_fields": "name,organisation,url,description",
            **s_kwargs,
        }
    )

    suggestions = []
    for hit in r["hits"]:
        doc = hit["document"]
        suggestion = {
            "name": doc.get("name", ""),
            "organisation": doc.get("organisation", ""),
            "url": doc.get("url", ""),
            "description": doc.get("description", "")[:100] + "..."
            if doc.get("description")
            else "",
        }
        suggestions.append(suggestion)

    return suggestions


if __name__ == "__main__":
    ts_client = generate_client()
    c1 = list_values(ts_client, CountableFieldsEnum.license)
    c2 = list_values(ts_client, CountableFieldsEnum.language)

    r = search_with_query(ts_client, "wind power")  # , languages="C++")
    print(r)

    # Test autocomplete
    suggestions = autocomplete(ts_client, "wind")
    print("Autocomplete suggestions for 'wind':", suggestions)

    # Test search suggestions
    search_suggestions = get_search_suggestions(ts_client, "solar")
    print("Search suggestions for 'solar':", search_suggestions)

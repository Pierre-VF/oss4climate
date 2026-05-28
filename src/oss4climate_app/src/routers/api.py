"""
Module containing the API code

Note: For now, only redirects
"""

from importlib.metadata import version
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate_app.src.config import URL_CODE_REPOSITORY, URL_LISTING_FEATHER
from oss4climate_app.src.data_io import (
    clear_cache,
    refresh_data,
)
from oss4climate_app.src.database import (
    dump_database_request_log_as_csv,
    dump_database_search_log_as_csv,
)
from oss4climate_app.src.routers import listing_credits_df
from oss4climate_app.src.search import typesense_io


class ForbiddenError(RuntimeError):
    pass


app = FastAPI(
    title="OSS4climate API",
    description="""
    API to access the oss4climate service. Please note that this is currently an **experimental proof-of-concept**
    so that stability is not guaranteed and that any integration with it might therefore break in case of updates.

    The service is provided without any guarantee and no liability will be accepted.
              """,
    version=version("oss4climate"),
)


@app.get("/search")
async def search(
    request: Request,
    background_tasks: BackgroundTasks,
    query: Optional[str] = None,
    extended_search: bool = False,
    languages: Optional[str] = None,
    license_category: Optional[str] = None,
    use_fuzzy_search: bool = False,
    use_hybrid_search: Optional[bool] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    exclude_forks: bool = False,
    exclude_inactive: bool = False,
    min_last_commit_days: Optional[int] = None,
    results_per_page: int = 50,
    page: int = 1,
    ts_client=Depends(typesense_io.generate_client),
) -> typesense_io.SearchResult:
    """
    Perform a search with advanced options

    Parameters:
    - query: Search query string
    - extended_search: Include lower quality results
    - languages: Comma-separated list of languages to filter by
    - license_category: License category to filter by
    - use_fuzzy_search: Enable fuzzy search for typo tolerance
    - use_hybrid_search: Enable hybrid search (keyword + vector). If None, uses server settings
    - sort_by: Field to sort by (e.g., "last_commit_timestamp", "name")
    - sort_order: Sort order ("asc" or "desc")
    - exclude_forks: Exclude forked repositories
    - exclude_inactive: Exclude inactive repositories
    - min_last_commit_days: Minimum days since last commit to include
    - results_per_page: Number of results per page
    - page: Page number
    """
    if query:
        query = query.strip().lower()
    if query is None:
        query = " "

    # Parse languages parameter
    languages_list = None
    if languages:
        languages_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
        if len(languages_list) == 1:
            languages_list = languages_list[0]  # Single language as string

    res = typesense_io.search_with_query(
        ts_client,
        query=query,
        results_per_page=results_per_page,
        page=page,
        languages=languages_list,
        license_category=license_category,
        high_quality_only=(not extended_search),
        use_fuzzy_search=use_fuzzy_search,
        use_hybrid_search=use_hybrid_search,
        sort_by=sort_by,
        sort_order=sort_order,
        exclude_forks=exclude_forks,
        exclude_inactive=exclude_inactive,
        min_last_commit_days=min_last_commit_days,
    )
    return res


@app.get("/search/advanced")
async def advanced_search(
    request: Request,
    background_tasks: BackgroundTasks,
    query: Optional[str] = None,
    extended_search: bool = False,
    languages: Optional[str] = None,
    license_category: Optional[str] = None,
    use_fuzzy_search: bool = False,
    use_hybrid_search: Optional[bool] = None,
    hybrid_alpha: float = 0.5,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    exclude_forks: bool = False,
    exclude_inactive: bool = False,
    min_last_commit_days: Optional[int] = None,
    facet_by: Optional[str] = None,
    max_facet_values: int = 100,
    results_per_page: int = 50,
    page: int = 1,
    ts_client=Depends(typesense_io.generate_client),
) -> typesense_io.SearchResult:
    """
    Perform an advanced search with faceting and more options

    This endpoint provides additional search capabilities including:
    - Hybrid search (keyword + vector)
    - Faceting for filtering
    - Advanced sorting and filtering
    """
    if query:
        query = query.strip().lower()
    if query is None:
        query = " "

    # Parse languages parameter
    languages_list = None
    if languages:
        languages_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
        if len(languages_list) == 1:
            languages_list = languages_list[0]

    # Parse facet_by parameter
    facet_by_list = None
    if facet_by:
        facet_by_list = [
            field.strip() for field in facet_by.split(",") if field.strip()
        ]

    res = typesense_io.search_with_query(
        ts_client,
        query=query,
        results_per_page=results_per_page,
        page=page,
        languages=languages_list,
        license_category=license_category,
        high_quality_only=(not extended_search),
        use_fuzzy_search=use_fuzzy_search,
        use_hybrid_search=use_hybrid_search,
        hybrid_alpha=hybrid_alpha,
        sort_by=sort_by,
        sort_order=sort_order,
        exclude_forks=exclude_forks,
        exclude_inactive=exclude_inactive,
        min_last_commit_days=min_last_commit_days,
        facet_by=facet_by_list,
        max_facet_values=max_facet_values,
    )
    return res


@app.get("/search/autocomplete")
async def search_autocomplete(
    query: str,
    limit: int = 10,
    extended_search: bool = False,
    ts_client=Depends(typesense_io.generate_client),
) -> list[str]:
    """
    Get autocomplete suggestions for a search query

    Parameters:
    - query: Partial search query
    - limit: Maximum number of suggestions to return
    - extended_search: Include suggestions from lower quality results

    Returns:
    - List of autocomplete suggestions
    """
    return typesense_io.autocomplete(
        ts_client,
        query,
        limit=limit,
        high_quality_only=(not extended_search),
    )


@app.get("/search/suggestions")
async def search_suggestions(
    query: str,
    limit: int = 5,
    extended_search: bool = False,
    ts_client=Depends(typesense_io.generate_client),
) -> list[dict[str, str]]:
    """
    Get search suggestions with context for a search query

    Parameters:
    - query: Search query
    - limit: Maximum number of suggestions to return
    - extended_search: Include suggestions from lower quality results

    Returns:
    - List of suggestion objects with name, organisation, url, and description
    """
    return typesense_io.get_search_suggestions(
        ts_client,
        query,
        limit=limit,
        high_quality_only=(not extended_search),
    )


@app.get("/code")
async def api_code():
    return RedirectResponse(URL_CODE_REPOSITORY, status_code=307)


@app.get("/data/credits")
async def data_credits():
    """
    Credits text for the data
    """
    credits_text = listing_credits_df()
    return credits_text.T.to_dict()


@app.get("/data/feather")
async def data_feather():
    """
    Redirects to the dataset in .feather format (please bear in mind the credit considerations for the source projects, see "credits" endpoint)
    """
    return RedirectResponse(URL_LISTING_FEATHER, status_code=307)


def _permission_admin(key: Optional[str] = None):
    if SETTINGS.DATA_REFRESH_KEY is None:
        raise ForbiddenError(
            "Not allowed to refresh when passkey is not set",
        )
    if key != SETTINGS.DATA_REFRESH_KEY:
        raise ForbiddenError(
            "You are not allowed to refresh the data (invalid key)",
        )


@app.get("/refresh_data")
async def _refresh_data(key: Optional[str] = None):
    try:
        _permission_admin(key)
    except ForbiddenError:
        return PlainTextResponse(
            "You are not allowed to do this",
            status_code=403,
        )
    log_info("DATA refreshing START")
    refresh_data(force_refresh=True)
    clear_cache()
    log_info("DATA refreshing END")
    return PlainTextResponse("Data was successfully refreshed")


@app.get("/download_request_metrics")
async def download_request_metrics(key: Optional[str] = None):
    try:
        _permission_admin(key)
    except ForbiddenError:
        return PlainTextResponse(
            "You are not allowed to do this",
            status_code=403,
        )
    return PlainTextResponse(dump_database_request_log_as_csv())


@app.get("/download_search_metrics")
async def download_search_metrics(key: Optional[str] = None):
    try:
        _permission_admin(key)
    except ForbiddenError:
        return PlainTextResponse(
            "You are not allowed to do this",
            status_code=403,
        )
    return PlainTextResponse(dump_database_search_log_as_csv())

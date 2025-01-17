"""
Module containing the API code

Note: For now, only redirects
"""

from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate_app.config import URL_CODE_REPOSITORY, URL_DATA_FEATHER
from oss4climate_app.src.data_io import (
    clear_cache,
    refresh_data,
    search_for_results,
)
from oss4climate_app.src.database import (
    dump_database_request_log_as_csv,
    dump_database_search_log_as_csv,
)
from oss4climate_app.src.log_activity import log_search
from oss4climate_app.src.routers import listing_credits


class ForbiddenError(RuntimeError):
    pass


app = FastAPI(
    title="OSS4climate API",
    description="""
    API to access the oss4climate service. Please note that this is currently an **experimental proof-of-concept**  
    so that stability is not guaranteed and that any integration with it might therefore break in case of updates. 

    The service is provided without any guarantee and no liability will be accepted.
              """,
)


@app.get("/search")
async def search(
    request: Request,
    background_tasks: BackgroundTasks,
    query: Optional[str] = None,
):
    if query:
        query = query.strip().lower()
    df_out = search_for_results(query)
    n_total_found = len(df_out)
    # Log results
    background_tasks.add_task(
        log_search,
        search_term=f"API:{query}",
        number_of_results=n_total_found,
        view_offset=None,
    )
    json_txt = (
        df_out.reset_index(inplace=False)
        .drop(columns=["score"])
        .T.to_json(date_format="iso", indent=None)
    )
    return PlainTextResponse(json_txt, media_type="text/json")


@app.get("/code")
async def api_code():
    return RedirectResponse(URL_CODE_REPOSITORY, status_code=307)


@app.get("/data/credits")
async def data_credits():
    """
    Credits text for the data
    """
    credits_text = listing_credits(html=False)
    return PlainTextResponse(credits_text)


@app.get("/data/credits_html")
async def data_credits_html():
    """
    Credits text for the data (HTML formatted)
    """
    credits_text = f"""<!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="utf-8">
            <title>Credits</title>
        </head>
        <body>
            <p>{listing_credits(html=True)}</p>
        </body>
    </html>"""
    return HTMLResponse(credits_text)


@app.get("/data/feather")
async def data_feather():
    """
    Redirects to the dataset in .feather format (please bear in mind the credit considerations for the source projects, see "credits" endpoint)
    """
    return RedirectResponse(URL_DATA_FEATHER, status_code=307)


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

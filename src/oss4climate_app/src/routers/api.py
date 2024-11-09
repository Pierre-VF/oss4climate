"""
Module containing the API code

Note: For now, only redirects
"""

from typing import Optional

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, RedirectResponse

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate_app.config import URL_CODE_REPOSITORY, URL_DATA_CSV, URL_DATA_FEATHER
from oss4climate_app.src.data_io import clear_cache, refresh_data
from oss4climate_app.src.database import (
    dump_database_request_log_as_csv,
    dump_database_search_log_as_csv,
)


class ForbiddenError(RuntimeError):
    pass


app = FastAPI(title="OSS4climate API")


@app.get("/code")
async def api_code():
    return RedirectResponse(URL_CODE_REPOSITORY, status_code=307)


@app.get("/data/csv")
async def data_csv():
    return RedirectResponse(URL_DATA_CSV, status_code=307)


@app.get("/data/feather")
async def data_feather():
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

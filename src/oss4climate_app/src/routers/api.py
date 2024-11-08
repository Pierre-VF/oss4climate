"""
Module containing the API code

Note: For now, only redirects
"""

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, RedirectResponse

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate_app.config import URL_CODE_REPOSITORY
from oss4climate_app.src.data_io import clear_cache, refresh_data

#
app = APIRouter()


@app.get("/code")
async def api_code():
    return RedirectResponse(URL_CODE_REPOSITORY, status_code=307)


@app.get("/data_csv")
async def api_data():
    return RedirectResponse(
        "https://data.pierrevf.consulting/oss4climate/listing_data.csv", status_code=307
    )


@app.get("/refresh_data")
async def _refresh_data(key: Optional[str] = None):
    if SETTINGS.DATA_REFRESH_KEY is None:
        return PlainTextResponse(
            "Not allowed to refresh when passkey is not set",
            status_code=403,
        )
    if key != SETTINGS.DATA_REFRESH_KEY:
        return PlainTextResponse(
            "You are not allowed to refresh the data (invalid key)",
            status_code=403,
        )
    log_info("DATA refreshing START")
    refresh_data(force_refresh=True)
    clear_cache()
    log_info("DATA refreshing END")
    return PlainTextResponse("Data was successfully refreshed")

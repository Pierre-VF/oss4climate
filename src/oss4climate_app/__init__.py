import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from tqdm import tqdm

from oss4climate.scripts import (
    FILE_OUTPUT_LISTING_FEATHER,
    listing_search,
)
from oss4climate.src.log import log_info, log_warning
from oss4climate_app.config import STATIC_FILES_PATH
from oss4climate_app.src.data_io import (
    SEARCH_ENGINE_DESCRIPTIONS,
    SEARCH_ENGINE_READMES,
    SEARCH_RESULTS,
)
from oss4climate_app.src.log_activity import log_landing
from oss4climate_app.src.routers import api, ui


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("Starting app")
    if not os.path.exists(FILE_OUTPUT_LISTING_FEATHER):
        log_warning("- Listing not found, downloading again")
        listing_search.download_listing_data_for_app()
    log_info("- Loading documents")
    SEARCH_RESULTS.load_documents(
        FILE_OUTPUT_LISTING_FEATHER,
    )
    log_info(" -- Feather file loaded")
    for __, r in tqdm(SEARCH_RESULTS.documents.iterrows()):
        # Skip repos with missing info
        for k in ["readme", "description"]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(url=r["url"], content=r["description"])
        SEARCH_ENGINE_READMES.index(r["url"], content=r["readme"])
    log_info(" -- All repos loaded")
    yield
    log_info("Exiting app")


app = FastAPI(
    title="OSS4climate",
    description="""
A search engine for open-source code for climate applications
""",
    lifespan=lifespan,
)


def get_top_urls(scores_dict: dict, n: int):
    sorted_urls = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)
    top_n_urls = sorted_urls[:n]
    top_n_dict = dict(top_n_urls)
    return top_n_dict


@app.get("/")
async def base_landing(request: Request, channel: Optional[str] = None):
    log_landing(request=request, channel=channel)
    return RedirectResponse("/ui/search", status_code=307)


@app.get("/favicon.ico")
def _favicon():
    # This is just a dummy favicon for now (waiting for a better logo)
    return RedirectResponse(
        "https://www.pierrevf.consulting/wp-content/uploads/2023/11/cropped-logo_base_png-32x32.png"
    )


# Adding routes
app.mount("/api", api.app)
app.mount("/ui", ui.app)
app.mount("/static", StaticFiles(directory=str(STATIC_FILES_PATH)), name="static")

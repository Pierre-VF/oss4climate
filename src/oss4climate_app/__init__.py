import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from tqdm import tqdm

from oss4climate.scripts import (
    FILE_OUTPUT_LISTING_FEATHER,
    listing_search,
)
from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info, log_warning
from oss4climate_app.config import STATIC_FILES_PATH, URL_APP, URL_FAVICON
from oss4climate_app.src.data_io import (
    SEARCH_ENGINE_DESCRIPTIONS,
    SEARCH_ENGINE_READMES,
    SEARCH_RESULTS,
)
from oss4climate_app.src.log_activity import log_landing
from oss4climate_app.src.routers import api, ui
from oss4climate_app.src.templates import render_template

_ENV_TEST_MODE = "OSS4CLIMATE_TEST_MODE"


def mark_test_mode():
    os.environ[_ENV_TEST_MODE] = "1"


def initialise_error_logging():
    if os.environ.get(_ENV_TEST_MODE):
        log_info("Skipping error logging initialisation in test mode")
        return
    sentry_dsn = SETTINGS.SENTRY_DSN_URL
    if sentry_dsn and len(sentry_dsn) > 1:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            sentry_dsn,
            traces_sample_rate=0,
            integrations=[
                StarletteIntegration(
                    transaction_style="endpoint",
                    failed_request_status_codes={403, *range(500, 599)},
                    http_methods_to_capture=("GET", "POST"),
                ),
                FastApiIntegration(
                    transaction_style="endpoint",
                    failed_request_status_codes={403, *range(500, 599)},
                    http_methods_to_capture=("GET", "POST"),
                ),
            ],
        )
        log_info("Initialised error logging in Sentry")
    else:
        log_info("Skipping error logging in Sentry")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialising error logging at app start
    initialise_error_logging()
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
    return ui.ui_base_search_page(request=request)


@app.head("/", include_in_schema=False, status_code=204)
def _head_base(request: Request):
    pass


@app.get("/favicon.ico")
def _favicon():
    # This is just a dummy favicon for now (waiting for a better logo)
    return RedirectResponse(URL_FAVICON)


# ----------------------------------------------------------------------------------
# For SEO of the app
# ----------------------------------------------------------------------------------


@app.get("/sitemap.xml")
def _sitemap_xml(request: Request):
    content = dict(
        BASE_URL=URL_APP,
        UPDATE_FREQUENCY="weekly",
        UI_ENDPOINTS=["ui/search", "ui/about", "ui/results"],
        LAST_UPDATE=str(datetime.now().date()),
    )
    return render_template(
        request,
        template_file="sitemap.xml",
        content=content,
    )


@app.get("/robots.txt")
def _robots_txt(request: Request):
    content = dict(
        BASE_URL=URL_APP,
    )
    return render_template(
        request,
        template_file="robots.txt",
        content=content,
    )


# Adding routes
app.mount("/api", api.app)
app.mount("/ui", ui.app)
app.mount("/static", StaticFiles(directory=str(STATIC_FILES_PATH)), name="static")

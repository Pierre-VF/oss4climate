import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from oss4climate.src.config import FILE_OUTPUT_OPTIMISED_LISTING_FEATHER, SETTINGS
from oss4climate.src.log import log_info, log_warning

from oss4climate_app.config import STATIC_FILES_PATH, URL_FAVICON
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
    if not os.path.exists(FILE_OUTPUT_OPTIMISED_LISTING_FEATHER):
        # Only importing this heavier part if needed
        from oss4climate.scripts import listing_search

        log_warning("- Listing not found, downloading again")
        listing_search.download_listing_data_for_app()
    log_info("- Loading documents")
    log_info(" -- Feather file loaded")
    for r in SEARCH_RESULTS.iter_documents(
        FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
        load_in_object_without_readme=True,  # As documents are used later for display
        display_tqdm=True,
        memory_safe=True,  # essential in environments with little memory
    ):
        # Skip repos with missing info
        for k in ["optimised_readme", "optimised_description"]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(
            url=r["url"], content=r["optimised_description"]
        )
        SEARCH_ENGINE_READMES.index(r["url"], content=r["optimised_readme"])
    log_info(" -- All repos loaded")
    ui.repository_index_characteristics_from_documents()
    log_info(" -- All metrics loaded")
    yield
    log_info("Exiting app")


if SETTINGS.APP_PROXY_PATH is not None:
    kwargs = dict(root_path=SETTINGS.APP_PROXY_PATH)
else:
    kwargs = dict()


app = FastAPI(
    title="OSS4climate",
    description="""
A search engine for open-source code for climate applications
""",
    lifespan=lifespan,
    openapi_url=None,
    redoc_url=None,
    **kwargs,
)


def get_top_urls(scores_dict: dict, n: int):
    sorted_urls = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)
    top_n_urls = sorted_urls[:n]
    top_n_dict = dict(top_n_urls)
    return top_n_dict


@app.get("/")
async def base_landing(request: Request, channel: Optional[str] = None):
    log_landing(request=request, channel=channel)
    return ui.ui_base_search_page(
        request=request,
    )


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
        BASE_URL=SETTINGS.full_url_base,
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
        BASE_URL=SETTINGS.full_url_base,
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

import os
from contextlib import asynccontextmanager
from datetime import datetime
from importlib.metadata import version
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info
from oss4climate_app.src import mcp_server
from oss4climate_app.src.config import STATIC_FILES_PATH
from oss4climate_app.src.data_io import download_listing_data_for_app
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

    # Ensure that context data is available
    download_listing_data_for_app(force_refresh=False, load_feather_listing=False)

    log_info("Starting app")
    if True:
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
    version=version("oss4climate"),
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
    return RedirectResponse("ui/search")


@app.head("/", include_in_schema=False, status_code=204)
def _head_base(request: Request):
    pass


@app.get("/favicon.ico")
def _favicon():
    url = SETTINGS.APP_URL_FAVICON
    if url:
        return RedirectResponse(url)
    else:
        return JSONResponse(content={"favicon": "not defined"}, status_code=404)


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

# Adding MCP
app.mount("/mcp", app=mcp_server.mcp.http_app(transport="sse"))

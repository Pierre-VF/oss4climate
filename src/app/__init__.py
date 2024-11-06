import os
import pathlib
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tqdm import tqdm

from oss4climate.scripts import (
    FILE_OUTPUT_LISTING_FEATHER,
    listing_search,
)
from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.nlp.search import SearchResults
from oss4climate.src.nlp.search_engine import SearchEngine

script_dir = pathlib.Path(__file__).resolve().parent
templates_path = script_dir / "templates"
static_path = script_dir / "static"
SEARCH_ENGINE_DESCRIPTIONS = SearchEngine()
SEARCH_ENGINE_READMES = SearchEngine()
SEARCH_RESULTS = SearchResults()

# Configuration (for avoidance of information duplication)
URL_CODE_REPOSITORY = "https://github.com/Pierre-VF/oss4climate"
URL_FEEDBACK_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSeei-0V5CobVNX-qOX3lI11FuvTBv1JV77fcUZOideeDtcEhA/viewform?usp=sf_link"


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
templates = Jinja2Templates(directory=str(templates_path))
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


def get_top_urls(scores_dict: dict, n: int):
    sorted_urls = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)
    top_n_urls = sorted_urls[:n]
    top_n_dict = dict(top_n_urls)
    return top_n_dict


@app.get("/")
async def base_landing():
    return RedirectResponse("/ui/search", status_code=307)


# -------------------------------------------------------------------------------------
# Functions with caching
# -------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _unique_licenses() -> list[str]:
    x = SEARCH_RESULTS.documents["license"].apply(_f_none_to_unknown).unique()
    x.sort()
    return x.tolist()


@lru_cache(maxsize=1)
def _unique_languages() -> list[str]:
    x = SEARCH_RESULTS.documents["language"].apply(_f_none_to_unknown).unique()
    x.sort()
    return x.tolist()


@lru_cache(maxsize=1)
def n_repositories_indexed():
    return SEARCH_RESULTS.n_documents


@lru_cache(maxsize=10)
def _search_for_results(query: str) -> pd.DataFrame:
    if len(query) < 1:
        df_x = SEARCH_RESULTS.documents.drop(columns=["readme"])
        df_x["score"] = 1
        return df_x

    print(f"Searching for {query}")
    res_desc = SEARCH_ENGINE_DESCRIPTIONS.search(query)
    res_readme = SEARCH_ENGINE_READMES.search(query)

    df_combined = (
        res_desc.to_frame("description")
        .merge(
            res_readme.to_frame("readme"),
            how="outer",
            left_index=True,
            right_index=True,
        )
        .fillna(0)
    )

    # Also checking for keywords in name
    def _f_score_in_name(x):
        kw = query.lower().split(" ")
        res = 0
        x_lower = x.lower()
        for i in kw:
            if len(i) > 3:  # To reduce noise (quick and dirty)
                if i in x_lower:
                    res += 1
        return res

    df_combined["score"] = df_combined["description"] * 10 + df_combined["readme"]
    df_out = SEARCH_RESULTS.documents.drop(columns=["readme"]).merge(
        df_combined[["score"]],
        how="outer",
        left_on="url",
        right_index=True,
    )

    df_out["score"] = (
        df_out["score"].astype(float).fillna(0)
        + df_out["name"].apply(_f_score_in_name) * 10
        + df_out["organisation"].apply(_f_score_in_name) * 10
    )

    # Focus only on relevant outputs and carry out filtering and duplicate removal
    df_out.query("score>0", inplace=True)
    df_out.sort_values(by="score", ascending=False, inplace=True)
    df_out.drop_duplicates(subset=["url"], inplace=True)
    return df_out


def _clear_cache():
    _unique_licenses.cache_clear()
    _unique_languages.cache_clear()
    n_repositories_indexed.cache_clear()
    _search_for_results.cache_clear()


def _refresh_data(force_refresh: bool = False):
    if force_refresh or not os.path.exists(FILE_OUTPUT_LISTING_FEATHER):
        log_warning("- Listing not found, downloading again")
        listing_search.download_listing_data_for_app()
    log_info("- Loading documents")
    SEARCH_RESULTS.load_documents(FILE_OUTPUT_LISTING_FEATHER)
    for __, r in tqdm(SEARCH_RESULTS.documents.iterrows()):
        # Skip repos with missing info
        for k in ["readme", "description"]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(url=r["url"], content=r["description"])
        SEARCH_ENGINE_READMES.index(r["url"], content=r["readme"])


# ----------------------------------------------------------------------------------
# UI endpoints
# ----------------------------------------------------------------------------------


def _f_none_to_unknown(x: str | date | None) -> str:
    if x is None:
        return "(unknown)"
    else:
        return str(x)


def _render_template(request: Request, template_file: str, content: dict | None = None):
    resp = {
        "request": request,
        "URL_CODE_REPOSITORY": URL_CODE_REPOSITORY,
        "URL_FEEDBACK_FORM": URL_FEEDBACK_FORM,
    }
    if content is not None:
        resp = resp | content
    return templates.TemplateResponse(request, template_file, resp)


@app.get("/ui/search", response_class=HTMLResponse, include_in_schema=False)
async def search(request: Request):
    return _render_template(
        request=request,
        template_file="search.html",
        content={
            "n_repositories_indexed": n_repositories_indexed(),
            "languages": _unique_languages(),
            "licenses": _unique_licenses(),
            "free_text": " ",
        },
    )


@app.get("/ui/results", response_class=HTMLResponse, include_in_schema=False)
async def search_results(
    request: Request,
    query: str,
    language: Optional[str] = None,
    license: Optional[str] = None,
    n_results: int = 100,
    offset: int | None = None,
):
    df_out = _search_for_results(query.strip().lower())

    # Adding a primitive refinment mechanism by language (not implemented in the most effective manner)
    if language and (language != "*"):
        df_out = df_out[df_out["language"] == language]
    if license and (license != "*"):
        df_out = df_out[df_out["license"] == license]

    if offset is None:
        df_shown = df_out.head(n_results)
    else:
        df_shown = df_out.iloc[offset : offset + n_results].copy()

    # Refining output
    df_shown = df_shown.drop(
        columns=["score"]  # Dropping scores, as it's not informative to the user
    )
    for i in ["license", "last_commit"]:
        df_shown.loc[:, i] = df_shown[i].apply(_f_none_to_unknown)

    n_found = len(df_shown)
    n_total_found = len(df_out)

    # URLs
    current_url = f"results?query={query}&n_results={n_results}"
    if language:
        current_url = f"{current_url}&language={language}"
    if license:
        current_url = f"{current_url}&license={license}"
    current_offset = 0 if offset is None else offset

    url_previous = f"{current_url}&offset={current_offset - n_results - 1}"
    url_next = f"{current_url}&offset={current_offset + n_results + 1}"

    show_previous = current_offset > 0
    show_next = current_offset <= (n_total_found - n_results)

    return _render_template(
        request=request,
        template_file="results.html",
        content={
            "request": request,
            "n_found": n_found,
            "n_total_found": n_total_found,
            "results": df_shown,
            "query": query,
            "url_previous": url_previous,
            "url_next": url_next,
            "show_previous": show_previous,
            "show_next": show_next,
        },
    )


@app.get("/ui/about", include_in_schema=False)
def read_about(request: Request):
    return _render_template(
        request=request,
        template_file="about.html",
    )


@app.get("/favicon.ico")
def _favicon():
    # This is just a dummy favicon for now (waiting for a better logo)
    return RedirectResponse(
        "https://www.pierrevf.consulting/wp-content/uploads/2023/11/cropped-logo_base_png-32x32.png"
    )


# ----------------------------------------------------------------------------------
# API endpoints
# ----------------------------------------------------------------------------------

# For now, only redirects


@app.get("/api/code")
async def api_code():
    return RedirectResponse(URL_CODE_REPOSITORY, status_code=307)


@app.get("/api/data_csv")
async def api_data():
    return RedirectResponse(
        "https://data.pierrevf.consulting/oss4climate/listing_data.csv", status_code=307
    )


@app.get("/api/refresh_data")
async def refresh_data(key: Optional[str] = None):
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
    _refresh_data(force_refresh=True)
    _clear_cache()
    log_info("DATA refreshing END")
    return PlainTextResponse("Data was successfully refreshed")

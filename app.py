"""
FastAPI app to operate a search

Note: heavily inspired from https://github.com/alexmolas/microsearch/
"""

import os
import pathlib
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tqdm import tqdm
from uvicorn import run

from oss4climate.scripts import (
    FILE_OUTPUT_LISTING_FEATHER,
    listing_search,
)
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.nlp.search import SearchResults
from oss4climate.src.nlp.search_engine import SearchEngine

script_dir = pathlib.Path(__file__).resolve().parent
templates_path = script_dir / "src/app/templates"
static_path = script_dir / "src/app/static"
SEARCH_ENGINE_DESCRIPTIONS = SearchEngine()
SEARCH_ENGINE_READMES = SearchEngine()
SEARCH_RESULTS = SearchResults()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("Starting app")
    if not os.path.exists(FILE_OUTPUT_LISTING_FEATHER):
        log_warning("- Listing not found, downloading again")
        listing_search.download_data()
    log_info("- Loading documents")
    SEARCH_RESULTS.load_documents(FILE_OUTPUT_LISTING_FEATHER)
    for __, r in tqdm(SEARCH_RESULTS.documents.iterrows()):
        # Skip repos with missing info
        for k in ["readme", "description"]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(url=r["url"], content=r["description"])
        SEARCH_ENGINE_READMES.index(r["url"], content=r["readme"])
    yield
    log_info("Exiting app")


app = FastAPI(lifespan=lifespan)
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


# ----------------------------------------------------------------------------------
# UI endpoints
# ----------------------------------------------------------------------------------
@app.get("/ui/search", response_class=HTMLResponse, include_in_schema=False)
async def search(request: Request):
    posts = SEARCH_ENGINE_DESCRIPTIONS.posts
    return templates.TemplateResponse(
        "search.html", {"request": request, "posts": posts}
    )


def _f_none_to_unknown(x: str | date | None) -> str:
    if x is None:
        return "(unknown)"
    else:
        return str(x)


@lru_cache(maxsize=10)
def _search_for_results(query: str) -> pd.DataFrame:
    print(f"Searching for {query}")
    res_desc = SEARCH_ENGINE_DESCRIPTIONS.search(query)
    res_readme = SEARCH_ENGINE_DESCRIPTIONS.search(query)

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
    df_combined["score"] = (
        df_combined["description"] * 10 + df_combined["readme"]
    ).round(1)
    df_out = (
        SEARCH_RESULTS.documents.drop(columns=["readme"])
        .merge(
            df_combined[["score"]],
            how="inner",
            left_on="url",
            right_index=True,
        )
        .sort_values(by="score", ascending=False)
    )
    return df_out


@app.get("/ui/results", response_class=HTMLResponse, include_in_schema=False)
async def search_results(
    request: Request,
    query: str,
    language: Optional[str] = None,
    n_results: int = 100,
    offset: int | None = None,
):
    df_out = _search_for_results(query)

    # Adding a primitive refinment mechanism by language (not implemented in the most effective manner)
    if language:
        df_out = df_out[df_out["language"] == language]

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
    current_offset = 0 if offset is None else offset

    url_previous = f"{current_url}&offset={current_offset - n_results - 1}"
    url_next = f"{current_url}&offset={current_offset + n_results + 1}"

    show_previous = current_offset > 0
    show_next = current_offset <= (n_total_found - n_results)

    return templates.TemplateResponse(
        "results.html",
        {
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
    return templates.TemplateResponse("about.html", {"request": request})


# ----------------------------------------------------------------------------------
# API endpoints
# ----------------------------------------------------------------------------------

# For now, only redirects


@app.get("/api/code")
async def api_code():
    return RedirectResponse("https://github.com/Pierre-VF/oss4climate", status_code=307)


@app.get("/api/data_csv")
async def api_data():
    return RedirectResponse(
        "https://data.pierrevf.consulting/oss4climate/listing_data.csv", status_code=307
    )


if __name__ == "__main__":
    # For local testing
    run(app, host="127.0.0.1", port=8080)

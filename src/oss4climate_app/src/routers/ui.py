"""
Module containing the UI code
"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse

from oss4climate.src.models import (
    EnumLicenseCategories,
)
from oss4climate_app.config import (
    FORCE_HTTPS,
    SETTINGS,
    URL_CODE_REPOSITORY,
    URL_FEEDBACK_FORM,
    umami_site_id,
)
from oss4climate_app.src.data_io import (
    repository_index_characteristics_from_documents,
    search_for_results,
    unique_license_categories,
)
from oss4climate_app.src.log_activity import log_search
from oss4climate_app.src.routers import listing_credits
from oss4climate_app.src.templates import render_template

app = APIRouter(include_in_schema=False)


def _f_none_to_unknown(x: str | date | None) -> str:
    if x is None:
        return "(unknown)"
    else:
        return str(x)


def _render_ui_template(
    request: Request, template_file: str, content: dict | None = None
):
    url = request.url.components
    if FORCE_HTTPS:
        canonical_url = f"https://{url.netloc}{url.path}"
    else:
        canonical_url = f"{url.scheme}://{url.netloc}{url.path}"
    resp = {
        "UMAMI_SITE_ID": umami_site_id(),
        "URL_CODE_REPOSITORY": URL_CODE_REPOSITORY,
        "URL_FEEDBACK_FORM": URL_FEEDBACK_FORM,
        "URL_BASE": SETTINGS.full_url_base,
        "credits_text": f"With contributions from manually curated listings: {listing_credits()}",
        "canonical_url": canonical_url,
    }
    if content is not None:
        resp = resp | content
    return render_template(request, template_file=template_file, content=resp)


def ui_base_search_page(request: Request):
    characteristics = repository_index_characteristics_from_documents()
    return _render_ui_template(
        request=request,
        template_file="search.html",
        content={
            "n_repositories_indexed": characteristics.n_repositories_indexed,
            "languages": characteristics.unique_languages,
            "licenses": characteristics.unique_licenses,
            "unique_license_categories": unique_license_categories(),
            "free_text": "",
        },
    )


@app.get("/search", response_class=HTMLResponse, include_in_schema=False)
async def search(request: Request):
    return ui_base_search_page(request=request)


@app.get("/results", response_class=HTMLResponse, include_in_schema=False)
async def search_results(
    request: Request,
    background_tasks: BackgroundTasks,
    query: Optional[str] = None,
    language: Optional[str] = None,
    license_category: Optional[str] = None,
    exclude_forks: Optional[bool] = None,
    exclude_inactive: Optional[bool] = None,
    # For backwards compatibility of links
    n_results: Optional[int] = None,
    offset: Optional[int] = None,
):
    if query:
        query = query.strip().lower()
    df_out = search_for_results(query)

    # Adding a primitive refinment mechanism by language (not implemented in the most effective manner)
    if language and (language != "*"):
        df_out = df_out[df_out["language"] == language]
    if license_category and (license_category != "*"):
        try:
            enum_license_category = EnumLicenseCategories[license_category]
        except KeyError:
            raise ValueError("Invalid license category")

        df_out = df_out[df_out["license_category"] == enum_license_category]

    if exclude_forks:
        df_out = df_out[df_out["is_fork"] == False]
    if exclude_inactive:
        t_limit = date.today() - timedelta(days=365)
        df_out = df_out[df_out["last_commit"] >= t_limit]

    # Refining output
    if "score" in df_out.keys():
        df_out.drop(
            columns=["score"],  # Dropping scores, as it's not informative to the user
            inplace=True,
        )
    for i in ["license", "last_commit"]:
        df_out.loc[:, i] = df_out[i].apply(_f_none_to_unknown)

    n_total_found = len(df_out)
    n_found = n_total_found

    # Filling the gaps for clean display
    cols_to_clean = ["description", "language", "license"]
    df_out.loc[:, cols_to_clean] = (
        df_out[cols_to_clean]
        .replace(
            {
                None: pd.NA,
                "nan": pd.NA,
            }
        )
        .fillna(value="(no data)")
        .infer_objects(copy=False)  # to avoid warning on downcasting
    )

    # Log results
    background_tasks.add_task(
        log_search,
        search_term=query,
        number_of_results=n_total_found,
        view_offset=None,
    )

    return _render_ui_template(
        request=request,
        template_file="results.html",
        content={
            "request": request,
            "n_found": n_found,
            "n_total_found": n_total_found,
            "results": df_out,
            "query": query,
        },
    )


@app.get("/about", include_in_schema=False)
def read_about(request: Request):
    return _render_ui_template(
        request=request,
        template_file="about.html",
    )


@app.get("/privacy", include_in_schema=False)
def read_privacy(request: Request):
    return _render_ui_template(
        request=request,
        template_file="privacy.html",
    )


# Corresponding HEAD endpoints ( https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI.head )
def _default_head_behaviour(request: Request):
    pass


@app.head("/", include_in_schema=False, status_code=204)
def _head_base(request: Request):
    _default_head_behaviour(request)


@app.head("/search", include_in_schema=False, status_code=204)
def _head_search(request: Request):
    _default_head_behaviour(request)


@app.head("/results", include_in_schema=False, status_code=204)
def _head_results(request: Request):
    _default_head_behaviour(request)


@app.head("/about", include_in_schema=False, status_code=204)
def _head_about(request: Request):
    _default_head_behaviour(request)

"""
Module containing the API code
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse

from oss4climate.src.parsers.licenses import LicenseCategoriesEnum
from oss4climate_app.config import (
    URL_CODE_REPOSITORY,
    URL_FEEDBACK_FORM,
)
from oss4climate_app.src.data_io import (
    n_repositories_indexed,
    search_for_results,
    unique_languages,
    unique_license_categories,
    unique_licenses,
)
from oss4climate_app.src.log_activity import log_search
from oss4climate_app.src.templates import render_template

app = APIRouter()


def _f_none_to_unknown(x: str | date | None) -> str:
    if x is None:
        return "(unknown)"
    else:
        return str(x)


def _render_ui_template(
    request: Request, template_file: str, content: dict | None = None
):
    resp = {
        "URL_CODE_REPOSITORY": URL_CODE_REPOSITORY,
        "URL_FEEDBACK_FORM": URL_FEEDBACK_FORM,
    }
    if content is not None:
        resp = resp | content
    return render_template(request, template_file=template_file, content=resp)


def ui_base_search_page(request: Request):
    return _render_ui_template(
        request=request,
        template_file="search.html",
        content={
            "n_repositories_indexed": n_repositories_indexed(),
            "languages": unique_languages(),
            "licenses": unique_licenses(),
            "unique_license_categories": unique_license_categories(),
            "free_text": " ",
        },
    )


@app.get("/search", response_class=HTMLResponse, include_in_schema=False)
async def search(request: Request):
    return ui_base_search_page(request=request)


@app.get("/results", response_class=HTMLResponse, include_in_schema=False)
async def search_results(
    request: Request,
    background_tasks: BackgroundTasks,
    query: str,
    language: Optional[str] = None,
    license_category: Optional[str] = None,
    n_results: int = 100,
    offset: int | None = None,
    exclude_forks: Optional[bool] = None,
    exclude_inactive: Optional[bool] = None,
):
    df_out = search_for_results(query.strip().lower())

    # Adding a primitive refinment mechanism by language (not implemented in the most effective manner)
    if language and (language != "*"):
        df_out = df_out[df_out["language"] == language]
    if license_category and (license_category != "*"):
        try:
            enum_license_category = LicenseCategoriesEnum[license_category]
        except KeyError:
            raise ValueError("Invalid license category")

        df_out = df_out[df_out["license_category"] == enum_license_category]

    if exclude_forks:
        df_out = df_out[df_out["is_fork"] == False]
    if exclude_inactive:
        t_limit = date.today() - timedelta(days=365)
        df_out = df_out[df_out["last_commit"] >= t_limit]

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
    if license_category:
        current_url = f"{current_url}&license_category={license_category}"
    current_offset = 0 if offset is None else offset

    url_previous = f"{current_url}&offset={current_offset - n_results - 1}"
    url_next = f"{current_url}&offset={current_offset + n_results + 1}"

    show_previous = current_offset > 0
    show_next = current_offset <= (n_total_found - n_results)

    # Log results
    background_tasks.add_task(
        log_search,
        search_term=query,
        number_of_results=n_total_found,
        view_offset=current_offset,
    )

    return _render_ui_template(
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


@app.get("/about", include_in_schema=False)
def read_about(request: Request):
    return _render_ui_template(
        request=request,
        template_file="about.html",
    )


# Corresponding HEAD endpoints ( https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI.head )
def _default_head_behaviour(request: Request):
    pass


@app.head("/", include_in_schema=False, status_code=204)
def _head_base(request: Request):
    _default_head_behaviour()


@app.head("/search", include_in_schema=False, status_code=204)
def _head_search(request: Request):
    _default_head_behaviour()


@app.head("/results", include_in_schema=False, status_code=204)
def _head_results(request: Request):
    _default_head_behaviour()


@app.head("/about", include_in_schema=False, status_code=204)
def _head_about(request: Request):
    _default_head_behaviour()

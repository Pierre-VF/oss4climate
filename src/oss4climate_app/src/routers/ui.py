"""
Module containing the API code
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from oss4climate_app.config import (
    TEMPLATES_PATH,
    URL_CODE_REPOSITORY,
    URL_FEEDBACK_FORM,
)
from oss4climate_app.src.data_io import (
    n_repositories_indexed,
    search_for_results,
    unique_languages,
    unique_licenses,
)
from oss4climate_app.src.log_activity import log_search

templates = Jinja2Templates(directory=str(TEMPLATES_PATH))

app = APIRouter()


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


@app.get("/search", response_class=HTMLResponse, include_in_schema=False)
async def search(request: Request):
    return _render_template(
        request=request,
        template_file="search.html",
        content={
            "n_repositories_indexed": n_repositories_indexed(),
            "languages": unique_languages(),
            "licenses": unique_licenses(),
            "free_text": " ",
        },
    )


@app.get("/results", response_class=HTMLResponse, include_in_schema=False)
async def search_results(
    request: Request,
    background_tasks: BackgroundTasks,
    query: str,
    language: Optional[str] = None,
    license: Optional[str] = None,
    n_results: int = 100,
    offset: int | None = None,
):
    df_out = search_for_results(query.strip().lower())

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

    # Log results
    background_tasks.add_task(
        log_search,
        search_term=query,
        number_of_results=n_total_found,
        view_offset=offset,
    )

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


@app.get("/about", include_in_schema=False)
def read_about(request: Request):
    return _render_template(
        request=request,
        template_file="about.html",
    )
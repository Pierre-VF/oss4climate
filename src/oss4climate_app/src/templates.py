from fastapi import Request
from fastapi.templating import Jinja2Templates

from oss4climate_app.config import (
    APP_VERSION,
    TEMPLATES_PATH,
)

templates = Jinja2Templates(directory=str(TEMPLATES_PATH))


def render_template(request: Request, template_file: str, content: dict | None = None):
    resp = {
        "request": request,
        "APP_VERSION": APP_VERSION,
    }
    if content is not None:
        resp = resp | content

    if template_file.endswith(".html"):
        media_type = "text/html"
    elif template_file.endswith(".xml"):
        media_type = "text/xml"
    elif template_file.endswith(".txt"):
        media_type = "text/plain"
    else:
        media_type = None

    return templates.TemplateResponse(
        request,
        template_file,
        resp,
        media_type=media_type,
    )

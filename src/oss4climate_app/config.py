import pathlib
import uuid
from functools import lru_cache

from oss4climate.src.config import (
    SETTINGS,
    URL_LISTING_CSV,
    URL_LISTING_FEATHER,
    URL_LISTINGS_INDEX,
    Settings,
)

_script_dir = pathlib.Path(__file__).resolve().parent
TEMPLATES_PATH = _script_dir / "templates"
STATIC_FILES_PATH = _script_dir / "static"

# To prevent caching between versions (this doesn't work too well across instances, but does the job for now)
APP_VERSION = str(uuid.uuid4())

# Configuration (for avoidance of information duplication)
URL_CODE_REPOSITORY = "https://github.com/Pierre-VF/oss4climate"
APP_URL_BASE = SETTINGS.APP_URL_BASE
URL_FEEDBACK_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSeei-0V5CobVNX-qOX3lI11FuvTBv1JV77fcUZOideeDtcEhA/viewform?usp=sf_link"

URL_DATA_LISTINGS_JSON = URL_LISTINGS_INDEX
URL_DATA_CSV = URL_LISTING_CSV
URL_DATA_FEATHER = URL_LISTING_FEATHER
URL_FAVICON = SETTINGS.APP_URL_FAVICON

FORCE_HTTPS = True


@lru_cache(maxsize=1)
def umami_site_id() -> str:
    return Settings().UMAMI_SITE_ID

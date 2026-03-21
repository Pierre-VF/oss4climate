import pathlib
import uuid

from oss4climate.src.config import (
    SETTINGS,
)

_script_dir = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_PATH = _script_dir / "templates"
STATIC_FILES_PATH = _script_dir / "static"

# To prevent caching between versions (this doesn't work too well across instances, but does the job for now)
APP_VERSION = str(uuid.uuid4())

# Configuration (for avoidance of information duplication)
URL_CODE_REPOSITORY = "https://github.com/Pierre-VF/oss4climate"
URL_FEEDBACK_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSeei-0V5CobVNX-qOX3lI11FuvTBv1JV77fcUZOideeDtcEhA/viewform?usp=sf_link"


# Link to all documents
FILE_INPUT_LISTINGS_INDEX = "indexes/listings.json"
FILE_OUTPUT_DIR = SETTINGS.LOCAL_FOLDER
FILE_OUTPUT_LISTING_FEATHER = f"{FILE_OUTPUT_DIR}/listing_data.feather"

# For data available on Github
__URL_GITHUB_BASE = (
    "https://raw.githubusercontent.com/Pierre-VF/oss4climate/refs/heads/main/indexes"
)
URL_LISTINGS_INDEX = f"{__URL_GITHUB_BASE}/listings.json"


# For data hosted outside of Github
URL_BASE = "https://data.pierrevf.consulting/oss4climate"
URL_RAW_INDEX = f"{URL_BASE}/summary.toml"
URL_LISTING_FEATHER = f"{URL_BASE}/listing_data.feather"


FORCE_HTTPS = True

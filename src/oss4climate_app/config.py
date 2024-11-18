import pathlib
import uuid

from oss4climate.scripts import listing_search

_script_dir = pathlib.Path(__file__).resolve().parent
TEMPLATES_PATH = _script_dir / "templates"
STATIC_FILES_PATH = _script_dir / "static"

# To prevent caching between versions (this doesn't work too well across instances, but does the job for now)
APP_VERSION = str(uuid.uuid4())

# Configuration (for avoidance of information duplication)
URL_CODE_REPOSITORY = "https://github.com/Pierre-VF/oss4climate"
URL_APP = "https://oss4climate.pierrevf.consulting"
URL_FEEDBACK_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSeei-0V5CobVNX-qOX3lI11FuvTBv1JV77fcUZOideeDtcEhA/viewform?usp=sf_link"

URL_DATA_CSV = listing_search.URL_LISTING_CSV
URL_DATA_FEATHER = listing_search.URL_LISTING_FEATHER
URL_FAVICON = "https://www.pierrevf.consulting/wp-content/uploads/2023/11/cropped-logo_base_png-32x32.png"

import pathlib

_script_dir = pathlib.Path(__file__).resolve().parent
TEMPLATES_PATH = _script_dir / "templates"
STATIC_FILES_PATH = _script_dir / "static"


# Configuration (for avoidance of information duplication)
URL_CODE_REPOSITORY = "https://github.com/Pierre-VF/oss4climate"
URL_FEEDBACK_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSeei-0V5CobVNX-qOX3lI11FuvTBv1JV77fcUZOideeDtcEhA/viewform?usp=sf_link"

URL_DATA_CSV = "https://data.pierrevf.consulting/oss4climate/listing_data.csv"
URL_DATA_FEATHER = "https://data.pierrevf.consulting/oss4climate/listing_data.feather"
URL_FAVICON = "https://www.pierrevf.consulting/wp-content/uploads/2023/11/cropped-logo_base_png-32x32.png"

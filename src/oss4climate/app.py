"""
Oss4climate app
"""

from pathlib import Path

from oss4x.app import (
    AppConfig,
    Theme,
    create_app,
    mark_test_mode,
    mcp,
)
from oss4x.app.src.config import get_file_output_listing_feather

index_folder = Path(__file__).parent.parent.parent / "indexes"
FILE_INPUT_LISTINGS_INDEX = str(index_folder / "listings.json")
FILE_INPUT_INDEX = str(index_folder / "repositories.toml")
FILE_OUTPUT_LISTING_FEATHER = get_file_output_listing_feather()

app = create_app(
    AppConfig(
        theme=Theme(),
        APPLICATION_FIELD="climate",
        URL_CODE_REPOSITORY="https://github.com/Pierre-VF/oss4climate",
        INDEXES_FOLDER=str(index_folder),
        FILE_INPUT_LISTINGS_INDEX=FILE_INPUT_LISTINGS_INDEX,
        # APP_URL_BASE="",
        APP_PROXY_PATH=None,
        APP_URL_FAVICON=None,
        URL_FEEDBACK_FORM="https://docs.google.com/forms/d/e/1FAIpQLSeei-0V5CobVNX-qOX3lI11FuvTBv1JV77fcUZOideeDtcEhA/viewform?usp=sf_link",
        URL_LISTINGS_INDEX="https://raw.githubusercontent.com/Pierre-VF/oss4climate/refs/heads/main/indexes/listings.json",
        URL_RAW_INDEX="https://data.pierrevf.com/oss4climate/summary.toml",
        URL_LISTING_FEATHER=None,
        FORCE_HTTPS=True,
    )
)

# To support imports in other modules (as a one-stop-shop)
__all__ = [
    "FILE_INPUT_INDEX",
    "FILE_INPUT_LISTINGS_INDEX",
    "FILE_OUTPUT_LISTING_FEATHER",
    "app",
    "get_file_output_listing_feather",
    "index_folder",
    "mark_test_mode",
    "mcp",
]

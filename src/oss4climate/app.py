"""
Oss4climate app
"""

import os.path
from pathlib import Path

from oss4x.app import (
    AppConfig,
    Theme,
    ThemeColors,
    ThemeShadows,
    ThemeSpacing,
    ThemeTypography,
    create_app,
    mark_test_mode,
    mcp,
)
from oss4x.app.src.config import get_file_output_listing_feather

index_folder = Path(__file__).parent.parent.parent / "indexes"
FILE_INPUT_LISTINGS_INDEX = str(index_folder / "listings.json")
FILE_INPUT_INDEX = str(index_folder / "repositories.toml")
FILE_OUTPUT_LISTING_FEATHER = get_file_output_listing_feather()

# Check that the indexes exist
if not os.path.exists(FILE_INPUT_LISTINGS_INDEX):
    raise RuntimeError(f"Input listings doesn't exist ({FILE_INPUT_LISTINGS_INDEX})")
if not os.path.exists(FILE_INPUT_INDEX):
    raise RuntimeError(f"Input index doesn't exist ({FILE_INPUT_INDEX})")

URL_FAVICON = "https://raw.githubusercontent.com/Pierre-VF/oss4climate/refs/heads/main/favicon.svg"

APP_THEME = Theme(
    colors=ThemeColors(
        primary="#2f8f5f",
        primary_light="#e6f4ec",
        primary_dark="#14532d",
        secondary="#3a8dde",
        secondary_light="#e3f0fd",
        background="#f6f8f7",
        surface="#ffffff",
        text_primary="#1f2937",
        text_secondary="#4b5563",
        text_light="#ffffff",
        border="#d8e0db",
        divider="#e7ede9",
        success="#16a34a",
        warning="#d97706",
        error="#dc2626",
        info="#0891b2",
    ),
    typography=ThemeTypography(
        font_family=(
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
            "'Helvetica Neue', Arial, sans-serif"
        ),
        font_family_mono=(
            "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
        ),
        font_size_xlarge="28px",
    ),
    spacing=ThemeSpacing(
        border_radius_sm=6,
        border_radius_md=10,
        border_radius_lg=16,
        border_radius_full=9999,
    ),
    shadows=ThemeShadows(
        sm="0 1px 2px rgba(16, 24, 40, 0.06)",
        md="0 4px 12px rgba(16, 24, 40, 0.08)",
        lg="0 8px 24px rgba(16, 24, 40, 0.12)",
        xl="0 16px 40px rgba(16, 24, 40, 0.16)",
    ),
)

app = create_app(
    AppConfig(
        theme=APP_THEME,
        APPLICATION_FIELD="climate",
        URL_CODE_REPOSITORY="https://github.com/Pierre-VF/oss4climate",
        INDEXES_FOLDER=str(index_folder),
        FILE_INPUT_LISTINGS_INDEX=FILE_INPUT_LISTINGS_INDEX,
        # APP_URL_BASE="",
        APP_PROXY_PATH=None,
        APP_URL_FAVICON=URL_FAVICON,
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

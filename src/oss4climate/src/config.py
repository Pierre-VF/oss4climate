from typing import Optional

import pydantic_settings
from dotenv import load_dotenv


class Settings(pydantic_settings.BaseSettings):
    GITHUB_API_TOKEN: Optional[str] = None
    GITLAB_ACCESS_TOKEN: Optional[str] = None
    SQLITE_DB: str = ".data/db.sqlite"
    APP_SQLITE_DB: str = ".data/app_db.sqlite"
    # Identifiants du FTP pour l'export
    EXPORT_FTP_URL: Optional[str] = None
    EXPORT_FTP_USER: Optional[str] = None
    EXPORT_FTP_PASSWORD: Optional[str] = None
    # App settings
    DATA_REFRESH_KEY: Optional[str] = None
    SENTRY_DSN_URL: Optional[str] = None

    model_config = pydantic_settings.SettingsConfigDict(
        env_file_encoding="utf-8",
    )


# Loading settings
load_dotenv(override=True)

SETTINGS = Settings()


# Link to all documents
FILE_INPUT_INDEX = "indexes/repositories.toml"
FILE_INPUT_LISTINGS_INDEX = "indexes/listings.toml"
FILE_OUTPUT_DIR = ".data"
FILE_OUTPUT_LISTING_CSV = f"{FILE_OUTPUT_DIR}/listing_data.csv"
FILE_OUTPUT_LISTING_FEATHER = f"{FILE_OUTPUT_DIR}/listing_data.feather"
FILE_OUTPUT_OPTIMISED_LISTING_FEATHER = (
    f"{FILE_OUTPUT_DIR}/optimised_listing_data.feather"
)
FILE_OUTPUT_SUMMARY_TOML = f"{FILE_OUTPUT_DIR}/summary.toml"

URL_BASE = "https://data.pierrevf.consulting/oss4climate"
URL_RAW_INDEX = f"{URL_BASE}/summary.toml"
URL_LISTING_CSV = f"{URL_BASE}/listing_data.csv"
URL_LISTING_FEATHER = f"{URL_BASE}/listing_data.feather"

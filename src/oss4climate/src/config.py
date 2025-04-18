from typing import Optional

import pydantic_settings
from dotenv import load_dotenv


class Settings(pydantic_settings.BaseSettings):
    GITHUB_API_TOKEN: Optional[str] = None
    GITLAB_ACCESS_TOKEN: Optional[str] = None
    LOCAL_FOLDER: str = ".data"
    SCRAPING_SQLITE_DB: str = "db.sqlite"
    APP_SQLITE_DB: str = "app_db.sqlite"
    # For usage analytics
    UMAMI_SITE_ID: str = ""
    # Identifiants of FTP for export
    EXPORT_FTP_URL: Optional[str] = None
    EXPORT_FTP_USER: Optional[str] = None
    EXPORT_FTP_PASSWORD: Optional[str] = None
    # App settings
    DATA_REFRESH_KEY: Optional[str] = None
    SENTRY_DSN_URL: Optional[str] = None

    model_config = pydantic_settings.SettingsConfigDict(
        env_file_encoding="utf-8",
    )

    @property
    def path_scraping_sqlite_db(self) -> str:
        return f"{self.LOCAL_FOLDER}/{self.SCRAPING_SQLITE_DB}"

    @property
    def path_app_sqlite_db(self) -> str:
        if self.APP_SQLITE_DB.startswith(self.LOCAL_FOLDER):
            # for backwards compatibility
            return self.APP_SQLITE_DB
        return f"{self.LOCAL_FOLDER}/{self.APP_SQLITE_DB}"


# Loading settings
load_dotenv(override=True)

SETTINGS = Settings()


# Link to all documents
FILE_INPUT_INDEX = "indexes/repositories.toml"
FILE_INPUT_LISTINGS_INDEX = "indexes/listings.json"
FILE_OUTPUT_DIR = SETTINGS.LOCAL_FOLDER
FILE_OUTPUT_LISTING_CSV = f"{FILE_OUTPUT_DIR}/listing_data.csv"
FILE_OUTPUT_LISTING_FEATHER = f"{FILE_OUTPUT_DIR}/listing_data.feather"
FILE_OUTPUT_OPTIMISED_LISTING_FEATHER = (
    f"{FILE_OUTPUT_DIR}/optimised_listing_data.feather"
)
FILE_OUTPUT_SUMMARY_TOML = f"{FILE_OUTPUT_DIR}/summary.toml"

URL_BASE = "https://data.pierrevf.consulting/oss4climate"
URL_RAW_INDEX = f"{URL_BASE}/summary.toml"
URL_LISTINGS_INDEX = f"{URL_BASE}/listings.json"
URL_LISTING_CSV = f"{URL_BASE}/listing_data.csv"
URL_LISTING_FEATHER = f"{URL_BASE}/listing_data.feather"
URL_OPTIMISED_LISTING_FEATHER = f"{URL_BASE}/optimised_listing_data.feather"

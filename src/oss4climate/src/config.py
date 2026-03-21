from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import pydantic_settings
from dotenv import load_dotenv


class Settings(pydantic_settings.BaseSettings):
    # For scraping
    GITHUB_API_TOKEN: Optional[str] = None
    GITLAB_ACCESS_TOKEN: Optional[str] = None
    LOCAL_FOLDER: str = str(Path(__file__).parent.parent.parent.parent / ".data")
    SCRAPING_SQLITE_DB: str = "db.sqlite"
    # For usage analytics
    UMAMI_SITE_ID: str = ""
    APP_SQLITE_DB: str = "app_db.sqlite"
    # Identifiants of FTP for export (scripts only)
    EXPORT_FTP_URL: Optional[str] = None
    EXPORT_FTP_USER: Optional[str] = None
    EXPORT_FTP_PASSWORD: Optional[str] = None
    # App settings
    DATA_REFRESH_KEY: Optional[str] = None
    SENTRY_DSN_URL: Optional[str] = None
    APP_URL_BASE: str = ""
    APP_PROXY_PATH: Optional[str] = None
    APP_URL_FAVICON: str | None = None

    # Typesense settings
    TYPESENSE_API_KEY: str = ""
    TYPESENSE_HOST: str = ""
    TYPESENSE_CONNECTION_TIMEOUT: int = 2

    # Search parameters
    ENABLE_HYBRID_SEARCH: bool = False

    model_config = pydantic_settings.SettingsConfigDict(
        env_file_encoding="utf-8",
    )

    @property
    def typesense_config(self) -> dict[str, int | str]:
        url = urlsplit(self.TYPESENSE_HOST)
        if url.hostname in [None, ""]:
            raise EnvironmentError("Hostname must be provided in TYPESENSE_HOST")
        if url.scheme in [None, ""]:
            raise EnvironmentError(
                "Scheme (http/https) must be provided in TYPESENSE_HOST"
            )
        if url.port in [None, ""]:
            raise EnvironmentError("Port must be provided in TYPESENSE_HOST")
        return {
            "host": url.hostname,
            "port": url.port,
            "protocol": url.scheme,
        }

    @property
    def full_url_base(self) -> str:
        if (self.APP_PROXY_PATH is None) or (self.APP_PROXY_PATH == ""):
            return self.APP_URL_BASE
        else:
            return f"{self.APP_URL_BASE}{self.APP_PROXY_PATH}"

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

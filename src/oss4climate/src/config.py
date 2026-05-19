import os
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

    # Database
    DATABASE_USERNAME: str | None = None
    DATABASE_PASSWORD: str | None = None
    DATABASE_HOST: str
    DATABASE_NAME: str | None = None
    DATABASE_PORT: int | None = None

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

    # For data and usage analytics
    UMAMI_SITE_ID: str | None = None

    # Search parameters
    ENABLE_HYBRID_SEARCH: bool = False

    model_config = pydantic_settings.SettingsConfigDict(
        env_file_encoding="utf-8",
    )

    @property
    def typesense_config(self) -> dict[str, int | str]:
        """
        Get Typesense configuration from TYPESENSE_HOST environment variable

        :return: Dictionary containing host, port, and protocol for Typesense connection
        :raises EnvironmentError: If hostname, scheme, or port is missing from TYPESENSE_HOST
        """
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
        """
        Get the full URL base by combining APP_URL_BASE and APP_PROXY_PATH

        :return: Combined URL base string
        """
        if (self.APP_PROXY_PATH is None) or (self.APP_PROXY_PATH == ""):
            return self.APP_URL_BASE
        else:
            return f"{self.APP_URL_BASE}{self.APP_PROXY_PATH}"

    @property
    def path_scraping_sqlite_db(self) -> str:
        """
        Get the full path to the scraping SQLite database

        :return: Full path string to the scraping database
        """
        return f"{self.LOCAL_FOLDER}/{self.SCRAPING_SQLITE_DB}"

    @property
    def database_connection_string(self) -> str:
        """
        Get the full database connection string

        :return: Full database connection string
        """

        if None not in {
            self.DATABASE_USERNAME,
            self.DATABASE_PASSWORD,
            self.DATABASE_PORT,
            self.DATABASE_NAME,
        }:
            # Postgres case
            out = f"postgresql+psycopg2://{self.DATABASE_USERNAME}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        else:
            # Sqlite case
            out = f"{self.LOCAL_FOLDER}/{self.DATABASE_HOST}"
            if not out.endswith(".sqlite"):
                raise ValueError("Env DATABASE_HOST should point to a SQLite database")
            db_folder, __ = os.path.split(out)
            os.makedirs(db_folder, exist_ok=True)
            out = "sqlite:///" + out
        return out


# Loading settings
load_dotenv(override=True)

SETTINGS = Settings()

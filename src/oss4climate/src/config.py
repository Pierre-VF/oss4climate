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

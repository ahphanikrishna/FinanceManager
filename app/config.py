import os
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_ENV = os.getenv("APP_ENV", "dev").lower()
if APP_ENV not in {"dev", "qa", "prod"}:
    APP_ENV = "dev"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=f".env.{APP_ENV}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    ALGORITHM: str = "HS256"

    ENVIRONMENT: str = APP_ENV
    DATABASE_URL: str = "sqlite:///./bank_data_dev.db"
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET_FILE: str = ""

settings = Settings()
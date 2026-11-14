"""Application settings loaded from environment variables / .env file.

Secrets are never hard-coded: SECRET_KEY and DATABASE_URL must come from the
environment (see .env.example).
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "NEXA LMS"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60
    INVITE_EXPIRE_HOURS: int = 72

    # E-mail: "console" logs messages (development), "smtp" sends them.
    EMAIL_BACKEND: Literal["console", "smtp"] = "console"
    EMAIL_FROM: str = "NEXA <no-reply@nexa.school>"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool = False
    SMTP_TIMEOUT: int = 15

    # Database
    DATABASE_URL: str

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    FRONTEND_URL: str = "http://localhost:5173"

    # Files
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_PATH: Path = BASE_DIR / "storage"
    MAX_UPLOAD_SIZE_MB: int = 10
    S3_BUCKET: str | None = None
    S3_ENDPOINT_URL: str | None = None
    S3_REGION: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None

    # Time zone for users who have not chosen one (IANA name)
    DEFAULT_TIMEZONE: str = "Europe/Moscow"

    # Real-time notifications (PostgreSQL LISTEN/NOTIFY -> Server-Sent Events)
    REALTIME_ENABLED: bool = True

    # Subscriptions
    SUBSCRIPTION_EXPIRING_DAYS: int = 7
    SUBSCRIPTION_CHECK_INTERVAL_MINUTES: int = 60
    # E-mail copies of notifications / chat messages that are still unread after the delay
    EMAIL_NOTIFICATIONS_ENABLED: bool = True
    EMAIL_NOTIFY_DELAY_MINUTES: int = 10
    EMAIL_OUTBOX_INTERVAL_SECONDS: int = 60

    @field_validator("LOCAL_STORAGE_PATH")
    @classmethod
    def storage_relative_to_backend(cls, v: Path) -> Path:
        """A relative path (e.g. ./storage from .env.example) is resolved against the
        backend folder, not the current directory: uploads must never land in the
        repository root when the server is started from elsewhere."""
        return v if v.is_absolute() else (BASE_DIR / v).resolve()

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Use psycopg 3 driver for plain postgresql:// URLs.
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

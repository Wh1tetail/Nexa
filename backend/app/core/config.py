"""Application settings loaded from environment variables / .env file.

Secrets are never hard-coded: SECRET_KEY and DATABASE_URL must come from the
environment (see .env.example).
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    EMAIL_FROM: str = "NEXA <no-reply@nexalanguage.com>"
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
    # Deletes stored files no database row refers to (0 = off). Only files older
    # than STORAGE_SWEEP_GRACE_HOURS are touched (uploads not yet committed are safe).
    STORAGE_SWEEP_INTERVAL_HOURS: int = 24
    STORAGE_SWEEP_GRACE_HOURS: int = 24

    # ---- Book-to-Test: PDF books ----
    BOOK_MAX_UPLOAD_MB: int = Field(default=200, ge=1, le=2000)
    BOOK_MAX_PAGES: int = Field(default=500, ge=1, le=5000)
    # a page with less text than this and a picture on it is a scan waiting for OCR
    BOOK_OCR_MIN_CHARS: int = Field(default=30, ge=1)
    # OCR (services/ocr_service.py). Off by default for local runs without Tesseract;
    # the Docker image ships Tesseract and docker-compose turns it on. Off = scans are only marked.
    OCR_ENABLED: bool = False
    OCR_ENGINE: str = ""  # the registered engine's name: "tesseract"
    OCR_LANGUAGES: str = "eng+rus+kaz"
    OCR_PAGE_TIMEOUT_SECONDS: int = Field(default=120, ge=5, le=1800)
    # the worker (python -m app.worker): parallel jobs, queue polling, retries
    BOOK_WORKER_CONCURRENCY: int = Field(default=1, ge=1, le=8)
    BOOK_WORKER_POLL_SECONDS: float = Field(default=3, gt=0)
    BOOK_JOB_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    # a running job whose heartbeat is older than this goes back to the queue
    BOOK_JOB_STALE_MINUTES: int = Field(default=15, ge=1)

    # ---- AI (Book-to-Test question generation) ----
    # Only services/ai_client.py talks to the provider; the key never leaves the server.
    AI_PROVIDER: Literal["anthropic"] = "anthropic"
    ANTHROPIC_API_KEY: SecretStr | None = None
    AI_MODEL: str = "claude-sonnet-5-5"
    # Tried in order after AI_MODEL when it declines the request or stays unavailable
    # after its retries, e.g. ["claude-opus-5-5"]; empty = no model switching.
    AI_FALLBACK_MODELS: list[str] = []
    AI_MAX_QUESTIONS_PER_JOB: int = Field(default=50, ge=1, le=200)
    AI_MAX_PAGES_PER_JOB: int = Field(default=30, ge=1, le=300)
    # pages sent in one request (longer ranges go in portions)
    AI_PAGES_PER_REQUEST: int = Field(default=10, ge=1, le=100)
    # question types methodists may generate (stage 1 of Book-to-Test: choice and true/false)
    AI_QUESTION_TYPES: list[str] = ["single_choice", "multiple_choice", "true_false"]
    # Retries per model for rate limits, timeouts, network/server errors and malformed answers
    AI_MAX_RETRIES: int = Field(default=3, ge=0, le=10)
    AI_TIMEOUT_SECONDS: float = Field(default=300, gt=0)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=32000, ge=1024, le=128000)
    # USD per million tokens, for cost estimates: {"model": {"input": .., "output": ..,
    # "cache_read": .., "cache_write": ..}}. Merged over the built-in table in ai_client.
    AI_PRICES: dict[str, dict[str, float]] = {}

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
    def book_max_upload_bytes(self) -> int:
        return self.BOOK_MAX_UPLOAD_MB * 1024 * 1024

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

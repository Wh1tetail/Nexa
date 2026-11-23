"""Book-to-Test: books (stage 1 - upload and storage)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BookJobKind, BookJobStatus, BookStatus, EnglishLevel
from app.schemas.homework import AttachmentOut

BookLanguage = Literal["en", "ru", "kk"]


class BookUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str | None = Field(default=None, max_length=200)
    language: BookLanguage = "en"
    level: EnglishLevel | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("author", mode="before")
    @classmethod
    def _author(cls, v):
        return (v.strip() or None) if isinstance(v, str) else v


class BookJobOut(BaseModel):
    id: int
    book_id: int
    kind: BookJobKind
    status: BookJobStatus
    progress: int
    attempts: int
    max_attempts: int
    cancel_requested: bool
    error_code: str | None
    usage: dict | None  # AI tokens and estimated cost (generation jobs)
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class BookOut(BaseModel):
    id: int
    title: str
    author: str | None
    language: str
    level: EnglishLevel | None
    page_count: int
    status: BookStatus
    error_code: str | None
    uploaded_by_name: str | None
    created_at: datetime
    updated_at: datetime | None
    file: AttachmentOut | None
    # the latest text-extraction job: progress while it runs, the error if it failed
    processing: BookJobOut | None = None

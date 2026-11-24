"""Book-to-Test: books, jobs, pages, chapters, generation and question drafts."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import (
    BookJobKind,
    BookJobStatus,
    BookStatus,
    ChapterOrigin,
    Difficulty,
    DraftStatus,
    EnglishLevel,
    PageTextSource,
    QuestionType,
)
from app.schemas.homework import AttachmentOut
from app.schemas.test import QuestionIn

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
    settings: dict[str, Any] = {}  # what was asked (generation) and, when done, the result
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
    has_outline: bool = False
    text_pages: int = 0  # pages with text
    ocr_pages: int = 0  # scans waiting for OCR
    # the latest text-extraction job: progress while it runs, the error if it failed
    processing: BookJobOut | None = None
    # the latest question-generation job and the drafts by status (stage 5)
    generation: BookJobOut | None = None
    drafts: dict[str, int] = {}


class PageOut(BaseModel):
    page_number: int
    text: str
    source: PageTextSource
    needs_ocr: bool
    char_count: int

    model_config = {"from_attributes": True}


class ChapterIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    parent_id: int | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        return v.strip() if isinstance(v, str) else v


class ChapterUpdate(BaseModel):
    """Only the fields sent change; "parent_id": null makes it a top-level chapter."""
    title: str | None = Field(default=None, min_length=1, max_length=300)
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    parent_id: int | None = None
    position: int | None = Field(default=None, ge=0)

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        return v.strip() if isinstance(v, str) else v


class ChapterOut(BaseModel):
    id: int
    parent_id: int | None
    title: str
    start_page: int
    end_page: int
    page_count: int
    position: int
    depth: int  # 1 = chapter, 2 = section, 3 = subsection
    origin: ChapterOrigin



class GenerateRequest(BaseModel):
    """A chapter, or a page range; the server checks the limits and the text."""
    chapter_id: int | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    question_count: int = Field(ge=1, le=200)
    types: list[QuestionType] = Field(min_length=1, max_length=6)
    difficulty: Difficulty | None = None  # None: mixed
    question_language: BookLanguage = "en"
    level: EnglishLevel | None = None

    @model_validator(mode="after")
    def _source(self):
        if self.chapter_id is None and (self.page_start is None or self.page_end is None):
            raise ValueError("Укажите главу или страницы")
        return self


class DraftOut(BaseModel):
    id: int
    job_id: int | None
    status: DraftStatus
    question: dict[str, Any]  # QuestionIn
    difficulty: Difficulty
    page_start: int
    page_end: int
    excerpt: str
    warnings: list[str]
    exported_test_id: int | None = None  # the library test it went to
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}



class DraftUpdate(BaseModel):
    """A methodist's edit: the question in the test format, its difficulty and quote."""
    question: QuestionIn
    difficulty: Difficulty
    excerpt: str | None = Field(default=None, max_length=1000)


class ReviewRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["approve", "reject", "reset"]


class ExportRequest(BaseModel):
    """Approved drafts into a new library test (title) or the end of an unpublished one (test_id)."""
    draft_ids: list[int] = Field(min_length=1, max_length=200)
    test_id: int | None = None
    title: str | None = Field(default=None, max_length=200)
    level: EnglishLevel | None = None
    section_ids: list[int] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=15)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = " ".join(t.strip().lower().split())[:40]
            if t and t not in out:
                out.append(t)
        return out

    @model_validator(mode="after")
    def _target(self):
        self.title = (self.title or "").strip() or None
        if self.test_id is None and not self.title:
            raise ValueError("Укажите название теста")
        return self


class ReviewResult(BaseModel):
    id: int
    ok: bool
    status: DraftStatus | None = None
    # why not: not_found, exported (already in the library), invalid, needs_edit (quote not on the page)
    reason: str | None = None

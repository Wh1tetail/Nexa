"""Book-to-Test: PDF books methodists generate test questions from.
The PDF itself is an ordinary `Attachment` (book_id), so storage, downloads and
the orphan sweep work as for every other file."""
from datetime import datetime
from typing import TYPE_CHECKING

from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import (
    BookJobKind,
    BookJobStatus,
    BookStatus,
    ChapterOrigin,
    Difficulty,
    DraftStatus,
    EnglishLevel,
    PageTextSource,
    str_enum,
)

if TYPE_CHECKING:
    from app.models.file import Attachment
    from app.models.user import User


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(200))  # the book's author
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    level: Mapped[EnglishLevel | None] = mapped_column(str_enum(EnglishLevel, "english_level"))
    page_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[BookStatus] = mapped_column(
        str_enum(BookStatus, "book_status"), default=BookStatus.UPLOADED, server_default=BookStatus.UPLOADED.value
    )
    error_code: Mapped[str | None] = mapped_column(String(60))  # why processing failed
    # processing summary (stage 3)
    has_outline: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    text_pages: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # pages with text
    ocr_pages: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # scans waiting for OCR
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploaded_by: Mapped["User | None"] = relationship()
    files: Mapped[list["Attachment"]] = relationship(
        primaryjoin="Book.id == Attachment.book_id",
        order_by="Attachment.id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def file(self) -> "Attachment | None":
        """The book's PDF (one per book)."""
        return self.files[0] if self.files else None


class BookJob(Base, TimestampMixin):
    """A queued background job (text extraction, AI generation). The worker takes
    one with SELECT ... FOR UPDATE SKIP LOCKED, so no job ever runs twice at once;
    `heartbeat_at` lets a crashed worker's job be put back in the queue."""
    __tablename__ = "book_jobs"
    __table_args__ = (Index("ix_book_jobs_queue", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    kind: Mapped[BookJobKind] = mapped_column(str_enum(BookJobKind, "book_job_kind"))
    status: Mapped[BookJobStatus] = mapped_column(
        str_enum(BookJobStatus, "book_job_status"), default=BookJobStatus.QUEUED,
        server_default=BookJobStatus.QUEUED.value,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # 0..100
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # retry delay
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    locked_by: Mapped[str | None] = mapped_column(String(100))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_detail: Mapped[str | None] = mapped_column(Text)  # short, never book text
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # AI tokens and estimated cost
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    book: Mapped[Book] = relationship()


class BookPage(Base):
    """The text of one PDF page (page_number as in the PDF, from 1). Questions point
    at pages, so the text is kept page by page."""
    __tablename__ = "book_pages"
    __table_args__ = (UniqueConstraint("book_id", "page_number", name="uq_book_pages_book_page"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="", server_default="")
    source: Mapped[PageTextSource] = mapped_column(
        str_enum(PageTextSource, "page_text_source"), default=PageTextSource.NONE, server_default=PageTextSource.NONE.value
    )
    needs_ocr: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ocr_confidence: Mapped[float | None] = mapped_column()
    char_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class BookChapter(Base, TimestampMixin):
    """A chapter or a subsection (parent_id) of a book: a page range."""
    __tablename__ = "book_chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("book_chapters.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    start_page: Mapped[int] = mapped_column(Integer)
    end_page: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    origin: Mapped[ChapterOrigin] = mapped_column(
        str_enum(ChapterOrigin, "chapter_origin"), default=ChapterOrigin.MANUAL, server_default=ChapterOrigin.MANUAL.value
    )


class QuestionDraft(Base, TimestampMixin):
    """A generated question waiting for a methodist's review. `question` is a dump of
    schemas.test.QuestionIn (checked by it), so the library takes it as it is; the
    source (pages, quote) stays with it. Nothing but a methodist's action approves it."""
    __tablename__ = "question_drafts"
    __table_args__ = (Index("ix_question_drafts_book_status", "book_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("book_jobs.id", ondelete="SET NULL"), index=True)
    status: Mapped[DraftStatus] = mapped_column(
        str_enum(DraftStatus, "draft_status"), default=DraftStatus.DRAFT, server_default=DraftStatus.DRAFT.value
    )
    question: Mapped[dict[str, Any]] = mapped_column(JSONB)
    difficulty: Mapped[Difficulty] = mapped_column(
        str_enum(Difficulty, "difficulty"), default=Difficulty.MEDIUM, server_default=Difficulty.MEDIUM.value
    )
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    excerpt: Mapped[str] = mapped_column(Text, default="", server_default="")
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    edited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exported_test_id: Mapped[int | None] = mapped_column(ForeignKey("tests.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

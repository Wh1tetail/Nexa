"""Book-to-Test job handlers (run by the worker through services/book_jobs.py).

Stage 2: `extract` checks the stored PDF again (it is read from the shared
storage into a temporary file, never whole into memory), confirms the page
count page by page with progress, and marks the book ready. Stage 3 adds text
and chapter extraction to the same handler.
"""
from __future__ import annotations

import logging
import tempfile

from sqlalchemy.orm import Session

from app.core.i18n import M
from app.models import Book, BookJob
from app.models.enums import BookJobKind, BookStatus, NotificationType
from app.services.book_jobs import FinalJobError, JobCancelled, JobContext, RetryableJobError, enqueue, register
from app.services.notification_service import notify
from app.storage.base import get_storage

log = logging.getLogger(__name__)

PROGRESS_EVERY = 10  # pages between progress updates


def _book_link(book: Book) -> str:
    return f"/methodist/books/{book.id}"


def _recipients(book: Book, job: BookJob) -> list[int]:
    return [uid for uid in {job.created_by_id or book.uploaded_by_id} if uid]


def start_processing(db: Session, book: Book, user) -> BookJob:
    """Queue text extraction for a book (upload, or the "process again" button)."""
    job = enqueue(db, book, BookJobKind.EXTRACT, user)
    book.status, book.error_code = BookStatus.PROCESSING, None
    return job


def _on_extract_failed(db: Session, job: BookJob) -> None:
    book = db.get(Book, job.book_id)
    if book is None:
        return
    book.status, book.error_code = BookStatus.FAILED, job.error_code
    notify(db, _recipients(book, job), NotificationType.BOOK_FAILED,
           M("Не удалось обработать книгу"), book.title, _book_link(book))


def _on_extract_cancelled(db: Session, job: BookJob) -> None:
    book = db.get(Book, job.book_id)
    if book is not None and book.status == BookStatus.PROCESSING:
        book.status = BookStatus.UPLOADED


@register(BookJobKind.EXTRACT, on_failed=_on_extract_failed, on_cancelled=_on_extract_cancelled)
def extract(db: Session, job: BookJob, ctx: JobContext) -> None:
    from pypdf import PdfReader

    book = db.get(Book, job.book_id)
    if book is None or book.file is None:
        raise FinalJobError("file_missing")
    with tempfile.TemporaryFile() as tmp:
        try:
            for chunk in get_storage().open(book.file.storage_key):
                tmp.write(chunk)
        except FileNotFoundError:
            raise FinalJobError("file_missing") from None
        except OSError as e:  # storage temporarily unavailable
            raise RetryableJobError("storage_unavailable", type(e).__name__) from None
        tmp.seek(0)
        try:
            reader = PdfReader(tmp, strict=False)
            if reader.is_encrypted:
                raise FinalJobError("pdf_encrypted")
            total = len(reader.pages)
            ctx.progress(1)
            for i, page in enumerate(reader.pages, start=1):
                _ = page.mediabox  # every page must open
                if i % PROGRESS_EVERY == 0 or i == total:
                    ctx.progress(round(99 * i / total))
        except (FinalJobError, RetryableJobError, JobCancelled):
            raise
        except Exception as e:
            raise FinalJobError("pdf_unreadable", type(e).__name__) from None
    if total < 1:
        raise FinalJobError("pdf_empty")
    book.page_count = total
    book.status, book.error_code = BookStatus.READY, None
    notify(db, _recipients(book, job), NotificationType.BOOK_PROCESSED,
           M("Книга обработана"), book.title, _book_link(book))
    log.info("Book %s processed: %d page(s)", book.id, total)

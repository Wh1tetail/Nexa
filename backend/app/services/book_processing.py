"""Book-to-Test job handlers (run by the worker through services/book_jobs.py).

`extract` reads the stored PDF (from the shared storage into a temporary file,
never whole into memory) and, page by page with progress:
- stores each page's text (`book_pages`), marking scans that need OCR; when OCR is
  on (services/ocr_service.py) the engine reads those pages (stage 4);
- builds chapters from the PDF outline, or from headings when there is none
  (services/pdf_extract.py). Chapters a methodist created or edited are kept:
  processing again then only refreshes the page texts;
- fills the book's summary (pages with text, pages waiting for OCR, outline found).
All of it is one transaction: a cancelled or failed run leaves the previous result.
"""
from __future__ import annotations

import logging
import os
import tempfile

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.core.i18n import M
from app.core.config import settings
from app.models import Book, BookChapter, BookJob, BookPage, QuestionDraft
from app.models.enums import BookJobKind, BookStatus, ChapterOrigin, Difficulty, NotificationType, PageTextSource
from app.services.book_jobs import FinalJobError, JobCancelled, JobContext, RetryableJobError, enqueue, register
from app.services.notification_service import notify
from app.services.ocr_service import OcrEngine, get_ocr_engine
from app.services.pdf_extract import ChapterDraft, PageResult, clean_text, detect_chapters, outline_chapters, read_page
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


def _store_pages(db: Session, book: Book, pages: list[PageResult]) -> None:
    db.execute(delete(BookPage).where(BookPage.book_id == book.id))
    db.add_all(
        BookPage(
            book_id=book.id, page_number=p.number, text=p.text, needs_ocr=p.needs_ocr, char_count=len(p.text),
            source=PageTextSource(p.source), ocr_confidence=p.confidence,
        )
        for p in pages
    )
    db.flush()


def _store_chapters(db: Session, book: Book, drafts: list[ChapterDraft], origin: ChapterOrigin,
                    parent: BookChapter | None = None) -> None:
    for pos, d in enumerate(drafts):
        ch = BookChapter(book_id=book.id, parent_id=parent.id if parent else None, title=d.title,
                         start_page=d.start_page, end_page=d.end_page, position=pos, origin=origin)
        db.add(ch)
        db.flush()
        _store_chapters(db, book, d.children, origin, ch)


def _run_ocr(engine: OcrEngine, pdf_path: str, pages: list[PageResult], ctx: JobContext) -> None:
    """Recognize the scanned pages in place; a page the engine can't read stays marked."""
    scans = [p for p in pages if p.needs_ocr]
    for i, p in enumerate(scans, start=1):
        try:
            res = engine.recognize(pdf_path, p.number, settings.OCR_LANGUAGES)
            text = clean_text(res.text)
        except Exception as e:
            log.warning("OCR failed on page %s (%s)", p.number, type(e).__name__)
            text = ""
            res = None
        if text and res is not None:
            p.text, p.needs_ocr, p.source, p.confidence = text, False, "ocr", res.confidence
        ctx.progress(95 + round(4 * i / len(scans)))


def _read_pdf(pdf_path: str, ctx: JobContext) -> tuple[list[PageResult], list[ChapterDraft], int]:
    """Text of every page and the outline; a broken or protected PDF fails the job for good."""
    from pypdf import PdfReader

    with open(pdf_path, "rb") as f:
        try:
            reader = PdfReader(f, strict=False)
            if reader.is_encrypted:
                raise FinalJobError("pdf_encrypted")
            total = len(reader.pages)
            if total < 1:
                raise FinalJobError("pdf_empty")
            ctx.progress(1)
            pages: list[PageResult] = []
            for i, page in enumerate(reader.pages, start=1):
                pages.append(read_page(page, i, settings.BOOK_OCR_MIN_CHARS))
                if i % PROGRESS_EVERY == 0 or i == total:
                    ctx.progress(round(95 * i / total))
            outline = outline_chapters(reader, total)
        except (FinalJobError, RetryableJobError, JobCancelled):
            raise
        except Exception as e:
            raise FinalJobError("pdf_unreadable", type(e).__name__) from None
    return pages, outline, total


@register(BookJobKind.EXTRACT, on_failed=_on_extract_failed, on_cancelled=_on_extract_cancelled)
def extract(db: Session, job: BookJob, ctx: JobContext) -> None:
    book = db.get(Book, job.book_id)
    if book is None or book.file is None:
        raise FinalJobError("file_missing")
    # a named temporary file: an OCR engine opens the PDF by its path
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="nexa-book-")
    try:
        with os.fdopen(fd, "wb") as out:
            try:
                for chunk in get_storage().open(book.file.storage_key):
                    out.write(chunk)
            except FileNotFoundError:
                raise FinalJobError("file_missing") from None
            except OSError as e:  # storage temporarily unavailable
                raise RetryableJobError("storage_unavailable", type(e).__name__) from None
        pages, outline, total = _read_pdf(pdf_path, ctx)
        engine = get_ocr_engine()
        if engine is not None and any(p.needs_ocr for p in pages):
            _run_ocr(engine, pdf_path, pages, ctx)
    finally:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass

    _store_pages(db, book, pages)
    has_manual = db.scalar(select(exists().where(
        BookChapter.book_id == book.id, BookChapter.origin == ChapterOrigin.MANUAL)))
    if not has_manual:
        db.execute(delete(BookChapter).where(BookChapter.book_id == book.id))
        if outline:
            _store_chapters(db, book, outline, ChapterOrigin.OUTLINE)
        else:
            _store_chapters(db, book, detect_chapters(pages, total), ChapterOrigin.DETECTED)
    ctx.check_cancel()
    book.page_count = total
    book.has_outline = bool(outline)
    book.text_pages = sum(1 for p in pages if p.text)
    book.ocr_pages = sum(1 for p in pages if p.needs_ocr)
    book.status, book.error_code = BookStatus.READY, None
    notify(db, _recipients(book, job), NotificationType.BOOK_PROCESSED,
           M("Книга обработана"), book.title, _book_link(book))
    log.info("Book %s processed: %d page(s)", book.id, total)



# ---------- question generation (stage 5) ----------

AI_FINAL_ERRORS = {
    "ai_not_configured", "ai_request_rejected", "ai_refused", "ai_malformed_response", "ai_output_truncated",
}


def _run_generation(db: Session, job: BookJob, ctx: JobContext):
    """The AI part of generate / regenerate: pages -> checked questions; AI errors -> job errors."""
    from dataclasses import replace

    from app.core.exceptions import AppError
    from app.models.enums import DraftStatus
    from app.services import ai_client as ai
    from app.services import question_generator as qg

    book = db.get(Book, job.book_id)
    if book is None:
        raise FinalJobError("book_missing")
    gs = qg.settings_from_job(dict(job.settings or {}))
    pages = [qg.PageText(p.page_number, p.text) for p in db.scalars(
        select(BookPage).where(BookPage.book_id == book.id, BookPage.page_number.between(gs.page_start, gs.page_end))
        .order_by(BookPage.page_number)
    )]
    existing = db.scalars(select(QuestionDraft.question).where(
        QuestionDraft.book_id == book.id, QuestionDraft.status != DraftStatus.REJECTED,
        QuestionDraft.page_start.between(gs.page_start, gs.page_end)))
    gs = replace(gs, avoid=tuple(dict.fromkeys([*gs.avoid, *(q.get("text", "") for q in existing)])))
    try:
        client = ai.get_ai_client()
    except ai.AINotConfigured:
        raise FinalJobError("ai_not_configured") from None
    usage = client.new_usage()
    ctx.progress(2)
    try:
        return book, qg.generate_questions(
            pages, gs, client=client, usage=usage,
            on_portion=lambda done, total: ctx.progress(5 + round(90 * done / total)),
        )
    except AppError as e:  # the pages changed since the job was queued
        raise FinalJobError("invalid_settings", e.template) from None
    except ai.AIUnavailable as e:
        raise RetryableJobError(e.code, str(e)[:200]) from None
    except ai.AIError as e:
        raise FinalJobError(e.code if e.code in AI_FINAL_ERRORS else "ai_error", type(e).__name__) from None
    finally:
        if usage.requests:
            ctx.record_usage(usage.to_dict())


def _store_drafts(db: Session, book: Book, job: BookJob, result) -> list[QuestionDraft]:
    rows = [QuestionDraft(
        book_id=book.id, job_id=job.id, question=d.question.model_dump(mode="json"),
        difficulty=Difficulty(d.difficulty), page_start=d.page, page_end=d.page,
        excerpt=d.excerpt, warnings=d.warnings,
    ) for d in result.drafts]
    db.add_all(rows)
    db.flush()
    job.settings = {**(job.settings or {}), "result": {
        "drafts": len(result.drafts), "rejected": len(result.rejected), "shortfall": result.shortfall,
        "model": result.model, "draft_ids": [r.id for r in rows],
    }}
    return rows


@register(BookJobKind.GENERATE)
def generate(db: Session, job: BookJob, ctx: JobContext) -> None:
    """AI questions for a page range -> drafts. Nothing is approved here."""
    book, result = _run_generation(db, job, ctx)
    rows = _store_drafts(db, book, job, result)
    ctx.check_cancel()
    if job.created_by_id:
        notify(db, [job.created_by_id], NotificationType.QUESTIONS_READY,
               M("Вопросы готовы: {n}", n=len(rows)), book.title, _book_link(book))


@register(BookJobKind.REGENERATE)
def regenerate(db: Session, job: BookJob, ctx: JobContext) -> None:
    """One replacement question; the replaced draft is rejected only when a new one came out."""
    from app.models.enums import DraftStatus

    book, result = _run_generation(db, job, ctx)
    rows = _store_drafts(db, book, job, result)
    old = db.get(QuestionDraft, (job.settings or {}).get("replace_draft_id") or 0)
    if rows and old is not None and old.status in (DraftStatus.DRAFT, DraftStatus.REJECTED):
        old.status = DraftStatus.REJECTED
    ctx.check_cancel()

"""Book-to-Test, stage 1: storing PDF books.

A book's PDF is an ordinary `Attachment` (book_id) in the shared storage, so
downloads (`/files/{id}`, editors only) and the orphan sweep work as for any
other file. The upload is checked before anything is stored: the extension, the
size (BOOK_MAX_UPLOAD_MB), the PDF signature, that it opens and is not
password-protected, and the page count (BOOK_MAX_PAGES). Reading the file never
loads it into memory at once; the page count comes from the PDF's page tree.
"""
import logging
import uuid
from datetime import UTC, datetime
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import BadRequest, Conflict, NotFound
from app.models import Attachment, Book, BookChapter, BookJob, BookPage, QuestionDraft, User
from app.models.enums import BookJobKind, ChapterOrigin, DraftStatus
from app.schemas.book import BookJobOut, BookOut, BookUpdate, ChapterIn, ChapterOut, ChapterUpdate
from app.schemas.homework import AttachmentOut
from app.storage.base import get_storage
from app.utils.files import safe_filename

log = logging.getLogger(__name__)

PDF_MIME = "application/pdf"


def _size(f: BinaryIO) -> int:
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    return size


def count_pdf_pages(f: BinaryIO) -> int:
    """Page count of a PDF that opens without a password, or a 400."""
    from pypdf import PdfReader

    f.seek(0)
    if f.read(5) != b"%PDF-":
        raise BadRequest("Файл повреждён или это не PDF")
    f.seek(0)
    try:
        reader = PdfReader(f, strict=False)
        if reader.is_encrypted:
            raise BadRequest("PDF защищён паролем — загрузите файл без защиты")
        pages = len(reader.pages)
    except BadRequest:
        raise
    except Exception:  # pypdf raises many kinds of errors on a broken file
        raise BadRequest("Файл повреждён или это не PDF") from None
    finally:
        f.seek(0)
    if pages < 1:
        raise BadRequest("В PDF нет страниц")
    if pages > settings.BOOK_MAX_PAGES:
        raise BadRequest("В PDF больше {n} страниц", n=settings.BOOK_MAX_PAGES)
    return pages


def check_upload(upload: UploadFile) -> tuple[str, int, int]:
    """(safe file name, size in bytes, pages) of an acceptable PDF, or a 400."""
    name = safe_filename(upload.filename or "book.pdf")
    if not name.lower().endswith(".pdf"):
        raise BadRequest("Загрузите файл PDF")
    size = _size(upload.file)
    if size == 0:
        raise BadRequest("Файл «{name}» пустой", name=name)
    if size > settings.book_max_upload_bytes:
        raise BadRequest("Файл «{name}» превышает {mb} МБ", name=name, mb=settings.BOOK_MAX_UPLOAD_MB)
    return name, size, count_pdf_pages(upload.file)


def create_book(db: Session, user: User, upload: UploadFile, meta: BookUpdate) -> Book:
    """Check, store and register a book (the caller commits)."""
    name, size, pages = check_upload(upload)
    now = datetime.now(UTC)
    book = Book(
        title=meta.title, author=meta.author, language=meta.language, level=meta.level,
        page_count=pages, uploaded_by_id=user.id, updated_at=now,
    )
    db.add(book)
    db.flush()
    key = f"{now:%Y/%m}/{uuid.uuid4().hex}.pdf"
    get_storage().save_file(key, upload.file, PDF_MIME)  # if the commit fails, the sweep removes it
    db.add(Attachment(
        uploaded_by_id=user.id, book_id=book.id, original_name=name,
        storage_key=key, mime_type=PDF_MIME, size_bytes=size,
    ))
    db.flush()
    db.refresh(book)
    log.info("Book %s uploaded: %d page(s), %d byte(s)", book.id, pages, size)
    return book


def get_book(db: Session, book_id: int) -> Book:
    book = db.scalar(select(Book).options(selectinload(Book.uploaded_by)).where(Book.id == book_id))
    if book is None:
        raise NotFound("Книга не найдена")
    return book


def list_books(db: Session) -> list[Book]:
    """Books are shared by every editor (like the test library)."""
    return list(db.scalars(
        select(Book).options(selectinload(Book.uploaded_by)).order_by(Book.created_at.desc(), Book.id.desc())
    ).all())


def update_book(book: Book, meta: BookUpdate) -> None:
    book.title, book.author, book.language, book.level = meta.title, meta.author, meta.language, meta.level
    book.updated_at = datetime.now(UTC)


def delete_book(db: Session, book: Book) -> list[str]:
    """Removes the book and its file rows; returns the storage keys to delete after the commit."""
    keys = [f.storage_key for f in book.files]
    db.delete(book)
    db.flush()
    return keys


def delete_stored(keys: list[str]) -> None:
    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:  # the orphan sweep retries later
            log.exception("Could not delete stored book file")


def _latest_job(db: Session, book_id: int, kind: BookJobKind) -> BookJob | None:
    return db.scalar(select(BookJob).where(BookJob.book_id == book_id, BookJob.kind == kind)
                     .order_by(BookJob.created_at.desc(), BookJob.id.desc()).limit(1))


def to_out(book: Book, db: Session | None = None) -> BookOut:
    from sqlalchemy import func

    f = book.file
    job = gen = None
    drafts: dict[str, int] = {}
    if db is not None:
        job = _latest_job(db, book.id, BookJobKind.EXTRACT)
        gen = _latest_job(db, book.id, BookJobKind.GENERATE)
        drafts = {s.value: n for s, n in db.execute(
            select(QuestionDraft.status, func.count()).where(QuestionDraft.book_id == book.id)
            .group_by(QuestionDraft.status)).all()}
    return BookOut(
        id=book.id, title=book.title, author=book.author, language=book.language, level=book.level,
        page_count=book.page_count, status=book.status, error_code=book.error_code,
        uploaded_by_name=book.uploaded_by.full_name if book.uploaded_by else None,
        created_at=book.created_at, updated_at=book.updated_at,
        file=AttachmentOut.model_validate(f) if f else None,
        processing=BookJobOut.model_validate(job) if job else None,
        generation=BookJobOut.model_validate(gen) if gen else None, drafts=drafts,
        has_outline=book.has_outline, text_pages=book.text_pages, ocr_pages=book.ocr_pages,
    )


# ---------- pages ----------

MAX_PAGES_PER_REQUEST = 20


def get_pages(db: Session, book: Book, first: int, last: int) -> list[BookPage]:
    if first < 1 or last < first:
        raise BadRequest("Неверный диапазон страниц")
    if last - first + 1 > MAX_PAGES_PER_REQUEST:
        raise BadRequest("Не более {n} страниц за один раз", n=MAX_PAGES_PER_REQUEST)
    return list(db.scalars(
        select(BookPage).where(BookPage.book_id == book.id, BookPage.page_number.between(first, last))
        .order_by(BookPage.page_number)
    ).all())


# ---------- chapters ----------

MAX_CHAPTER_DEPTH = 3


def _chapters(db: Session, book_id: int) -> list[BookChapter]:
    return list(db.scalars(select(BookChapter).where(BookChapter.book_id == book_id)).all())


def chapter_tree(db: Session, book: Book) -> list[ChapterOut]:
    """Chapters in reading order (parents before their sections), with depth."""
    rows = _chapters(db, book.id)
    by_parent: dict[int | None, list[BookChapter]] = {}
    for c in rows:
        by_parent.setdefault(c.parent_id, []).append(c)
    out: list[ChapterOut] = []

    def walk(parent_id: int | None, depth: int) -> None:
        for c in sorted(by_parent.get(parent_id, []), key=lambda x: (x.start_page, x.position, x.id)):
            out.append(ChapterOut(
                id=c.id, parent_id=c.parent_id, title=c.title, start_page=c.start_page, end_page=c.end_page,
                page_count=c.end_page - c.start_page + 1, position=c.position, depth=depth, origin=c.origin,
            ))
            walk(c.id, depth + 1)

    walk(None, 1)
    return out


def get_chapter(db: Session, chapter_id: int) -> BookChapter:
    ch = db.get(BookChapter, chapter_id)
    if ch is None:
        raise NotFound("Глава не найдена")
    return ch


def _depth(rows: dict[int, BookChapter], ch_id: int | None) -> int:
    depth = 0
    while ch_id is not None:
        depth += 1
        ch_id = rows[ch_id].parent_id
    return depth


def _height(rows: dict[int, BookChapter], ch_id: int) -> int:
    kids = [c.id for c in rows.values() if c.parent_id == ch_id]
    return 1 + max((_height(rows, k) for k in kids), default=0)


def _check(book: Book, rows: dict[int, BookChapter], start: int, end: int, parent_id: int | None,
           self_id: int | None = None) -> None:
    if not 1 <= start <= end <= book.page_count:
        raise BadRequest("Страницы главы — от 1 до {n}, начальная не больше конечной", n=book.page_count)
    if parent_id is not None:
        parent = rows.get(parent_id)
        if parent is None:
            raise NotFound("Глава не найдена")
        anc: int | None = parent_id
        while anc is not None:  # not itself, not one of its own sections
            if anc == self_id:
                raise BadRequest("Глава не может быть подразделом самой себя")
            anc = rows[anc].parent_id
        if not parent.start_page <= start <= end <= parent.end_page:
            raise BadRequest("Подраздел должен быть внутри страниц главы ({start}–{end})",
                             start=parent.start_page, end=parent.end_page)
        height = _height(rows, self_id) if self_id is not None else 1
        if _depth(rows, parent_id) + height > MAX_CHAPTER_DEPTH:
            raise BadRequest("Не больше трёх уровней вложенности")
    if self_id is not None:
        for c in rows.values():
            if c.parent_id == self_id and not start <= c.start_page <= c.end_page <= end:
                raise BadRequest("Подразделы выходят за страницы главы")


def create_chapter(db: Session, book: Book, data: ChapterIn) -> BookChapter:
    rows = {c.id: c for c in _chapters(db, book.id)}
    _check(book, rows, data.start_page, data.end_page, data.parent_id)
    siblings = [c.position for c in rows.values() if c.parent_id == data.parent_id]
    ch = BookChapter(book_id=book.id, parent_id=data.parent_id, title=data.title, start_page=data.start_page,
                     end_page=data.end_page, position=max(siblings, default=-1) + 1, origin=ChapterOrigin.MANUAL)
    db.add(ch)
    db.flush()
    return ch


def update_chapter(db: Session, book: Book, ch: BookChapter, data: ChapterUpdate) -> None:
    fields = data.model_fields_set
    rows = {c.id: c for c in _chapters(db, book.id)}
    start = data.start_page if "start_page" in fields and data.start_page is not None else ch.start_page
    end = data.end_page if "end_page" in fields and data.end_page is not None else ch.end_page
    parent_id = data.parent_id if "parent_id" in fields else ch.parent_id
    _check(book, rows, start, end, parent_id, self_id=ch.id)
    if "title" in fields and data.title:
        ch.title = data.title
    if "position" in fields and data.position is not None:
        ch.position = data.position
    ch.start_page, ch.end_page, ch.parent_id = start, end, parent_id
    ch.origin = ChapterOrigin.MANUAL  # edited by a methodist: kept when the book is processed again


def delete_chapter(db: Session, ch: BookChapter) -> None:
    db.delete(ch)  # its sections go with it (ON DELETE CASCADE)
    db.flush()



# ---------- question generation (stage 5) ----------

def generation_settings(db: Session, book: Book, data) -> dict:
    """The generate job's settings after every check a methodist can act on (400s)."""
    from app.core.config import settings
    from app.models.enums import BookStatus
    from app.services import ai_client
    from app.services import question_generator as qg

    if book.status != BookStatus.READY:
        raise Conflict("Книга ещё не обработана")
    if not ai_client.is_configured():
        raise BadRequest("Генерация вопросов не настроена: нет ключа AI")
    chapter_title = None
    if data.chapter_id is not None:
        ch = get_chapter(db, data.chapter_id)
        if ch.book_id != book.id:
            raise NotFound("Глава не найдена")
        start, end, chapter_title = ch.start_page, ch.end_page, ch.title
    else:
        start, end = data.page_start, data.page_end
    allowed = set(settings.AI_QUESTION_TYPES)
    if any(t.value not in allowed for t in data.types):
        raise BadRequest("Выберите типы вопросов")
    st = {
        "chapter_id": data.chapter_id, "chapter_title": chapter_title, "page_start": start, "page_end": end,
        "question_count": data.question_count, "types": [t.value for t in data.types],
        "difficulty": data.difficulty.value if data.difficulty else "mixed",
        "question_language": data.question_language if data.question_language in ("en", "ru") else "en",
        "level": (data.level or book.level).value if (data.level or book.level) else None,
    }
    gs = qg.settings_from_job(st)
    pages = [qg.PageText(p.page_number, p.text) for p in get_pages_any(db, book, start, end)]
    qg.check_settings(gs, pages)  # limits and "no text on these pages"
    return st


def get_pages_any(db: Session, book: Book, first: int, last: int) -> list[BookPage]:
    return list(db.scalars(
        select(BookPage).where(BookPage.book_id == book.id, BookPage.page_number.between(first, last))
        .order_by(BookPage.page_number)
    ).all())


def list_drafts(db: Session, book: Book, status=None, job_id: int | None = None) -> list[QuestionDraft]:
    q = select(QuestionDraft).where(QuestionDraft.book_id == book.id)
    if status is not None:
        q = q.where(QuestionDraft.status == status)
    if job_id is not None:
        q = q.where(QuestionDraft.job_id == job_id)
    return list(db.scalars(q.order_by(QuestionDraft.page_start, QuestionDraft.id)).all())



# ---------- review (stage 6) ----------

def get_draft(db: Session, draft_id: int, book: Book | None = None) -> QuestionDraft:
    d = db.get(QuestionDraft, draft_id)
    if d is None or (book is not None and d.book_id != book.id):
        raise NotFound("Вопрос не найден")
    return d


def _source_text(db: Session, d: QuestionDraft) -> str:
    return "\n".join(p.text for p in get_pages_any(db, db.get(Book, d.book_id), d.page_start, d.page_end))


def update_draft(db: Session, user: User, d: QuestionDraft, data) -> None:
    """Saves an edit; the checks run again and the draft goes back to review."""
    from datetime import UTC, datetime

    from app.services.question_generator import draft_warnings

    if d.status == DraftStatus.EXPORTED:
        raise Conflict("Вопрос уже в библиотеке")
    excerpt = (data.excerpt if data.excerpt is not None else d.excerpt).strip()
    d.question = data.question.model_dump(mode="json")
    d.difficulty = data.difficulty
    d.excerpt = excerpt
    d.warnings = draft_warnings(data.question, excerpt, _source_text(db, d))
    d.status, d.reviewed_by_id, d.reviewed_at = DraftStatus.DRAFT, None, None
    d.edited_by_id, d.updated_at = user.id, datetime.now(UTC)


def review(db: Session, user: User, book: Book, ids: list[int], action: str) -> list:
    """Approve / reject / back to review, one draft at a time: the server decides for each
    (a stale or forged list from the browser changes nothing it shouldn't)."""
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from app.schemas.book import ReviewResult
    from app.schemas.test import QuestionIn

    now = datetime.now(UTC)
    rows = {d.id: d for d in db.scalars(select(QuestionDraft).where(
        QuestionDraft.book_id == book.id, QuestionDraft.id.in_(ids)).with_for_update())}
    out = []
    for i in dict.fromkeys(ids):
        d = rows.get(i)
        if d is None:
            out.append(ReviewResult(id=i, ok=False, reason="not_found"))
            continue
        if d.status == DraftStatus.EXPORTED:
            out.append(ReviewResult(id=i, ok=False, status=d.status, reason="exported"))
            continue
        if action == "approve":
            try:
                QuestionIn.model_validate(d.question)  # stored drafts are checked again, never trusted
            except (ValidationError, ValueError):
                out.append(ReviewResult(id=i, ok=False, status=d.status, reason="invalid"))
                continue
            if "source_not_found" in (d.warnings or []):
                out.append(ReviewResult(id=i, ok=False, status=d.status, reason="needs_edit"))
                continue
            d.status = DraftStatus.APPROVED
        elif action == "reject":
            d.status = DraftStatus.REJECTED
        else:
            d.status = DraftStatus.DRAFT
        d.reviewed_by_id = user.id if action != "reset" else None
        d.reviewed_at = now if action != "reset" else None
        d.updated_at = now
        out.append(ReviewResult(id=i, ok=True, status=d.status))
    db.flush()
    return out


def regenerate_settings(db: Session, d: QuestionDraft) -> dict:
    """Settings for one replacement question from the same pages (a page around for context)."""
    from app.services import ai_client
    from app.models import BookJob

    if d.status not in (DraftStatus.DRAFT, DraftStatus.REJECTED):
        raise Conflict("Утверждённый вопрос нельзя перегенерировать: сначала верните его на проверку")
    if not ai_client.is_configured():
        raise BadRequest("Генерация вопросов не настроена: нет ключа AI")
    book = db.get(Book, d.book_id)
    source = db.get(BookJob, d.job_id).settings if d.job_id and db.get(BookJob, d.job_id) else {}
    start, end = max(1, d.page_start - 1), min(book.page_count, d.page_end + 1)
    others = db.scalars(select(QuestionDraft).where(
        QuestionDraft.book_id == book.id, QuestionDraft.status != DraftStatus.REJECTED,
        QuestionDraft.page_start.between(start, end))).all()
    return {
        "page_start": start, "page_end": end, "question_count": 1, "types": [d.question["type"]],
        "difficulty": d.difficulty.value, "question_language": source.get("question_language", "en"),
        "level": source.get("level") or (book.level.value if book.level else None),
        "avoid": [o.question.get("text", "") for o in others],
        "replace_draft_id": d.id,
    }

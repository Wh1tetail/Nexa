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
from app.core.exceptions import BadRequest, NotFound
from app.models import Attachment, Book, User
from app.schemas.book import BookOut, BookUpdate
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


def to_out(book: Book) -> BookOut:
    f = book.file
    return BookOut(
        id=book.id, title=book.title, author=book.author, language=book.language, level=book.level,
        page_count=book.page_count, status=book.status, error_code=book.error_code,
        uploaded_by_name=book.uploaded_by.full_name if book.uploaded_by else None,
        created_at=book.created_at, updated_at=book.updated_at,
        file=AttachmentOut.model_validate(f) if f else None,
    )

"""Book-to-Test: PDF books (methodists; admins through the same editor right).

Stage 1: upload, list, details, metadata, delete. Processing (text, chapters)
and question generation come in later stages.
"""
from fastapi import APIRouter, File, Form, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import DB, LibraryEditor
from app.models.enums import EnglishLevel
from app.schemas.book import BookLanguage, BookOut, BookUpdate
from app.services import book_service as svc

router = APIRouter(prefix="/books", tags=["books (Book-to-Test)"])


@router.get("", response_model=list[BookOut])
def list_books(_: LibraryEditor, db: DB) -> list[BookOut]:
    return [svc.to_out(b) for b in svc.list_books(db)]


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def upload_book(
    user: LibraryEditor,
    db: DB,
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str | None = Form(None),
    language: BookLanguage = Form("en"),
    level: EnglishLevel | None = Form(None),
) -> BookOut:
    # a plain def: FastAPI runs it in a worker thread, so reading a large PDF never blocks the loop
    try:
        meta = BookUpdate(title=title, author=author, language=language, level=level)
    except ValidationError as e:
        raise RequestValidationError(e.errors()) from None
    book = svc.create_book(db, user, file, meta)
    db.commit()
    return svc.to_out(svc.get_book(db, book.id))


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, _: LibraryEditor, db: DB) -> BookOut:
    return svc.to_out(svc.get_book(db, book_id))


@router.put("/{book_id}", response_model=BookOut)
def update_book(book_id: int, data: BookUpdate, _: LibraryEditor, db: DB) -> BookOut:
    book = svc.get_book(db, book_id)
    svc.update_book(book, data)
    db.commit()
    return svc.to_out(svc.get_book(db, book_id))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, _: LibraryEditor, db: DB) -> Response:
    keys = svc.delete_book(db, svc.get_book(db, book_id))
    db.commit()
    svc.delete_stored(keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

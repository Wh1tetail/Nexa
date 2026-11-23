"""Book-to-Test: PDF books (methodists; admins through the same editor right).

Stage 1: upload, list, details, metadata, delete.
Stage 2: an upload queues text extraction for the worker (app/worker.py);
jobs can be followed, cancelled and started again.
"""
from fastapi import APIRouter, File, Form, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import DB, LibraryEditor
from app.models.enums import EnglishLevel
from app.schemas.book import BookJobOut, BookLanguage, BookOut, BookUpdate
from app.services import book_jobs
from app.services import book_service as svc
from app.services.book_processing import start_processing

router = APIRouter(prefix="/books", tags=["books (Book-to-Test)"])


# ---------- jobs (declared before /{book_id}) ----------

@router.get("/jobs/{job_id}", response_model=BookJobOut)
def get_job(job_id: int, _: LibraryEditor, db: DB) -> BookJobOut:
    return BookJobOut.model_validate(book_jobs.get_job(db, job_id))


@router.post("/jobs/{job_id}/cancel", response_model=BookJobOut)
def cancel_job(job_id: int, _: LibraryEditor, db: DB) -> BookJobOut:
    job = book_jobs.cancel(db, book_jobs.get_job(db, job_id))
    db.commit()
    return BookJobOut.model_validate(job)


# ---------- books ----------

@router.get("", response_model=list[BookOut])
def list_books(_: LibraryEditor, db: DB) -> list[BookOut]:
    return [svc.to_out(b, db) for b in svc.list_books(db)]


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
    start_processing(db, book, user)  # the worker picks it up after the commit
    db.commit()
    return svc.to_out(svc.get_book(db, book.id), db)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, _: LibraryEditor, db: DB) -> BookOut:
    return svc.to_out(svc.get_book(db, book_id), db)


@router.put("/{book_id}", response_model=BookOut)
def update_book(book_id: int, data: BookUpdate, _: LibraryEditor, db: DB) -> BookOut:
    book = svc.get_book(db, book_id)
    svc.update_book(book, data)
    db.commit()
    return svc.to_out(svc.get_book(db, book_id), db)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, _: LibraryEditor, db: DB) -> Response:
    keys = svc.delete_book(db, svc.get_book(db, book_id))  # its jobs go with it (a running one stops)
    db.commit()
    svc.delete_stored(keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{book_id}/reprocess", response_model=BookOut)
def reprocess_book(book_id: int, user: LibraryEditor, db: DB) -> BookOut:
    book = svc.get_book(db, book_id)
    start_processing(db, book, user)
    db.commit()
    return svc.to_out(svc.get_book(db, book_id), db)


@router.get("/{book_id}/jobs", response_model=list[BookJobOut])
def list_jobs(book_id: int, _: LibraryEditor, db: DB) -> list[BookJobOut]:
    svc.get_book(db, book_id)
    return [BookJobOut.model_validate(j) for j in book_jobs.latest_jobs(db, book_id)]

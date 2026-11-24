"""Book-to-Test: PDF books (methodists; admins through the same editor right).

Stage 1: upload, list, details, metadata, delete.
Stage 2: an upload queues text extraction for the worker (app/worker.py);
jobs can be followed, cancelled and started again.
Stage 3: page texts and chapters (found in the PDF, edited by methodists).
Stage 5: AI question generation (a worker job) and its drafts.
Stage 6: review - edit, approve / reject (each checked by the server), regenerate one.
"""
from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import DB, LibraryEditor
from app.models.enums import EnglishLevel
from app.models.enums import BookJobKind, DraftStatus
from app.schemas.book import (
    BookJobOut,
    BookLanguage,
    BookOut,
    BookUpdate,
    ChapterIn,
    ChapterOut,
    ChapterUpdate,
    DraftOut,
    DraftUpdate,
    GenerateRequest,
    PageOut,
    ReviewRequest,
    ReviewResult,
)
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


@router.patch("/chapters/{chapter_id}", response_model=list[ChapterOut])
def update_chapter(chapter_id: int, data: ChapterUpdate, _: LibraryEditor, db: DB) -> list[ChapterOut]:
    ch = svc.get_chapter(db, chapter_id)
    book = svc.get_book(db, ch.book_id)
    svc.update_chapter(db, book, ch, data)
    db.commit()
    return svc.chapter_tree(db, book)


@router.delete("/chapters/{chapter_id}", response_model=list[ChapterOut])
def delete_chapter(chapter_id: int, _: LibraryEditor, db: DB) -> list[ChapterOut]:
    ch = svc.get_chapter(db, chapter_id)
    book = svc.get_book(db, ch.book_id)
    svc.delete_chapter(db, ch)
    db.commit()
    return svc.chapter_tree(db, book)


@router.put("/drafts/{draft_id}", response_model=DraftOut)
def update_draft(draft_id: int, data: DraftUpdate, user: LibraryEditor, db: DB) -> DraftOut:
    d = svc.get_draft(db, draft_id)
    svc.update_draft(db, user, d, data)
    db.commit()
    return DraftOut.model_validate(d)


@router.post("/drafts/{draft_id}/regenerate", response_model=BookJobOut, status_code=status.HTTP_202_ACCEPTED)
def regenerate_draft(draft_id: int, user: LibraryEditor, db: DB) -> BookJobOut:
    d = svc.get_draft(db, draft_id)
    book = svc.get_book(db, d.book_id)
    job = book_jobs.enqueue(db, book, BookJobKind.REGENERATE, user, svc.regenerate_settings(db, d))
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


@router.get("/{book_id}/pages", response_model=list[PageOut])
def get_pages(
    book_id: int, _: LibraryEditor, db: DB,
    first: int = Query(1, alias="from"), last: int = Query(10, alias="to"),
) -> list[PageOut]:
    book = svc.get_book(db, book_id)
    return [PageOut.model_validate(p) for p in svc.get_pages(db, book, first, last)]


@router.get("/{book_id}/chapters", response_model=list[ChapterOut])
def list_chapters(book_id: int, _: LibraryEditor, db: DB) -> list[ChapterOut]:
    return svc.chapter_tree(db, svc.get_book(db, book_id))


@router.post("/{book_id}/chapters", response_model=list[ChapterOut], status_code=status.HTTP_201_CREATED)
def create_chapter(book_id: int, data: ChapterIn, _: LibraryEditor, db: DB) -> list[ChapterOut]:
    book = svc.get_book(db, book_id)
    svc.create_chapter(db, book, data)
    db.commit()
    return svc.chapter_tree(db, book)



@router.post("/{book_id}/generate", response_model=BookJobOut, status_code=status.HTTP_202_ACCEPTED)
def generate_questions(book_id: int, data: GenerateRequest, user: LibraryEditor, db: DB) -> BookJobOut:
    book = svc.get_book(db, book_id)
    job = book_jobs.enqueue(db, book, BookJobKind.GENERATE, user, svc.generation_settings(db, book, data))
    db.commit()
    return BookJobOut.model_validate(job)


@router.get("/{book_id}/drafts", response_model=list[DraftOut])
def list_drafts(
    book_id: int, _: LibraryEditor, db: DB, status_: DraftStatus | None = Query(None, alias="status"),
    job_id: int | None = None,
) -> list[DraftOut]:
    book = svc.get_book(db, book_id)
    return [DraftOut.model_validate(d) for d in svc.list_drafts(db, book, status_, job_id)]



@router.post("/{book_id}/drafts/review", response_model=list[ReviewResult])
def review_drafts(book_id: int, data: ReviewRequest, user: LibraryEditor, db: DB) -> list[ReviewResult]:
    book = svc.get_book(db, book_id)
    out = svc.review(db, user, book, data.ids, data.action)
    db.commit()
    return out

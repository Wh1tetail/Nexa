"""Book-to-Test, stage 7: approved drafts go to the test library.

Only drafts a methodist approved are taken, and the server checks each again
(status, the test rules). They become a new unpublished library test, or are
added to the end of an existing one that is still unpublished: nothing is ever
published here. Every question keeps where it came from in `test_questions.source`
(book, pages, quote, difficulty), which only editors ever see.
"""
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.models import Book, QuestionDraft, Test, User
from app.models.enums import DraftStatus
from app.schemas.test import QuestionIn, TestSettings
from app.services import library_service as lib
from app.services import test_service

MAX_QUESTIONS = 200  # the same limit as a test saved in the editor


def _question(book: Book, d: QuestionDraft) -> QuestionIn:
    source = {
        "book_id": book.id, "book_title": book.title[:300], "page_start": d.page_start,
        "page_end": d.page_end, "excerpt": d.excerpt or None, "difficulty": d.difficulty.value,
    }
    try:
        return QuestionIn.model_validate({**d.question, "source": source})
    except (ValidationError, ValueError):
        raise BadRequest("Вопрос не проходит проверку теста: верните его на проверку и исправьте")


def export(db: Session, user: User, book: Book, data) -> Test:
    ids = list(dict.fromkeys(data.draft_ids))
    rows = {d.id: d for d in db.scalars(select(QuestionDraft).where(
        QuestionDraft.book_id == book.id, QuestionDraft.id.in_(ids)).with_for_update())}
    if any(i not in rows or rows[i].status != DraftStatus.APPROVED for i in ids):
        raise BadRequest("В библиотеку можно отправить только утверждённые вопросы этой книги")
    questions = [_question(book, rows[i]) for i in ids]
    now = datetime.now(UTC)

    if data.test_id is not None:
        test = db.scalar(select(Test).options(selectinload(Test.questions)).where(
            Test.id == data.test_id, Test.is_library.is_(True)).with_for_update())
        if test is None:
            raise NotFound("Тест не найден")
        if test.published:
            raise Conflict("Дополнить можно только неопубликованный тест библиотеки")
        if len(test.questions) + len(questions) > MAX_QUESTIONS:
            raise BadRequest("В тесте не больше {n} вопросов", n=MAX_QUESTIONS)
        test_service.append_questions(test, questions)
    else:
        test = Test(
            is_library=True, teacher_id=None, published=False, author_id=user.id,
            title=data.title, level=data.level or book.level, updated_at=now,
        )
        test_service.apply_settings(test, TestSettings())
        db.add(test)
        test_service.build_questions(test, questions)
        lib.set_sections(db, test, data.section_ids)
        lib.set_tags(db, test, data.tags)
    test.updated_at = now
    db.flush()
    for i in ids:
        d = rows[i]
        d.status, d.exported_test_id, d.updated_at = DraftStatus.EXPORTED, test.id, now
    db.flush()
    return test

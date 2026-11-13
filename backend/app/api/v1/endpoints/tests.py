"""Teacher-side test management."""
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import DB, CurrentTeacher, get_owned_student, resolve_recipients
from app.core.exceptions import BadRequest, NotFound
from app.models import StudentProfile, TeacherProfile, Test, TestAttempt
from app.models.enums import AttemptStatus
from app.schemas.test import (
    AssignRequest,
    AttemptDetail,
    AttemptSummary,
    GradeRequest,
    TestCreate,
    TestDetail,
    TestListItem,
    TestUpdate,
)
from app.services import test_service as svc

router = APIRouter(prefix="/tests", tags=["tests (teacher)"])


def _load(db: Session, teacher: TeacherProfile, test_id: int) -> Test:
    test = db.scalar(
        select(Test)
        .options(selectinload(Test.questions), selectinload(Test.students), selectinload(Test.attempts))
        .where(Test.id == test_id)
    )
    if test is None or test.teacher_id != teacher.id:
        raise NotFound("Тест не найден")
    return test


def _detail(test: Test) -> TestDetail:
    return TestDetail(
        id=test.id,
        title=test.title,
        description=test.description,
        time_limit_minutes=test.time_limit_minutes,
        due_at=test.due_at,
        created_at=test.created_at,
        questions=[svc.question_out(q, reveal=True) for q in test.questions],
        student_ids=[s.id for s in test.students],
        has_attempts=bool(test.attempts),
    )


def _load_attempt(db: Session, teacher: TeacherProfile, attempt_id: int) -> TestAttempt:
    a = db.get(TestAttempt, attempt_id)
    if a is None or a.test.teacher_id != teacher.id:
        raise NotFound("Попытка не найдена")
    return a


@router.get("", response_model=list[TestListItem])
def list_tests(teacher: CurrentTeacher, db: DB) -> list[TestListItem]:
    tests = db.scalars(
        select(Test)
        .options(selectinload(Test.questions), selectinload(Test.students), selectinload(Test.attempts))
        .where(Test.teacher_id == teacher.id)
        .order_by(Test.created_at.desc())
    ).all()
    return [
        TestListItem(
            id=t.id,
            title=t.title,
            description=t.description,
            time_limit_minutes=t.time_limit_minutes,
            due_at=t.due_at,
            created_at=t.created_at,
            questions_count=len(t.questions),
            assigned_count=len(t.students),
            completed_count=sum(1 for a in t.attempts if a.status != AttemptStatus.IN_PROGRESS),
            pending_review_count=sum(1 for a in t.attempts if a.status == AttemptStatus.PENDING_REVIEW),
        )
        for t in tests
    ]


@router.post("", response_model=TestDetail, status_code=status.HTTP_201_CREATED)
def create_test(data: TestCreate, teacher: CurrentTeacher, db: DB) -> TestDetail:
    students = resolve_recipients(db, teacher, data.student_ids, data.group_ids)
    test = Test(
        teacher_id=teacher.id,
        title=data.title,
        description=data.description,
        time_limit_minutes=data.time_limit_minutes,
        due_at=data.due_at,
    )
    db.add(test)
    svc.build_questions(test, data.questions)
    db.flush()
    svc.assign_students(db, test, students)
    db.commit()
    return _detail(_load(db, teacher, test.id))


@router.get("/attempts/all", response_model=list[AttemptSummary])
def list_all_attempts(
    teacher: CurrentTeacher, db: DB, student_id: int | None = None, status_filter: AttemptStatus | None = None
) -> list[AttemptSummary]:
    q = (
        select(TestAttempt)
        .join(TestAttempt.test)
        .options(
            selectinload(TestAttempt.test).selectinload(Test.questions),
            selectinload(TestAttempt.student).selectinload(StudentProfile.user),
        )
        .where(Test.teacher_id == teacher.id)
        .order_by(TestAttempt.submitted_at.desc().nulls_last())
    )
    if student_id:
        get_owned_student(db, teacher, student_id)
        q = q.where(TestAttempt.student_id == student_id)
    if status_filter:
        q = q.where(TestAttempt.status == status_filter)
    return [svc.attempt_summary(a) for a in db.scalars(q).all()]


@router.get("/attempts/{attempt_id}", response_model=AttemptDetail)
def get_attempt(attempt_id: int, teacher: CurrentTeacher, db: DB) -> AttemptDetail:
    return svc.attempt_detail(_load_attempt(db, teacher, attempt_id), for_teacher=True)


@router.post("/attempts/{attempt_id}/grade", response_model=AttemptDetail)
def grade_attempt(attempt_id: int, data: GradeRequest, teacher: CurrentTeacher, db: DB) -> AttemptDetail:
    attempt = _load_attempt(db, teacher, attempt_id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        raise BadRequest("Ученик ещё не завершил тест")
    answers = {a.id: a for a in attempt.answers}
    questions = {q.id: q for q in attempt.test.questions}
    for g in data.answers:
        ans = answers.get(g.answer_id)
        if ans is None:
            raise BadRequest("Ответ не относится к этой попытке")
        q = questions[ans.question_id]
        if g.points_awarded > q.points:
            raise BadRequest(f"Максимум за вопрос — {q.points} балл(ов)")
        ans.points_awarded = g.points_awarded
        ans.is_correct = g.points_awarded >= q.points
        ans.teacher_comment = g.teacher_comment
    if any(a.points_awarded is None for a in attempt.answers):
        raise BadRequest("Оцените все ответы, требующие проверки")
    svc.recompute_score(attempt)
    was_graded = attempt.status == AttemptStatus.GRADED
    attempt.status = AttemptStatus.GRADED
    attempt.graded_at = datetime.now(UTC)
    if not was_graded:
        svc.notify_graded(db, attempt)
    db.commit()
    return svc.attempt_detail(attempt, for_teacher=True)


@router.get("/{test_id}", response_model=TestDetail)
def get_test(test_id: int, teacher: CurrentTeacher, db: DB) -> TestDetail:
    return _detail(_load(db, teacher, test_id))


@router.put("/{test_id}", response_model=TestDetail)
def update_test(test_id: int, data: TestUpdate, teacher: CurrentTeacher, db: DB) -> TestDetail:
    test = _load(db, teacher, test_id)
    test.title = data.title
    test.description = data.description
    test.time_limit_minutes = data.time_limit_minutes
    test.due_at = data.due_at
    if test.attempts:
        # Questions are locked once someone started the test (results must stay consistent).
        existing = [(q.type, q.text, q.options, q.correct_answer, q.points) for q in test.questions]
        incoming = [(q.type, q.text, [o.model_dump() for o in q.options], q.correct_answer, q.points) for q in data.questions]
        if existing != incoming:
            raise BadRequest("Вопросы нельзя изменить: тест уже начали проходить")
    else:
        svc.build_questions(test, data.questions)
    svc.assign_students(db, test, resolve_recipients(db, teacher, data.student_ids, data.group_ids))
    db.commit()
    return _detail(_load(db, teacher, test_id))


@router.post("/{test_id}/assign", response_model=TestDetail)
def assign_test(test_id: int, data: AssignRequest, teacher: CurrentTeacher, db: DB) -> TestDetail:
    test = _load(db, teacher, test_id)
    svc.assign_students(db, test, resolve_recipients(db, teacher, data.student_ids, data.group_ids))
    db.commit()
    return _detail(_load(db, teacher, test_id))


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(test_id: int, teacher: CurrentTeacher, db: DB) -> Response:
    db.delete(_load(db, teacher, test_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{test_id}/attempts", response_model=list[AttemptSummary])
def list_attempts(test_id: int, teacher: CurrentTeacher, db: DB) -> list[AttemptSummary]:
    test = _load(db, teacher, test_id)
    return [svc.attempt_summary(a) for a in sorted(test.attempts, key=lambda a: a.started_at, reverse=True)]

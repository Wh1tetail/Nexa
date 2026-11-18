"""Teacher-side test management."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, File, Response, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import DB, CurrentTeacher, get_owned_student, resolve_recipients
from app.core.exceptions import BadRequest, NotFound
from app.core.i18n import M
from app.models import Attachment, StudentProfile, TeacherProfile, Test, TestAttempt
from app.models.enums import CONTENT_TYPES, AttemptStatus, NotificationType
from app.models.test import test_assignments
from app.schemas.test import (
    TestParticipant,
    UnassignRequest,
    AssignRequest,
    AttemptDetail,
    AttemptSummary,
    GradeRequest,
    TestCreate,
    TestDetail,
    TestListItem,
    TestUpdate,
)
from app.schemas.homework import AttachmentOut
from app.services import file_service
from app.services import participation
from app.services import test_service as svc
from app.services.notification_service import notify
from app.utils.files import validate_upload

MAX_TEST_FILES = 20

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
        files=[AttachmentOut.model_validate(f) for f in test.files],
        **svc.settings_of(test),
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
            files_count=len(t.files),
            **svc.settings_of(t),
            questions_count=sum(1 for q in t.questions if q.type not in CONTENT_TYPES),
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
    svc.apply_settings(test, data)
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
            raise BadRequest("Максимум за вопрос — {points} балл(ов)", points=q.points)
        ans.points_awarded = g.points_awarded
        ans.is_correct = g.points_awarded >= q.points
        ans.teacher_comment = g.teacher_comment
    if any(a.points_awarded is None for a in attempt.answers):
        raise BadRequest("Оцените все ответы, требующие проверки")
    old_score = attempt.score
    svc.recompute_score(attempt)  # any answer may be re-scored, auto-graded ones included
    was_graded = attempt.status == AttemptStatus.GRADED
    attempt.status = AttemptStatus.GRADED
    attempt.graded_at = datetime.now(UTC)
    if not was_graded:
        svc.notify_graded(db, attempt)
    elif attempt.score != old_score:
        svc.notify_graded(db, attempt, changed=True)
    from app.services import gamification

    gamification.on_test_graded(db, attempt)  # XP once per test; a later better grade can add the bonus
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
    svc.apply_settings(test, data)  # settings may change any time
    if test.attempts:
        # Questions are locked once someone started the test (results must stay consistent).
        def shape(type_, text, options, correct, points, explanation, files, config):
            return (type_, text, options, correct, points, explanation or None, list(files or []), config or {})

        existing = [shape(q.type, q.text, q.options, q.correct_answer, q.points, q.explanation, q.attachment_ids,
                          q.config) for q in test.questions]
        incoming = [shape(q.type, q.text, [o.model_dump() for o in q.options], q.correct_answer, q.points,
                          q.explanation, q.attachment_ids, q.config) for q in data.questions]
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


# ---------- materials ----------

@router.post("/{test_id}/files", response_model=list[AttachmentOut], status_code=status.HTTP_201_CREATED)
async def upload_test_files(
    test_id: int, teacher: CurrentTeacher, db: DB, files: list[UploadFile] = File(...)
) -> list[AttachmentOut]:
    """Reading texts, audio for listening, pictures. Same rules as homework files."""
    test = _load(db, teacher, test_id)
    if test.attempts:
        raise BadRequest("Материалы нельзя изменить: тест уже начали проходить")
    if len(test.files) + len(files) > MAX_TEST_FILES:
        raise BadRequest("Не более {n} файлов в тесте", n=MAX_TEST_FILES)
    validated = [await validate_upload(f) for f in files]  # nothing is stored if any file is rejected
    saved = [file_service.store_validated(db, vf, teacher.user, test_id=test.id) for vf in validated]
    db.commit()
    return [AttachmentOut.model_validate(a) for a in saved]


@router.delete("/{test_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_file(test_id: int, file_id: int, teacher: CurrentTeacher, db: DB) -> Response:
    test = _load(db, teacher, test_id)
    att = db.get(Attachment, file_id)
    if att is None or att.test_id != test.id:
        raise NotFound("Файл не найден")
    if test.attempts:
        raise BadRequest("Материалы нельзя изменить: тест уже начали проходить")
    for q in test.questions:  # questions stop showing it
        if file_id in (q.attachment_ids or []):
            q.attachment_ids = [i for i in q.attachment_ids if i != file_id]
    test.files.remove(att)
    file_service.delete_attachment(db, att)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/attempts/{attempt_id}/retake", status_code=status.HTTP_204_NO_CONTENT)
def allow_retake(attempt_id: int, teacher: CurrentTeacher, db: DB) -> Response:
    """Give the student one more attempt at this test. Earlier attempts and
    their results are kept; the extra attempt works even after the deadline."""
    attempt = _load_attempt(db, teacher, attempt_id)
    test, student = attempt.test, attempt.student
    granted = db.execute(
        update(test_assignments)
        .where(
            test_assignments.c.test_id == test.id, test_assignments.c.student_id == student.id,
            test_assignments.c.removed_at.is_(None),
        )
        .values(extra_attempts=test_assignments.c.extra_attempts + 1)
    ).rowcount
    if not granted:
        raise BadRequest("Тест больше не назначен этому ученику")
    notify(db, [student.user_id], NotificationType.TEST_ASSIGNED, M("Тест можно пройти ещё раз"), test.title,
           "/student/tests")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{test_id}/attempts", response_model=list[AttemptSummary])
def list_attempts(
    test_id: int, teacher: CurrentTeacher, db: DB, state: Literal["active", "removed", "all"] = "all"
) -> list[AttemptSummary]:
    """Results; state filters by whether the student is still assigned."""
    test = _load(db, teacher, test_id)
    rows = participation.test_rows(db, test.id)
    keep = {
        "all": lambda sid: True,
        "active": lambda sid: sid in rows and rows[sid] is None,
        "removed": lambda sid: sid not in rows or rows[sid] is not None,
    }[state]
    attempts = [a for a in test.attempts if keep(a.student_id)]
    return [svc.attempt_summary(a) for a in sorted(attempts, key=lambda a: a.started_at, reverse=True)]


@router.get("/{test_id}/participants", response_model=list[TestParticipant])
def list_participants(
    test_id: int, teacher: CurrentTeacher, db: DB, state: Literal["active", "removed", "all"] = "active"
) -> list[TestParticipant]:
    """Assigned students with their progress; excluded ones keep their results."""
    test = _load(db, teacher, test_id)
    rows = participation.test_rows(db, test.id)
    wanted = [sid for sid, removed in rows.items()
              if state == "all" or (state == "active") == (removed is None)]
    students = {s.id: s for s in db.scalars(
        select(StudentProfile).options(selectinload(StudentProfile.user)).where(StudentProfile.id.in_(wanted))
    ).all()}
    by_student: dict[int, list[TestAttempt]] = {}
    for a in sorted(test.attempts, key=lambda a: a.number):
        by_student.setdefault(a.student_id, []).append(a)
    out = []
    for sid in wanted:
        attempts = by_student.get(sid, [])
        best = svc.best_attempt(attempts)
        out.append(TestParticipant(
            student_id=sid, student_name=students[sid].user.full_name, removed_at=rows[sid],
            attempts_used=len(attempts), last_status=attempts[-1].status if attempts else None,
            best_percent=svc.percent(best) if best else None,
        ))
    return sorted(out, key=lambda p: (p.removed_at is not None, p.student_name))


@router.post("/{test_id}/unassign", response_model=TestDetail)
def unassign_test(test_id: int, data: UnassignRequest, teacher: CurrentTeacher, db: DB) -> TestDetail:
    """Exclude students: the test disappears for them; attempts and results stay."""
    test = _load(db, teacher, test_id)
    participation.unassign_test(db, test.id, set(data.student_ids))
    db.commit()
    db.expire_all()
    return _detail(_load(db, teacher, test_id))

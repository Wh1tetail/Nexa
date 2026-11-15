"""Student-side endpoints. Every query is scoped to the current student."""
from datetime import UTC, datetime

from fastapi import APIRouter, File, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import DB, CurrentStudent, StudentWithAccess
from app.core.exceptions import BadRequest, NotFound
from app.core.i18n import M
from app.models import Attachment, Homework, HomeworkSubmission, StudentProfile, Subscription, Test, TestAttempt
from app.models.enums import AttemptStatus, NotificationType, SubmissionStatus
from app.models.test import test_assignments
from app.schemas.homework import AttachmentOut, StudentHomework, SubmitRequest
from app.schemas.lesson import StudentAttendanceSummary
from app.schemas.subscription import SubscriptionOut
from app.schemas.test import AttemptDetail, SaveProgress, StudentTestItem, SubmitAttempt
from app.services import attendance_service as att_svc
from app.services import file_service
from app.services import homework_service as hw_svc
from app.services import subscription_service as sub_svc
from app.services import test_service as test_svc
from app.services.notification_service import notify

router = APIRouter(prefix="/me", tags=["student"])

EDITABLE = (SubmissionStatus.NEW, SubmissionStatus.IN_PROGRESS, SubmissionStatus.NEEDS_REVISION)


# ---------- subscription ----------

@router.get("/subscription", response_model=SubscriptionOut | None)
def my_subscription(student: CurrentStudent, db: DB) -> SubscriptionOut | None:
    sub = sub_svc.current_subscription(db, student.id)
    return sub_svc.to_out(sub) if sub else None


@router.get("/subscriptions", response_model=list[SubscriptionOut])
def my_subscriptions(student: CurrentStudent, db: DB) -> list[SubscriptionOut]:
    subs = db.scalars(
        select(Subscription).where(Subscription.student_id == student.id).order_by(Subscription.start_date.desc())
    ).all()
    return [sub_svc.to_out(s) for s in subs]


# ---------- homework ----------

def _submissions_query(student: StudentProfile):
    return (
        select(HomeworkSubmission)
        .join(HomeworkSubmission.homework)
        .options(
            selectinload(HomeworkSubmission.files),
            selectinload(HomeworkSubmission.homework).selectinload(Homework.attachments),
            selectinload(HomeworkSubmission.homework).selectinload(Homework.teacher),
        )
        .where(HomeworkSubmission.student_id == student.id)
    )


def _own_submission(db: Session, student: StudentProfile, submission_id: int) -> HomeworkSubmission:
    sub = db.scalar(_submissions_query(student).where(HomeworkSubmission.id == submission_id))
    if sub is None:
        raise NotFound("Задание не найдено")
    return sub


@router.get("/homework", response_model=list[StudentHomework])
def my_homework(
    student: StudentWithAccess, db: DB, status_filter: SubmissionStatus | None = None
) -> list[StudentHomework]:
    q = _submissions_query(student).order_by(Homework.due_at.asc().nulls_last(), Homework.created_at.desc())
    if status_filter:
        q = q.where(HomeworkSubmission.status == status_filter)
    return [hw_svc.to_student_view(s) for s in db.scalars(q).all()]


@router.get("/homework/{submission_id}", response_model=StudentHomework)
def my_homework_item(submission_id: int, student: StudentWithAccess, db: DB) -> StudentHomework:
    return hw_svc.to_student_view(_own_submission(db, student, submission_id))


@router.post("/homework/{submission_id}/start", response_model=StudentHomework)
def start_homework(submission_id: int, student: StudentWithAccess, db: DB) -> StudentHomework:
    sub = _own_submission(db, student, submission_id)
    if sub.status == SubmissionStatus.NEW:
        sub.status = SubmissionStatus.IN_PROGRESS
        db.commit()
    return hw_svc.to_student_view(sub)


@router.post(
    "/homework/{submission_id}/files", response_model=list[AttachmentOut], status_code=status.HTTP_201_CREATED
)
async def upload_files(
    submission_id: int, student: StudentWithAccess, db: DB, files: list[UploadFile] = File(...)
) -> list[AttachmentOut]:
    sub = _own_submission(db, student, submission_id)
    if sub.status not in EDITABLE:
        raise BadRequest("Работа уже отправлена на проверку")
    if len(sub.files) + len(files) > file_service.MAX_FILES_PER_OWNER:
        raise BadRequest("Не более {n} файлов", n=file_service.MAX_FILES_PER_OWNER)
    saved = [await file_service.store_upload(db, f, student.user, submission_id=sub.id) for f in files]
    if sub.status == SubmissionStatus.NEW:
        sub.status = SubmissionStatus.IN_PROGRESS
    db.commit()
    return [AttachmentOut.model_validate(a) for a in saved]


@router.delete("/homework/{submission_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(submission_id: int, file_id: int, student: StudentWithAccess, db: DB) -> Response:
    sub = _own_submission(db, student, submission_id)
    if sub.status not in EDITABLE:
        raise BadRequest("Работа уже отправлена на проверку")
    att = db.get(Attachment, file_id)
    if att is None or att.submission_id != sub.id:
        raise NotFound("Файл не найден")
    file_service.delete_attachment(db, att)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/homework/{submission_id}/submit", response_model=StudentHomework)
def submit_homework(
    submission_id: int, data: SubmitRequest, student: StudentWithAccess, db: DB
) -> StudentHomework:
    sub = _own_submission(db, student, submission_id)
    if sub.status not in EDITABLE:
        raise BadRequest("Работа уже отправлена на проверку")
    if not sub.files and not (data.student_comment and data.student_comment.strip()):
        raise BadRequest("Прикрепите файл или напишите ответ")
    sub.student_comment = data.student_comment
    sub.status = SubmissionStatus.SUBMITTED
    sub.submitted_at = datetime.now(UTC)
    notify(
        db,
        [sub.homework.teacher.user_id],
        NotificationType.HOMEWORK_SUBMITTED,
        M("Сдано домашнее задание"),
        f"{student.user.full_name}: «{sub.homework.title}»",
        f"/teacher/homework/{sub.homework_id}?submission={sub.id}",
    )
    db.commit()
    return hw_svc.to_student_view(sub)


# ---------- tests ----------

def _assigned_test(db: Session, student: StudentProfile, test_id: int) -> Test:
    test = db.scalar(
        select(Test)
        .join(test_assignments, test_assignments.c.test_id == Test.id)
        .options(selectinload(Test.questions))
        .where(Test.id == test_id, test_assignments.c.student_id == student.id)
    )
    if test is None:
        raise NotFound("Тест не найден")
    return test


def _own_attempt(db: Session, student: StudentProfile, attempt_id: int) -> TestAttempt:
    a = db.get(TestAttempt, attempt_id)
    if a is None or a.student_id != student.id:
        raise NotFound("Попытка не найдена")
    return a


@router.get("/tests", response_model=list[StudentTestItem])
def my_tests(student: StudentWithAccess, db: DB) -> list[StudentTestItem]:
    tests = db.scalars(
        select(Test)
        .join(test_assignments, test_assignments.c.test_id == Test.id)
        .options(selectinload(Test.questions))
        .where(test_assignments.c.student_id == student.id)
        .order_by(Test.created_at.desc())
    ).all()
    attempts = {
        a.test_id: a
        for a in db.scalars(select(TestAttempt).where(TestAttempt.student_id == student.id)).all()
    }
    return [test_svc.student_item(t, attempts.get(t.id)) for t in tests]


@router.post("/tests/{test_id}/start", response_model=AttemptDetail)
def start_test(test_id: int, student: StudentWithAccess, db: DB) -> AttemptDetail:
    test = _assigned_test(db, student, test_id)
    attempt = db.scalar(
        select(TestAttempt).where(TestAttempt.test_id == test.id, TestAttempt.student_id == student.id)
    )
    if attempt is None:
        if not test_svc.is_available(test):
            raise BadRequest("Тест ещё не открыт")
        if test.due_at and test.due_at < datetime.now(UTC):
            raise BadRequest("Срок сдачи теста истёк")
        attempt = TestAttempt(
            test_id=test.id,
            student_id=student.id,
            started_at=datetime.now(UTC),
            max_score=float(sum(q.points for q in test.questions)),
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
    elif attempt.status == AttemptStatus.IN_PROGRESS and test_svc.is_time_over(attempt):
        # time ran out while the student was away: submit what was saved
        test_svc.finalize(db, attempt, {a.question_id: a.answer for a in attempt.answers})
        db.commit()
    return test_svc.attempt_detail(attempt, for_teacher=False)


@router.put("/tests/attempts/{attempt_id}/progress", response_model=AttemptDetail)
def save_progress(attempt_id: int, data: SaveProgress, student: StudentWithAccess, db: DB) -> AttemptDetail:
    attempt = _own_attempt(db, student, attempt_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise BadRequest("Тест уже завершён")
    if test_svc.is_time_over(attempt):
        raise BadRequest("Время на прохождение теста истекло")
    test_svc.save_answers(attempt, {a.question_id: a.answer for a in data.answers})
    db.commit()
    return test_svc.attempt_detail(attempt, for_teacher=False)


@router.post("/tests/attempts/{attempt_id}/submit", response_model=AttemptDetail)
def submit_test(attempt_id: int, data: SubmitAttempt, student: StudentWithAccess, db: DB) -> AttemptDetail:
    attempt = _own_attempt(db, student, attempt_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise BadRequest("Тест уже завершён")
    incoming = {a.question_id: a.answer for a in data.answers}
    if test_svc.is_time_over(attempt):
        # Late submission: only previously saved answers count.
        incoming = {a.question_id: a.answer for a in attempt.answers}
    test_svc.finalize(db, attempt, incoming)
    db.commit()
    db.refresh(attempt)
    return test_svc.attempt_detail(attempt, for_teacher=False)


@router.get("/tests/attempts/{attempt_id}", response_model=AttemptDetail)
def get_my_attempt(attempt_id: int, student: StudentWithAccess, db: DB) -> AttemptDetail:
    return test_svc.attempt_detail(_own_attempt(db, student, attempt_id), for_teacher=False)


# ---------- attendance ----------

@router.get("/attendance", response_model=StudentAttendanceSummary)
def my_attendance(student: StudentWithAccess, db: DB) -> StudentAttendanceSummary:
    rows = list(db.scalars(att_svc.records_query(student_id=student.id)).unique().all())
    return StudentAttendanceSummary(
        stats=att_svc.build_stats(student, rows),
        lessons=[att_svc.to_my_lesson(r) for r in rows],
    )

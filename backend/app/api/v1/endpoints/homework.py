"""Teacher-side homework management."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, File, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import DB, CurrentTeacher, get_owned_student, resolve_recipients
from app.core.exceptions import BadRequest, NotFound
from app.core.i18n import M
from app.models import Attachment, Homework, HomeworkSubmission, StudentProfile, TeacherProfile, User
from app.models.enums import NotificationType, SubmissionStatus
from app.schemas.homework import (
    HomeworkUnassign,
    AttachmentOut,
    HomeworkCreate,
    HomeworkDetail,
    HomeworkListItem,
    HomeworkUpdate,
    ReviewRequest,
    SubmissionOut,
)
from app.services import file_service
from app.services import homework_service as svc
from app.services.notification_service import notify

router = APIRouter(prefix="/homework", tags=["homework (teacher)"])


def _load(db: Session, teacher: TeacherProfile, hw_id: int) -> Homework:
    hw = db.scalar(
        select(Homework)
        .options(
            selectinload(Homework.attachments),
            selectinload(Homework.submissions).selectinload(HomeworkSubmission.files),
            selectinload(Homework.submissions)
            .selectinload(HomeworkSubmission.student)
            .selectinload(StudentProfile.user),
        )
        .where(Homework.id == hw_id)
    )
    if hw is None or hw.teacher_id != teacher.id:
        raise NotFound("Задание не найдено")
    return hw


def _teacher_user(teacher: TeacherProfile) -> User:
    return teacher.user


@router.get("", response_model=list[HomeworkListItem])
def list_homework(teacher: CurrentTeacher, db: DB, search: str | None = None) -> list[HomeworkListItem]:
    q = (
        select(Homework)
        .options(selectinload(Homework.submissions))
        .where(Homework.teacher_id == teacher.id)
        .order_by(Homework.created_at.desc())
    )
    if search:
        q = q.where(Homework.title.ilike(f"%{search.strip()}%"))
    return [svc.to_list_item(h) for h in db.scalars(q).all()]


@router.post("", response_model=HomeworkDetail, status_code=status.HTTP_201_CREATED)
def create_homework(data: HomeworkCreate, teacher: CurrentTeacher, db: DB) -> HomeworkDetail:
    students = resolve_recipients(db, teacher, data.student_ids, data.group_ids)
    if not students:
        raise BadRequest("В выбранных группах нет учеников")
    hw = Homework(
        teacher_id=teacher.id,
        title=data.title,
        description=data.description,
        due_at=data.due_at,
        max_grade=data.max_grade,
        group_id=data.group_ids[0] if len(data.group_ids) == 1 else None,
    )
    db.add(hw)
    db.flush()
    svc.assign(db, hw, students)
    db.commit()
    return svc.to_detail(_load(db, teacher, hw.id))


@router.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(
    teacher: CurrentTeacher,
    db: DB,
    student_id: int | None = None,
    status_filter: SubmissionStatus | None = None,
    state: Literal["active", "removed", "all"] = "active",
) -> list[SubmissionOut]:
    q = (
        select(HomeworkSubmission)
        .join(HomeworkSubmission.homework)
        .options(
            selectinload(HomeworkSubmission.files),
            selectinload(HomeworkSubmission.student).selectinload(StudentProfile.user),
        )
        .where(Homework.teacher_id == teacher.id)
        .order_by(HomeworkSubmission.submitted_at.desc().nulls_last(), HomeworkSubmission.id.desc())
    )
    if student_id:
        get_owned_student(db, teacher, student_id)
        q = q.where(HomeworkSubmission.student_id == student_id)
    if status_filter:
        q = q.where(HomeworkSubmission.status == status_filter)
    if state == "active":
        q = q.where(HomeworkSubmission.removed_at.is_(None))
    elif state == "removed":
        q = q.where(HomeworkSubmission.removed_at.is_not(None))
    return [svc.submission_out(s) for s in db.scalars(q).all()]


@router.get("/student/{student_id}/history")
def student_history(student_id: int, teacher: CurrentTeacher, db: DB) -> list[dict]:
    """Homework history of a student (with titles) for the profile page."""
    get_owned_student(db, teacher, student_id)
    subs = db.scalars(
        select(HomeworkSubmission)
        .join(HomeworkSubmission.homework)
        .options(selectinload(HomeworkSubmission.homework))
        .where(HomeworkSubmission.student_id == student_id, Homework.teacher_id == teacher.id)
        .order_by(Homework.created_at.desc())
    ).all()
    return [
        {
            "submission_id": s.id,
            "homework_id": s.homework_id,
            "title": s.homework.title,
            "due_at": s.homework.due_at,
            "status": s.status,
            "grade": s.grade,
            "max_grade": s.homework.max_grade,
            "submitted_at": s.submitted_at,
        }
        for s in subs
    ]


@router.get("/{hw_id}", response_model=HomeworkDetail)
def get_homework(hw_id: int, teacher: CurrentTeacher, db: DB) -> HomeworkDetail:
    return svc.to_detail(_load(db, teacher, hw_id))


@router.patch("/{hw_id}", response_model=HomeworkDetail)
def update_homework(hw_id: int, data: HomeworkUpdate, teacher: CurrentTeacher, db: DB) -> HomeworkDetail:
    hw = _load(db, teacher, hw_id)
    payload = data.model_dump(exclude_unset=True, exclude={"add_student_ids", "add_group_ids"})
    for k, v in payload.items():
        if v is not None or k in ("description", "due_at"):
            setattr(hw, k, v)
    if data.add_student_ids or data.add_group_ids:
        svc.assign(db, hw, resolve_recipients(db, teacher, data.add_student_ids, data.add_group_ids))
    db.commit()
    return svc.to_detail(_load(db, teacher, hw_id))


@router.post("/{hw_id}/unassign", response_model=HomeworkDetail)
def unassign_homework(hw_id: int, data: HomeworkUnassign, teacher: CurrentTeacher, db: DB) -> HomeworkDetail:
    """Exclude students from the task (also single students of a group task)."""
    hw = _load(db, teacher, hw_id)
    svc.unassign(hw, set(data.student_ids))
    db.commit()
    return svc.to_detail(_load(db, teacher, hw_id))


@router.delete("/{hw_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_homework(hw_id: int, teacher: CurrentTeacher, db: DB) -> Response:
    hw = _load(db, teacher, hw_id)
    keys = [a.storage_key for a in hw.attachments] + [f.storage_key for s in hw.submissions for f in s.files]
    db.delete(hw)
    db.commit()
    from app.storage.base import get_storage

    for k in keys:
        get_storage().delete(k)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{hw_id}/attachments", response_model=list[AttachmentOut], status_code=status.HTTP_201_CREATED)
async def upload_attachments(
    hw_id: int, teacher: CurrentTeacher, db: DB, files: list[UploadFile] = File(...)
) -> list[AttachmentOut]:
    hw = _load(db, teacher, hw_id)
    if len(hw.attachments) + len(files) > file_service.MAX_FILES_PER_OWNER:
        raise BadRequest("Не более {n} файлов на задание", n=file_service.MAX_FILES_PER_OWNER)
    saved = [await file_service.store_upload(db, f, teacher.user, homework_id=hw.id) for f in files]
    db.commit()
    return [AttachmentOut.model_validate(a) for a in saved]


@router.delete("/{hw_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(hw_id: int, attachment_id: int, teacher: CurrentTeacher, db: DB) -> Response:
    _load(db, teacher, hw_id)
    att = db.get(Attachment, attachment_id)
    if att is None or att.homework_id != hw_id:
        raise NotFound("Файл не найден")
    file_service.delete_attachment(db, att)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/submissions/{submission_id}/review", response_model=SubmissionOut)
def review_submission(
    submission_id: int, data: ReviewRequest, teacher: CurrentTeacher, db: DB
) -> SubmissionOut:
    sub = db.get(HomeworkSubmission, submission_id)
    if sub is None or sub.homework.teacher_id != teacher.id:
        raise NotFound("Работа не найдена")
    if data.grade is not None and data.grade > sub.homework.max_grade:
        raise BadRequest("Оценка не может быть больше {max}", max=sub.homework.max_grade)
    sub.status = data.status
    sub.grade = data.grade
    sub.teacher_comment = data.teacher_comment
    if data.status in (SubmissionStatus.REVIEWED, SubmissionStatus.NEEDS_REVISION):
        sub.reviewed_at = datetime.now(UTC)
        title = M(
            "Домашнее задание проверено"
            if data.status == SubmissionStatus.REVIEWED
            else "Домашнее задание требует исправления"
        )
        body = (
            M("{title} — оценка {grade}/{max}", title=sub.homework.title, grade=sub.grade, max=sub.homework.max_grade)
            if sub.grade is not None
            else sub.homework.title
        )
        notify(db, [sub.student.user_id], NotificationType.HOMEWORK_REVIEWED, title, body,
               f"/student/homework/{sub.id}")
    db.commit()
    db.refresh(sub)
    return svc.submission_out(sub)

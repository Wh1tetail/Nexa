import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import Forbidden, NotFound
from app.models import Attachment, HomeworkSubmission, User
from app.models.enums import UserRole
from app.storage.base import get_storage
from app.utils.files import validate_upload

MAX_FILES_PER_OWNER = 10


async def store_upload(
    db: Session,
    upload: UploadFile,
    uploader: User,
    *,
    homework_id: int | None = None,
    submission_id: int | None = None,
) -> Attachment:
    vf = await validate_upload(upload)
    now = datetime.now(UTC)
    # random key: original names never touch the filesystem
    key = f"{now:%Y/%m}/{uuid.uuid4().hex}.{vf.extension}"
    get_storage().save(key, vf.data, vf.mime_type)
    att = Attachment(
        uploaded_by_id=uploader.id,
        homework_id=homework_id,
        submission_id=submission_id,
        original_name=vf.original_name,
        storage_key=key,
        mime_type=vf.mime_type,
        size_bytes=len(vf.data),
    )
    db.add(att)
    return att


def delete_attachment(db: Session, att: Attachment) -> None:
    key = att.storage_key
    db.delete(att)
    db.flush()
    get_storage().delete(key)


def get_accessible_attachment(db: Session, user: User, attachment_id: int) -> Attachment:
    """Access rules:
    - teacher: files of their own homework and of submissions to it
    - student: materials of homework assigned to them, and their own submission files
    - admin: everything
    """
    att = db.get(Attachment, attachment_id)
    if att is None:
        raise NotFound("Файл не найден")
    if user.role == UserRole.ADMIN:
        return att

    if att.homework_id is not None:
        from app.models import Homework

        hw = db.get(Homework, att.homework_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and hw.teacher_id == user.teacher_profile.id:
            return att
        if user.role == UserRole.STUDENT and user.student_profile:
            assigned = any(s.student_id == user.student_profile.id for s in hw.submissions)
            if assigned:
                return att
    elif att.submission_id is not None:
        sub = db.get(HomeworkSubmission, att.submission_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and sub.homework.teacher_id == user.teacher_profile.id:
            return att
        if user.role == UserRole.STUDENT and user.student_profile and sub.student_id == user.student_profile.id:
            return att
    raise Forbidden("Нет доступа к файлу")

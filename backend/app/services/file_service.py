import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import Forbidden, NotFound
from app.models import Attachment, HomeworkSubmission, User
from app.models.enums import UserRole
from app.storage.base import get_storage
from app.utils.files import ValidatedFile, validate_upload

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
    return store_validated(db, vf, uploader, homework_id=homework_id, submission_id=submission_id)


def store_validated(
    db: Session,
    vf: ValidatedFile,
    uploader: User,
    *,
    homework_id: int | None = None,
    submission_id: int | None = None,
    message_id: int | None = None,
    test_id: int | None = None,
) -> Attachment:
    """Save an already validated file and add its row to the session (caller commits)."""
    now = datetime.now(UTC)
    # random key: original names never touch the filesystem
    key = f"{now:%Y/%m}/{uuid.uuid4().hex}.{vf.extension}"
    get_storage().save(key, vf.data, vf.mime_type)
    att = Attachment(
        uploaded_by_id=uploader.id,
        homework_id=homework_id,
        submission_id=submission_id,
        message_id=message_id,
        test_id=test_id,
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


def _student_access(db: Session, user: User) -> bool:
    from app.services.subscription_service import has_access

    return has_access(db, user.student_profile.id)


def get_accessible_attachment(db: Session, user: User, attachment_id: int) -> Attachment:
    """Access rules:
    - teacher: files of their own homework and of submissions to it
    - student: materials of homework assigned to them, and their own submission files
    - chat files: only the two participants of the conversation (not even admins)
    - test materials: the test's teacher; a student once they have started the test
    - admin: everything else
    """
    att = db.get(Attachment, attachment_id)
    if att is None:
        raise NotFound("Файл не найден")
    if att.message_id is not None:
        from app.services.message_service import can_access_message

        if can_access_message(db, user, att.message_id):
            return att
        raise NotFound("Файл не найден")
    if user.role == UserRole.ADMIN:
        return att

    if att.test_id is not None:
        from app.models import Test, TestAttempt

        test = db.get(Test, att.test_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and test.teacher_id == user.teacher_profile.id:
            return att
        # students only once they have started the test (no peeking at a listening task)
        if user.role == UserRole.STUDENT and user.student_profile and _student_access(db, user):
            started = db.query(TestAttempt.id).filter_by(test_id=test.id, student_id=user.student_profile.id).first()
            if started:
                return att
        raise NotFound("Файл не найден")

    if att.homework_id is not None:
        from app.models import Homework

        hw = db.get(Homework, att.homework_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and hw.teacher_id == user.teacher_profile.id:
            return att
        if user.role == UserRole.STUDENT and user.student_profile and _student_access(db, user):
            assigned = any(s.student_id == user.student_profile.id for s in hw.submissions)
            if assigned:
                return att
    elif att.submission_id is not None:
        sub = db.get(HomeworkSubmission, att.submission_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and sub.homework.teacher_id == user.teacher_profile.id:
            return att
        if (user.role == UserRole.STUDENT and user.student_profile and sub.student_id == user.student_profile.id
                and _student_access(db, user)):
            return att
    raise Forbidden("Нет доступа к файлу")

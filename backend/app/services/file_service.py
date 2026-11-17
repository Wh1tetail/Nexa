import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import select
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
    course_lesson_id: int | None = None,
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
        course_lesson_id=course_lesson_id,
        original_name=vf.original_name,
        storage_key=key,
        mime_type=vf.mime_type,
        size_bytes=len(vf.data),
    )
    db.add(att)
    return att


def duplicate_attachment(db: Session, f: Attachment, uploader: User, **owner: int) -> Attachment:
    """A copy of a stored file with its own storage object (deleting one never
    removes the other), attached to `owner` (e.g. test_id=..., course_lesson_id=...)."""
    storage = get_storage()
    data = b"".join(storage.open(f.storage_key))
    ext = f.storage_key.rsplit(".", 1)[-1]
    key = f"{datetime.now(UTC):%Y/%m}/{uuid.uuid4().hex}.{ext}"
    storage.save(key, data, f.mime_type)
    att = Attachment(uploaded_by_id=uploader.id, original_name=f.original_name, storage_key=key,
                     mime_type=f.mime_type, size_bytes=f.size_bytes, **owner)
    db.add(att)
    db.flush()
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
    - course lesson materials: methodists; teachers once the lesson and course are published;
      students while the lesson is in one of their started assignments
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

    if att.course_lesson_id is not None:  # course materials: editors; teachers once published
        from app.models import CourseLesson

        les = db.get(CourseLesson, att.course_lesson_id)
        if user.role == UserRole.METHODIST:
            return att
        if user.role == UserRole.TEACHER and les.published and les.module.level.course.published:
            return att
        if user.role == UserRole.STUDENT and user.student_profile and _student_access(db, user):
            from app.services.course_progress import can_open_lesson_file

            if can_open_lesson_file(db, user.student_profile, les.id):
                return att
        raise NotFound("Файл не найден")

    if att.test_id is not None:
        from app.models import Test, TestAttempt

        test = db.get(Test, att.test_id)
        if test.is_library:  # shared library: editors always, teachers once published
            if user.role == UserRole.METHODIST or (user.role == UserRole.TEACHER and test.published):
                return att
            raise NotFound("Файл не найден")
        if user.role == UserRole.TEACHER and user.teacher_profile and test.teacher_id == user.teacher_profile.id:
            return att
        # students only once they have started the test (no peeking at a listening task)
        if user.role == UserRole.STUDENT and user.student_profile and _student_access(db, user):
            from app.models.test import test_assignments as ta

            sid = user.student_profile.id
            started = db.query(TestAttempt.id).filter_by(test_id=test.id, student_id=sid).first()
            assigned = db.execute(select(ta.c.student_id).where(
                ta.c.test_id == test.id, ta.c.student_id == sid, ta.c.removed_at.is_(None)
            )).first()
            if started and assigned:
                return att
        raise NotFound("Файл не найден")

    if att.homework_id is not None:
        from app.models import Homework

        hw = db.get(Homework, att.homework_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and hw.teacher_id == user.teacher_profile.id:
            return att
        if user.role == UserRole.STUDENT and user.student_profile and _student_access(db, user):
            assigned = any(s.student_id == user.student_profile.id and s.removed_at is None for s in hw.submissions)
            if assigned:
                return att
    elif att.submission_id is not None:
        sub = db.get(HomeworkSubmission, att.submission_id)
        if user.role == UserRole.TEACHER and user.teacher_profile and sub.homework.teacher_id == user.teacher_profile.id:
            return att
        if (user.role == UserRole.STUDENT and user.student_profile and sub.student_id == user.student_profile.id
                and sub.removed_at is None and _student_access(db, user)):
            return att
    raise Forbidden("Нет доступа к файлу")

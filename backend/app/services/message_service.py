"""Teacher <-> student chat.

A conversation is the (teacher_id, student_id) pair, and only the student's
CURRENT teacher can take part in it: a teacher sees threads with their own
students, a student sees one thread with their teacher. Anything else is 404.

New messages and read receipts are pushed over the realtime stream as `chat`
events (inside the transaction, so they are delivered only on commit):
  {"type": "message", "student_id", "teacher_id", "message_id",
   "sender_user_id", "sender_name", "preview"}
  {"type": "read", "student_id", "teacher_id", "reader_user_id", "up_to_id"}
The client refetches the thread; the payload stays small (pg_notify limit).
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import UploadFile
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Forbidden, NotFound
from app.core.i18n import tr
from app.models import Message, StudentProfile, TeacherProfile, User
from app.models.enums import UserRole
from app.models.message import MAX_MESSAGE_LENGTH
from app.services import file_service
from app.services.realtime import publish
from app.utils.files import validate_upload

PREVIEW_LENGTH = 200
MAX_PAGE = 100
MAX_FILES_PER_MESSAGE = 5
ONLY_PARTICIPANTS = "Сообщения доступны только преподавателям и ученикам"


@dataclass
class Thread:
    teacher: TeacherProfile
    student: StudentProfile
    me: User
    partner: User

    @property
    def user_ids(self) -> list[int]:
        return [self.teacher.user_id, self.student.user_id]


def get_thread(db: Session, user: User, student_id: int) -> Thread:
    """Resolve a conversation the user may access (404 for anything foreign)."""
    if user.role == UserRole.TEACHER and user.teacher_profile is not None:
        student = db.get(StudentProfile, student_id)
        if student is None or student.teacher_id != user.teacher_profile.id:
            raise NotFound("Диалог не найден")
        return Thread(user.teacher_profile, student, user, student.user)
    if user.role == UserRole.STUDENT and user.student_profile is not None:
        student = user.student_profile
        if student.id != student_id or student.teacher is None:
            raise NotFound("Диалог не найден")
        return Thread(student.teacher, student, user, student.teacher.user)
    raise Forbidden(ONLY_PARTICIPANTS)


def _in_thread(teacher_id: int, student_id: int):
    return and_(Message.teacher_id == teacher_id, Message.student_id == student_id)


def list_messages(db: Session, thread: Thread, before_id: int | None, limit: int) -> list[Message]:
    """The newest `limit` messages (older than `before_id` if given), oldest first."""
    q = select(Message).where(_in_thread(thread.teacher.id, thread.student.id))
    if before_id is not None:
        q = q.where(Message.id < before_id)
    rows = db.scalars(q.order_by(Message.id.desc()).limit(max(1, min(limit, MAX_PAGE)))).all()
    return list(reversed(rows))


def _push(db: Session, thread: Thread, event: dict[str, Any]) -> None:
    # both participants: the partner gets it, the sender's other tabs/devices stay in sync
    publish(db, [{"user_id": uid, "chat": event} for uid in thread.user_ids])


def _check_can_send(thread: Thread) -> None:
    if not thread.partner.is_active:
        raise BadRequest("Пользователь деактивирован — отправка сообщений недоступна")


def preview(msg: Message, lang: str | None = None) -> str:
    """Short text for toasts and e-mails: the text, or the attached file names."""
    if msg.body:
        return msg.body[:PREVIEW_LENGTH]
    names = [a.original_name for a in msg.attachments]
    if not names:
        return ""
    if len(names) > 1:
        return tr("📎 {name} и ещё {n}", lang, name=names[0], n=len(names) - 1)[:PREVIEW_LENGTH]
    return tr("📎 {name}", lang, name=names[0])[:PREVIEW_LENGTH]


def _new_message(db: Session, thread: Thread, body: str) -> Message:
    msg = Message(
        teacher_id=thread.teacher.id, student_id=thread.student.id,
        sender_user_id=thread.me.id, body=body,
    )
    db.add(msg)
    db.flush()
    return msg


def _publish_and_commit(db: Session, thread: Thread, msg: Message) -> Message:
    db.flush()
    db.refresh(msg, ["attachments"])
    _push(db, thread, {
        "type": "message", "student_id": thread.student.id, "teacher_id": thread.teacher.id,
        "message_id": msg.id, "sender_user_id": thread.me.id, "sender_name": thread.me.full_name,
        "preview": preview(msg, thread.partner.locale),  # the toast is shown to the partner
    })
    db.commit()
    db.refresh(msg)
    return msg


def send_message(db: Session, thread: Thread, body: str) -> Message:
    _check_can_send(thread)
    return _publish_and_commit(db, thread, _new_message(db, thread, body))


async def send_files(db: Session, thread: Thread, body: str, uploads: list[UploadFile]) -> Message:
    """A message with 1..5 files and an optional caption."""
    _check_can_send(thread)
    body = body.strip()
    if len(body) > MAX_MESSAGE_LENGTH:
        raise BadRequest("Сообщение не может быть длиннее {n} символов", n=MAX_MESSAGE_LENGTH)
    uploads = [u for u in uploads if u.filename]
    if not uploads:
        raise BadRequest("Выберите файл")
    if len(uploads) > MAX_FILES_PER_MESSAGE:
        raise BadRequest("Не более {n} файлов в одном сообщении", n=MAX_FILES_PER_MESSAGE)
    # validate everything first: nothing is stored if any file is rejected
    validated = [await validate_upload(u) for u in uploads]
    msg = _new_message(db, thread, body)
    for vf in validated:
        file_service.store_validated(db, vf, thread.me, message_id=msg.id)
    return _publish_and_commit(db, thread, msg)


def can_access_message(db: Session, user: User, message_id: int) -> bool:
    """True only for the two participants (student and their current teacher)."""
    msg = db.get(Message, message_id)
    if msg is None:
        return False
    try:
        thread = get_thread(db, user, msg.student_id)
    except (NotFound, Forbidden):
        return False
    return thread.teacher.id == msg.teacher_id


def mark_read(db: Session, thread: Thread) -> int:
    """Mark everything the partner sent in this thread as read by me."""
    ids = list(db.scalars(
        update(Message)
        .where(
            _in_thread(thread.teacher.id, thread.student.id),
            Message.sender_user_id != thread.me.id,
            Message.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
        .returning(Message.id)
    ).all())
    if ids:
        _push(db, thread, {
            "type": "read", "student_id": thread.student.id, "teacher_id": thread.teacher.id,
            "reader_user_id": thread.me.id, "up_to_id": max(ids),
        })
    db.commit()
    return len(ids)


def _unread_by_student(db: Session, user: User, teacher_id: int, student_ids: list[int] | None) -> dict[int, int]:
    q = (
        select(Message.student_id, func.count())
        .where(Message.teacher_id == teacher_id, Message.read_at.is_(None), Message.sender_user_id != user.id)
        .group_by(Message.student_id)
    )
    if student_ids is not None:
        q = q.where(Message.student_id.in_(student_ids))
    return {sid: n for sid, n in db.execute(q).all()}


def list_threads(db: Session, user: User) -> list[dict[str, Any]]:
    if user.role == UserRole.TEACHER and user.teacher_profile is not None:
        teacher = user.teacher_profile
        students = db.scalars(select(StudentProfile).where(StudentProfile.teacher_id == teacher.id)).all()
        pairs = [(teacher, s) for s in students]
    elif user.role == UserRole.STUDENT and user.student_profile is not None:
        student = user.student_profile
        pairs = [(student.teacher, student)] if student.teacher else []
    else:
        raise Forbidden(ONLY_PARTICIPANTS)
    if not pairs:
        return []

    teacher_id = pairs[0][0].id
    student_ids = [s.id for _, s in pairs]
    last_ids = (
        select(func.max(Message.id))
        .where(Message.teacher_id == teacher_id, Message.student_id.in_(student_ids))
        .group_by(Message.student_id)
    )
    last = {m.student_id: m for m in db.scalars(select(Message).where(Message.id.in_(last_ids))).all()}
    unread = _unread_by_student(db, user, teacher_id, student_ids)

    threads = []
    for teacher, student in pairs:
        partner = student.user if user.role == UserRole.TEACHER else teacher.user
        threads.append({
            "student_id": student.id,
            "teacher_id": teacher.id,
            "partner": {"user_id": partner.id, "full_name": partner.full_name, "is_active": partner.is_active},
            "last_message": last.get(student.id),
            "unread_count": unread.get(student.id, 0),
        })
    # conversations with the newest messages first, then the rest alphabetically
    threads.sort(key=lambda t: (
        -(t["last_message"].id if t["last_message"] else 0), t["partner"]["full_name"].lower(),
    ))
    return threads


def unread_total(db: Session, user: User) -> int:
    if user.role == UserRole.TEACHER and user.teacher_profile is not None:
        return sum(_unread_by_student(db, user, user.teacher_profile.id, None).values())
    if user.role == UserRole.STUDENT and user.student_profile is not None:
        s = user.student_profile
        if s.teacher_id is None:
            return 0
        return _unread_by_student(db, user, s.teacher_id, [s.id]).get(s.id, 0)
    return 0

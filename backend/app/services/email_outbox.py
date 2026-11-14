"""E-mail copies of notifications and chat messages (transactional outbox).

Requests never send these e-mails. Notifications and messages are just rows;
a background loop (see app/main.py) periodically picks rows that are
  - older than EMAIL_NOTIFY_DELAY_MINUTES, and
  - not yet handled (`email_processed_at IS NULL`),
and sends ONE e-mail per recipient with everything that is STILL UNREAD —
whoever has the app open and reads in time gets no e-mail at all.

Several workers may run the loop: a PostgreSQL advisory lock lets only one of
them work at a time. Rows are marked handled and committed BEFORE the e-mails
go out, so a crash can lose an e-mail but never sends one twice.
"""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Message, Notification, StudentProfile, TeacherProfile, User
from app.models.enums import UserRole
from app.services import email_service
from app.services.notification_service import SECTION_OF, SECTIONS

OUTBOX_LOCK = 724_002
BATCH = 500

# user-facing categories (keys of users.email_prefs); all on by default.
# Notification categories are the app sections; SYSTEM notifications stay in-app.
CATEGORY_OF = SECTION_OF
CATEGORIES = ("messages", *SECTIONS)


def effective_prefs(user: User) -> dict[str, bool]:
    stored = user.email_prefs or {}
    return {c: bool(stored.get(c, True)) for c in CATEGORIES}


def wants(user: User, category: str | None) -> bool:
    return category is not None and user.is_active and effective_prefs(user)[category]


def _url(path: str) -> str:
    return settings.FRONTEND_URL.rstrip("/") + path


def _base(user: User) -> str:
    return "/student" if user.role == UserRole.STUDENT else "/teacher"


@dataclass
class _Digest:
    user: User
    items: list[Notification] = field(default_factory=list)


@dataclass
class _ChatDigest:
    user: User
    # student_id -> (sender name, unread count, last preview)
    threads: dict[int, list] = field(default_factory=dict)


def _collect_notifications(db: Session, cutoff: datetime, now: datetime) -> list[_Digest]:
    rows = db.scalars(
        select(Notification)
        .where(Notification.email_processed_at.is_(None), Notification.created_at <= cutoff)
        .order_by(Notification.id)
        .limit(BATCH)
        .with_for_update(skip_locked=True)
    ).all()
    digests: dict[int, _Digest] = {}
    for n in rows:
        n.email_processed_at = now
        if n.is_read:
            continue  # seen in the app in time
        user = db.get(User, n.user_id)
        if user is None or not wants(user, CATEGORY_OF.get(n.type)):
            continue
        digests.setdefault(user.id, _Digest(user)).items.append(n)
    return list(digests.values())


def _collect_messages(db: Session, cutoff: datetime, now: datetime) -> list[_ChatDigest]:
    from app.services.message_service import preview

    rows = db.scalars(
        select(Message)
        .where(Message.email_processed_at.is_(None), Message.created_at <= cutoff)
        .order_by(Message.id)
        .limit(BATCH)
        .with_for_update(skip_locked=True)
    ).all()
    digests: dict[int, _ChatDigest] = {}
    for m in rows:
        m.email_processed_at = now
        if m.read_at is not None:
            continue
        teacher = db.get(TeacherProfile, m.teacher_id)
        student = db.get(StudentProfile, m.student_id)
        if teacher is None or student is None or student.teacher_id != teacher.id:
            continue  # the pair no longer exists (student moved to another teacher)
        sender_is_teacher = m.sender_user_id == teacher.user_id
        recipient = student.user if sender_is_teacher else teacher.user
        sender = teacher.user if sender_is_teacher else student.user
        if not wants(recipient, "messages"):
            continue
        d = digests.setdefault(recipient.id, _ChatDigest(recipient))
        entry = d.threads.setdefault(m.student_id, [sender.full_name, 0, ""])
        entry[1] += 1
        entry[2] = preview(m, recipient.locale)  # rows are in id order: keeps the newest
    return list(digests.values())


def process_email_outbox(db: Session, now: datetime | None = None) -> int:
    """One pass of the outbox. Returns the number of e-mails sent."""
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return 0
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": OUTBOX_LOCK}):
        return 0  # another worker is on it
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.EMAIL_NOTIFY_DELAY_MINUTES)

    notes = _collect_notifications(db, cutoff, now)
    chats = _collect_messages(db, cutoff, now)
    # Build everything while the rows are loaded, commit, then send (at most once).
    outgoing = []
    for d in notes:
        u = d.user
        link = d.items[0].link if len(d.items) == 1 and d.items[0].link else f"{_base(u)}/notifications"
        outgoing.append((
            email_service.notifications_digest,
            (u.email, u.full_name, [(n.title, n.body) for n in d.items], _url(link), _url(f"{_base(u)}/settings"),
             u.locale),
        ))
    for d in chats:
        u = d.user
        if u.role == UserRole.TEACHER and len(d.threads) == 1:
            link = f"/teacher/messages/{next(iter(d.threads))}"
        else:
            link = f"{_base(u)}/messages"
        threads = [(who, n, p) for who, n, p in d.threads.values()]
        outgoing.append((
            email_service.unread_messages,
            (u.email, u.full_name, threads, _url(link), _url(f"{_base(u)}/settings"), u.locale),
        ))
    db.commit()

    for fn, args in outgoing:
        fn(*args)
    return len(outgoing)

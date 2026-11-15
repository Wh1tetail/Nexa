"""Subscription business rules: derived status, lesson accounting, expiry alerts."""
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.core.i18n import M
from app.core.config import settings
from app.core.exceptions import BadRequest
from app.models import StudentProfile, Subscription
from app.models.enums import NotificationType, SubscriptionStatus
from app.schemas.subscription import SubscriptionOut
from app.services.notification_service import notify

log = logging.getLogger(__name__)

# Arbitrary constant identifying the expiry check in pg_try_advisory_xact_lock
EXPIRY_CHECK_LOCK = 724_001


def today() -> date:
    return datetime.now(UTC).date()


def days_left(sub: Subscription, ref: date | None = None) -> int:
    ref = ref or today()
    return max((sub.end_date - ref).days, 0)


def compute_status(sub: Subscription, ref: date | None = None) -> SubscriptionStatus:
    ref = ref or today()
    if sub.is_frozen:
        return SubscriptionStatus.FROZEN
    if sub.end_date < ref:
        return SubscriptionStatus.EXPIRED
    if (sub.end_date - ref).days <= settings.SUBSCRIPTION_EXPIRING_DAYS:
        return SubscriptionStatus.EXPIRING_SOON
    return SubscriptionStatus.ACTIVE


def to_out(sub: Subscription) -> SubscriptionOut:
    ref = today()
    total_days = max((sub.end_date - sub.start_date).days, 1)
    elapsed = min(max((ref - sub.start_date).days, 0), total_days)
    return SubscriptionOut(
        id=sub.id,
        student_id=sub.student_id,
        student_name=sub.student.user.full_name,
        title=sub.title,
        start_date=sub.start_date,
        end_date=sub.end_date,
        total_lessons=sub.total_lessons,
        used_lessons=sub.used_lessons,
        lessons_left=max(sub.total_lessons - sub.used_lessons, 0),
        days_left=days_left(sub, ref),
        total_days=total_days,
        progress_percent=round(elapsed * 100 / total_days),
        status=compute_status(sub, ref),
        is_frozen=sub.is_frozen,
        frozen_at=sub.frozen_at,
        notes=sub.notes,
        created_at=sub.created_at,
    )


ACCESS_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRING_SOON)


def has_access(db: Session, student_id: int) -> bool:
    """Lessons, homework and tests are open only while the current subscription
    has started and is active (or ending soon). Expired, frozen, not started yet
    or no subscription at all -> closed. Checked live on every request, so a
    renewal (extend, unfreeze, new subscription) gives access back at once."""
    sub = current_subscription(db, student_id)
    return bool(sub and sub.start_date <= today() and compute_status(sub) in ACCESS_STATUSES)


def current_subscription(db: Session, student_id: int) -> Subscription | None:
    """The subscription that is relevant 'now' for a student:
    the latest one that has started (or, failing that, the next upcoming one)."""
    ref = today()
    subs = db.scalars(
        select(Subscription)
        .options(joinedload(Subscription.student).joinedload(StudentProfile.user))
        .where(Subscription.student_id == student_id)
        .order_by(Subscription.end_date.desc(), Subscription.id.desc())
    ).all()
    if not subs:
        return None
    started = [s for s in subs if s.start_date <= ref]
    return started[0] if started else subs[-1]


def charge_lesson(db: Session, student_id: int, on: date) -> Subscription | None:
    """Deduct one lesson from the subscription valid on `on` (if any lessons left)."""
    sub = db.scalars(
        select(Subscription)
        .where(
            Subscription.student_id == student_id,
            Subscription.start_date <= on,
            Subscription.end_date >= on,
            Subscription.is_frozen.is_(False),
            Subscription.used_lessons < Subscription.total_lessons,
        )
        .order_by(Subscription.end_date.asc())
        .with_for_update()
    ).first()
    if sub:
        sub.used_lessons += 1
    return sub


def refund_lesson(db: Session, subscription_id: int | None) -> None:
    if subscription_id is None:
        return
    sub = db.get(Subscription, subscription_id, with_for_update=True)
    if sub and sub.used_lessons > 0:
        sub.used_lessons -= 1


def use_lessons(sub: Subscription, count: int) -> None:
    new_used = sub.used_lessons + count
    if new_used < 0:
        raise BadRequest("Количество использованных занятий не может быть отрицательным")
    if new_used > sub.total_lessons:
        raise BadRequest("Все оплаченные занятия уже использованы")
    sub.used_lessons = new_used


def check_expirations(db: Session) -> int:
    """Notify teachers (and students) about subscriptions that are expiring soon
    or have expired. Idempotent thanks to *_notified_at columns.

    Every uvicorn worker runs this periodically; a transaction-level advisory
    lock makes concurrent runs skip instead of sending duplicate notifications."""
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": EXPIRY_CHECK_LOCK}):
        log.info("Subscription check already running in another worker, skipping")
        db.rollback()
        return 0
    ref = today()
    soon = ref + timedelta(days=settings.SUBSCRIPTION_EXPIRING_DAYS)
    now = datetime.now(UTC)
    sent = 0
    subs = db.scalars(
        select(Subscription)
        .options(
            joinedload(Subscription.student).joinedload(StudentProfile.user),
            joinedload(Subscription.teacher),
        )
        .where(Subscription.is_frozen.is_(False), Subscription.end_date <= soon)
        .where(
            (Subscription.expired_notified_at.is_(None))
            | (Subscription.expiring_notified_at.is_(None))
        )
    ).unique().all()
    for sub in subs:
        # skip subscriptions that were superseded by a newer one
        newer = db.scalar(
            select(Subscription.id).where(
                Subscription.student_id == sub.student_id,
                Subscription.end_date > sub.end_date,
            ).limit(1)
        )
        if newer:
            sub.expiring_notified_at = sub.expiring_notified_at or now
            sub.expired_notified_at = sub.expired_notified_at or now
            continue
        name = sub.student.user.full_name
        link = f"/teacher/students/{sub.student_id}"
        if sub.end_date < ref and sub.expired_notified_at is None:
            notify(db, [sub.teacher.user_id], NotificationType.SUBSCRIPTION_EXPIRED,
                   M("Абонемент закончился"), M("У ученика {name} закончился абонемент.", name=name), link)
            notify(db, [sub.student.user_id], NotificationType.SUBSCRIPTION_EXPIRED,
                   M("Ваш абонемент закончился"), M("Обратитесь к преподавателю для продления."), "/student")
            sub.expired_notified_at = now
            sub.expiring_notified_at = sub.expiring_notified_at or now
            sent += 1
        elif sub.end_date >= ref and sub.expiring_notified_at is None:
            left = (sub.end_date - ref).days
            notify(db, [sub.teacher.user_id], NotificationType.SUBSCRIPTION_EXPIRING,
                   M("Абонемент скоро закончится"),
                   M("У ученика {name} абонемент заканчивается через {n} дн.", name=name, n=left), link)
            notify(db, [sub.student.user_id], NotificationType.SUBSCRIPTION_EXPIRING,
                   M("Абонемент скоро закончится"), M("Осталось дней: {n}.", n=left), "/student")
            sub.expiring_notified_at = now
            sent += 1
    db.commit()
    if sent:
        log.info("Subscription expiry notifications sent: %s", sent)
    return sent


def reset_notification_flags(sub: Subscription) -> None:
    """After extending / editing dates, allow alerts to fire again."""
    sub.expiring_notified_at = None
    sub.expired_notified_at = None

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.core.i18n import Msg, render
from app.models.enums import NotificationType

# Which part of the app a notification belongs to. Used for the counters in the
# side menu and as the e-mail categories (users.email_prefs). SYSTEM has none.
SECTION_OF: dict[NotificationType, str] = {
    NotificationType.HOMEWORK_ASSIGNED: "homework",
    NotificationType.HOMEWORK_SUBMITTED: "homework",
    NotificationType.HOMEWORK_REVIEWED: "homework",
    NotificationType.TEST_ASSIGNED: "tests",
    NotificationType.TEST_COMPLETED: "tests",
    NotificationType.TEST_GRADED: "tests",
    NotificationType.LESSON_CHANGED: "lessons",
    NotificationType.COURSE_ASSIGNED: "courses",
    NotificationType.SUBSCRIPTION_EXPIRING: "subscription",
    NotificationType.SUBSCRIPTION_EXPIRED: "subscription",
}
SECTIONS = ("homework", "tests", "lessons", "courses", "subscription")


def types_of(section: str) -> list[NotificationType]:
    return [t for t, s in SECTION_OF.items() if s == section]


def notify(
    db: Session,
    user_ids: Iterable[int],
    type_: NotificationType,
    title: str | Msg,
    body: str | Msg | None = None,
    link: str | None = None,
) -> None:
    """Queue notifications in the current transaction (caller commits).
    Msg texts are rendered in each recipient's language (users.locale);
    plain strings are user content (titles, names) and are stored as is."""
    ids = set(user_ids)
    if not ids:
        return
    langs = dict(db.execute(select(User.id, User.locale).where(User.id.in_(ids))).all())
    for uid in ids:
        lang = langs.get(uid)
        db.add(Notification(user_id=uid, type=type_, title=render(title, lang), body=render(body, lang), link=link))

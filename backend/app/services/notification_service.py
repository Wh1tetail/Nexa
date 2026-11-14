from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models import Notification
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
    NotificationType.SUBSCRIPTION_EXPIRING: "subscription",
    NotificationType.SUBSCRIPTION_EXPIRED: "subscription",
}
SECTIONS = ("homework", "tests", "lessons", "subscription")


def types_of(section: str) -> list[NotificationType]:
    return [t for t, s in SECTION_OF.items() if s == section]


def notify(
    db: Session,
    user_ids: Iterable[int],
    type_: NotificationType,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> None:
    """Queue notifications in the current transaction (caller commits)."""
    for uid in set(user_ids):
        db.add(Notification(user_id=uid, type=type_, title=title, body=body, link=link))

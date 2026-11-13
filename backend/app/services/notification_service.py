from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models import Notification
from app.models.enums import NotificationType


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

from datetime import datetime

from app.models.enums import NotificationType
from app.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: int
    type: NotificationType
    title: str
    body: str | None
    link: str | None
    is_read: bool
    created_at: datetime

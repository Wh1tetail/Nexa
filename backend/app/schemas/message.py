from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.message import MAX_MESSAGE_LENGTH
from app.schemas.common import ORMModel
from app.schemas.homework import AttachmentOut


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Сообщение не может быть пустым")
        return v


class MessageOut(ORMModel):
    id: int
    teacher_id: int
    student_id: int
    sender_user_id: int
    body: str
    created_at: datetime
    read_at: datetime | None
    attachments: list[AttachmentOut] = []


class ChatPartner(BaseModel):
    user_id: int
    full_name: str
    is_active: bool


class ThreadOut(BaseModel):
    """A conversation; `student_id` is the thread key for both sides."""
    student_id: int
    teacher_id: int
    partner: ChatPartner
    last_message: MessageOut | None
    unread_count: int


class ReadResult(BaseModel):
    count: int


class UnreadCount(BaseModel):
    count: int

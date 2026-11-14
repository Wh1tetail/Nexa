from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

MAX_MESSAGE_LENGTH = 4000


class Message(Base, TimestampMixin):
    """One chat message in the conversation between a teacher and one of their students.
    A conversation is identified by the (teacher_id, student_id) pair."""
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_thread_id", "teacher_id", "student_id", "id"),
        # fast unread counters: only unread rows are indexed
        Index("ix_messages_unread", "teacher_id", "student_id", "sender_user_id",
              postgresql_where="read_at IS NULL"),
        CheckConstraint(f"char_length(body) BETWEEN 1 AND {MAX_MESSAGE_LENGTH}", name="body_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"))
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthAttempt(Base):
    """Failed sign-in / password-reset attempts, shared by all workers
    (see app/middleware/rate_limit.py)."""
    __tablename__ = "auth_attempts"
    __table_args__ = (Index("ix_auth_attempts_key_at", "key", "attempted_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(300))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

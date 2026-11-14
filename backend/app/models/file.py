from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Attachment(Base, TimestampMixin):
    """A stored file attached to exactly one owner: a homework (teacher material),
    a homework submission (student work) or a chat message."""

    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "(homework_id IS NOT NULL)::int + (submission_id IS NOT NULL)::int"
            " + (message_id IS NOT NULL)::int = 1",
            name="single_owner",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    uploaded_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    homework_id: Mapped[int | None] = mapped_column(
        ForeignKey("homework.id", ondelete="CASCADE"), index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("homework_submissions.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)

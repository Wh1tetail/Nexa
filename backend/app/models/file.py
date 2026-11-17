from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Attachment(Base, TimestampMixin):
    """A stored file attached to exactly one owner: a homework (teacher material),
    a homework submission (student work), a chat message, a test (materials) or
    a course lesson (materials)."""

    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "(homework_id IS NOT NULL)::int + (submission_id IS NOT NULL)::int"
            " + (message_id IS NOT NULL)::int + (test_id IS NOT NULL)::int"
            " + (course_lesson_id IS NOT NULL)::int = 1",
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
    test_id: Mapped[int | None] = mapped_column(
        ForeignKey("tests.id", ondelete="CASCADE"), index=True
    )
    course_lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_lessons.id", ondelete="CASCADE"), index=True
    )
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)

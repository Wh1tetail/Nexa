"""Book-to-Test: PDF books methodists generate test questions from.
The PDF itself is an ordinary `Attachment` (book_id), so storage, downloads and
the orphan sweep work as for every other file."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import BookStatus, EnglishLevel, str_enum

if TYPE_CHECKING:
    from app.models.file import Attachment
    from app.models.user import User


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(200))  # the book's author
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    level: Mapped[EnglishLevel | None] = mapped_column(str_enum(EnglishLevel, "english_level"))
    page_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[BookStatus] = mapped_column(
        str_enum(BookStatus, "book_status"), default=BookStatus.UPLOADED, server_default=BookStatus.UPLOADED.value
    )
    error_code: Mapped[str | None] = mapped_column(String(60))  # why processing failed
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploaded_by: Mapped["User | None"] = relationship()
    files: Mapped[list["Attachment"]] = relationship(
        primaryjoin="Book.id == Attachment.book_id",
        order_by="Attachment.id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def file(self) -> "Attachment | None":
        """The book's PDF (one per book)."""
        return self.files[0] if self.files else None

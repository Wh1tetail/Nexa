from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import SubmissionStatus, str_enum
from app.models.file import Attachment
from app.models.user import Group, StudentProfile, TeacherProfile


class Homework(Base, TimestampMixin):
    __tablename__ = "homework"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    max_grade: Mapped[int] = mapped_column(Integer, default=10, server_default="10")

    teacher: Mapped[TeacherProfile] = relationship()
    group: Mapped[Group | None] = relationship()
    attachments: Mapped[list[Attachment]] = relationship(
        primaryjoin="Homework.id == Attachment.homework_id",
        cascade="all, delete-orphan",
        order_by="Attachment.id",
    )
    submissions: Mapped[list["HomeworkSubmission"]] = relationship(
        back_populates="homework", cascade="all, delete-orphan"
    )


class HomeworkSubmission(Base, TimestampMixin):
    """Per-student assignment of a homework. Created when homework is assigned
    (status NEW) and progresses through the student / teacher workflow."""

    __tablename__ = "homework_submissions"
    __table_args__ = (
        UniqueConstraint("homework_id", "student_id", name="uq_submission_homework_student"),
        CheckConstraint("grade IS NULL OR grade >= 0", name="grade_non_negative"),
        Index("ix_submissions_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    homework_id: Mapped[int] = mapped_column(
        ForeignKey("homework.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE")
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        str_enum(SubmissionStatus, "submission_status"),
        default=SubmissionStatus.NEW,
        index=True,
    )
    student_comment: Mapped[str | None] = mapped_column(Text)
    teacher_comment: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    homework: Mapped[Homework] = relationship(back_populates="submissions")
    student: Mapped[StudentProfile] = relationship()
    files: Mapped[list[Attachment]] = relationship(
        primaryjoin="HomeworkSubmission.id == Attachment.submission_id",
        cascade="all, delete-orphan",
        order_by="Attachment.id",
    )

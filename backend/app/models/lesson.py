from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import AttendanceStatus, LessonStatus, str_enum
from app.models.user import Group, StudentProfile, TeacherProfile


class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"
    __table_args__ = (CheckConstraint("duration_minutes > 0", name="duration_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    meeting_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[LessonStatus] = mapped_column(
        str_enum(LessonStatus, "lesson_status"), default=LessonStatus.SCHEDULED
    )
    # Lessons created together as a weekly series share this id.
    series_id: Mapped[str | None] = mapped_column(String(32), index=True)

    teacher: Mapped[TeacherProfile] = relationship()
    group: Mapped[Group | None] = relationship()
    attendance: Mapped[list["Attendance"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )


class Attendance(Base, TimestampMixin):
    """One row per (lesson, participant). status is NULL until the teacher marks it."""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("lesson_id", "student_id", name="uq_attendance_lesson_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[AttendanceStatus | None] = mapped_column(
        str_enum(AttendanceStatus, "attendance_status")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Subscription a lesson was deducted from (present/late), to allow reverting.
    charged_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL")
    )

    lesson: Mapped[Lesson] = relationship(back_populates="attendance")
    student: Mapped[StudentProfile] = relationship()

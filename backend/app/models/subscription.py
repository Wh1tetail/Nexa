from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.user import StudentProfile, TeacherProfile


class Subscription(Base, TimestampMixin):
    """A paid package of lessons valid between start_date and end_date.

    Status (active / expiring soon / expired / frozen) is derived from dates and
    is_frozen in services.subscription_service, never stored, so it's always fresh.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="dates_order"),
        CheckConstraint("total_lessons > 0", name="total_positive"),
        CheckConstraint(
            "used_lessons >= 0 AND used_lessons <= total_lessons", name="used_range"
        ),
        Index("ix_subscriptions_student_end", "student_id", "end_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    total_lessons: Mapped[int] = mapped_column(Integer)
    used_lessons: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_frozen: Mapped[bool] = mapped_column(default=False, server_default="false")
    frozen_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    # Prevent duplicate notifications
    expiring_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[StudentProfile] = relationship()
    teacher: Mapped[TeacherProfile] = relationship()

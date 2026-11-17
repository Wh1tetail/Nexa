"""Gamification: XP history, earned achievements, learning days and settings."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.models.enums import AchievementCode, XPReason, str_enum


class XPTransaction(Base, TimestampMixin):
    """One award of XP. The unique key makes every award happen once, even when
    requests repeat or race (inserts use ON CONFLICT DO NOTHING)."""
    __tablename__ = "xp_transactions"
    __table_args__ = (UniqueConstraint("student_id", "reason", "ref_key", name="uq_xp_transactions_once"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    reason: Mapped[XPReason] = mapped_column(str_enum(XPReason, "xp_reason"))
    ref_key: Mapped[str] = mapped_column(String(64))  # e.g. "lesson:12", "test:5"
    points: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))  # what it was for, kept as it was


class StudentAchievement(Base):
    __tablename__ = "student_achievements"
    __table_args__ = (UniqueConstraint("student_id", "code", name="uq_student_achievements_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    code: Mapped[AchievementCode] = mapped_column(str_enum(AchievementCode, "achievement_code"))
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class StudentActivityDay(Base):
    """A day (in the student's time zone) with learning activity, for streaks."""
    __tablename__ = "student_activity_days"

    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)


class AppSetting(Base):
    """School-wide settings edited by administrators (key -> JSON value)."""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

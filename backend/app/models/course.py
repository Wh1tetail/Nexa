"""Courses / programmes built by methodists: Course -> Level -> Module -> Lesson -> blocks.

The content is shared: teachers and (later) students read the same rows; no
per-student copies are ever made.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import EnglishLevel, LessonBlockType, str_enum

if TYPE_CHECKING:
    from app.models.file import Attachment
    from app.models.user import User


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    # teachers see a course only once it is published (and only its published lessons)
    published: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped["User | None"] = relationship()
    levels: Mapped[list["CourseLevel"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="CourseLevel.position"
    )


class CourseLevel(Base, TimestampMixin):
    __tablename__ = "course_levels"
    __table_args__ = (UniqueConstraint("course_id", "level", name="uq_course_levels_course_level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    level: Mapped[EnglishLevel] = mapped_column(str_enum(EnglishLevel, "english_level"))
    title: Mapped[str] = mapped_column(String(200))  # e.g. "A1 Beginner"
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    course: Mapped[Course] = relationship(back_populates="levels")
    modules: Mapped[list["CourseModule"]] = relationship(
        back_populates="level", cascade="all, delete-orphan", order_by="CourseModule.position"
    )


class CourseModule(Base, TimestampMixin):
    __tablename__ = "course_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("course_levels.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    level: Mapped[CourseLevel] = relationship(back_populates="modules")
    lessons: Mapped[list["CourseLesson"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="CourseLesson.position"
    )


class CourseLesson(Base, TimestampMixin):
    __tablename__ = "course_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("course_modules.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    module: Mapped[CourseModule] = relationship(back_populates="lessons")
    blocks: Mapped[list["LessonBlock"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="LessonBlock.position"
    )
    files: Mapped[list["Attachment"]] = relationship(
        cascade="all, delete-orphan", order_by="Attachment.id", foreign_keys="Attachment.course_lesson_id"
    )


class LessonBlock(Base, TimestampMixin):
    """One block of a lesson. Settings and exercises live in `content` (see
    services/lesson_blocks.py); exercise questions use the test question format."""
    __tablename__ = "lesson_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("course_lessons.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    type: Mapped[LessonBlockType] = mapped_column(str_enum(LessonBlockType, "lesson_block_type"))
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

    lesson: Mapped[CourseLesson] = relationship(back_populates="blocks")

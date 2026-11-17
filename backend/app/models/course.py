"""Courses / programmes built by methodists: Course -> Level -> Module -> Lesson -> blocks.

The content is shared: teachers and (later) students read the same rows; no
per-student copies are ever made.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import EnglishLevel, LessonBlockType, str_enum

if TYPE_CHECKING:
    from app.models.file import Attachment
    from app.models.user import Group, StudentProfile, TeacherProfile, User


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


class CourseAssignment(Base, TimestampMixin):
    """A teacher gives a level or a module of a course to students (directly or
    through a group: members who join the group later get it too). Content is
    shared; progress lives in LessonProgress. Cancelling sets removed_at."""
    __tablename__ = "course_assignments"
    __table_args__ = (CheckConstraint("(level_id IS NULL) <> (module_id IS NULL)", name="one_scope"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    level_id: Mapped[int | None] = mapped_column(ForeignKey("course_levels.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("course_modules.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    teacher: Mapped["TeacherProfile"] = relationship()
    course: Mapped[Course] = relationship()
    level: Mapped[CourseLevel | None] = relationship()
    module: Mapped[CourseModule | None] = relationship()
    group: Mapped["Group | None"] = relationship()
    members: Mapped[list["CourseAssignmentStudent"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class CourseAssignmentStudent(Base):
    """A student in an assignment; taking a student off sets removed_at (progress stays)."""
    __tablename__ = "course_assignment_students"

    assignment_id: Mapped[int] = mapped_column(ForeignKey("course_assignments.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), primary_key=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignment: Mapped[CourseAssignment] = relationship(back_populates="members")
    student: Mapped["StudentProfile"] = relationship()


class LessonProgress(Base):
    """A student's work on a course lesson. Survives the lesson's deletion
    (lesson_id becomes NULL, the title is kept) so history is never lost.

    blocks: {"<block_id>": {"answers": {...}, "results": [...], "score", "max",
             "best", "attempts", "checked_at"}}
    plays:  {"<block_id>": listens counted}
    """
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id", ondelete="SET NULL"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), index=True)
    lesson_title: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # mean of the best results of the lesson's exercises, % (None: no exercises)
    score_percent: Mapped[float | None] = mapped_column(Float)
    blocks: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    plays: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

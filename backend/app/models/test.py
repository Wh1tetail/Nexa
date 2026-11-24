from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import AttemptStatus, EnglishLevel, QuestionType, str_enum
from app.models.user import StudentProfile, TeacherProfile, User

if TYPE_CHECKING:
    from app.models.file import Attachment

test_assignments = Table(
    "test_assignments",
    Base.metadata,
    Column("test_id", ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "student_id",
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    # attempts the teacher allowed this student on top of Test.max_attempts
    Column("extra_attempts", Integer, nullable=False, server_default="0"),
    # excluded from the test: hidden from the student, attempts and results kept
    Column("removed_at", DateTime(timezone=True)),
)


class Test(Base, TimestampMixin):
    __test__ = False  # not a pytest test class
    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes > 0", name="time_limit_positive"
        ),
        CheckConstraint(
            "passing_percent IS NULL OR passing_percent BETWEEN 1 AND 100", name="passing_percent_range"
        ),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="max_attempts_range"),
        # a teacher's own test, or a library test (shared, no owning teacher)
        CheckConstraint(
            "(is_library AND teacher_id IS NULL) OR (NOT is_library AND teacher_id IS NOT NULL)",
            name="owner_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True
    )
    # --- shared library (methodists / admins); teachers use it by copying ---
    is_library: Mapped[bool] = mapped_column(default=False, server_default="false", index=True)
    published: Mapped[bool] = mapped_column(default=False, server_default="false")  # visible to teachers
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    level: Mapped[EnglishLevel | None] = mapped_column(str_enum(EnglishLevel, "english_level"))
    # a copy remembers where it came from (library test or another test)
    source_test_id: Mapped[int | None] = mapped_column(ForeignKey("tests.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # --- settings ---
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # can't start before
    shuffle_questions: Mapped[bool] = mapped_column(default=False, server_default="false")
    shuffle_options: Mapped[bool] = mapped_column(default=False, server_default="false")
    # after grading the student sees correct answers and explanations (score is always shown)
    show_correct_answers: Mapped[bool] = mapped_column(default=True, server_default="true")
    passing_percent: Mapped[int | None] = mapped_column(Integer)  # None = no pass/fail
    # how many times a student may take it (the best result counts)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    teacher: Mapped[TeacherProfile | None] = relationship()
    author: Mapped["User | None"] = relationship(foreign_keys=[author_id])
    sections: Mapped[list["TestSection"]] = relationship(secondary="test_section_links", order_by="TestSection.name")
    tags: Mapped[list["TestTag"]] = relationship(secondary="test_tag_links", order_by="TestTag.name")
    questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="TestQuestion.position"
    )
    # active assignees only; assignment rows are written by test_service (they may be restored)
    students: Mapped[list[StudentProfile]] = relationship(
        secondary=test_assignments,
        secondaryjoin="and_(StudentProfile.id == test_assignments.c.student_id, test_assignments.c.removed_at.is_(None))",
        viewonly=True,
    )
    attempts: Mapped[list["TestAttempt"]] = relationship(
        back_populates="test", cascade="all, delete-orphan"
    )
    # materials (reading texts, audio for listening, pictures); questions refer to them by id
    files: Mapped[list["Attachment"]] = relationship(
        primaryjoin="Test.id == Attachment.test_id",
        order_by="Attachment.id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TestQuestion(Base):
    __test__ = False
    """options: [{"id": "a", "text": "..."}] for choice questions.
    correct_answer: list of option ids (choice / true_false) or
    list of accepted strings (short_answer; used as a hint for manual review
    and for automatic exact-match checking)."""

    __tablename__ = "test_questions"
    # content blocks (audio, reading) are worth 0 points
    __table_args__ = (CheckConstraint("points >= 0", name="points_not_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[QuestionType] = mapped_column(str_enum(QuestionType, "question_type"))
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    correct_answer: Mapped[list[str]] = mapped_column(JSONB, default=list)
    points: Mapped[int] = mapped_column(Integer, default=1)
    explanation: Mapped[str | None] = mapped_column(Text)  # shown with the results
    # ids of the test's files shown with this question (picture, audio)
    attachment_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default="[]")
    # type settings: gaps, matching pairs, audio file and play limit, reading text
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    # where the question came from (schemas.test.QuestionSource: book, pages, quote,
    # difficulty); editors only - question_out leaves it out unless with_source=True
    source: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    test: Mapped[Test] = relationship(back_populates="questions")


class TestAttempt(Base):
    __test__ = False
    __tablename__ = "test_attempts"
    __table_args__ = (
        UniqueConstraint("test_id", "student_id", "number", name="uq_attempt_test_student_number"),
        # at most one unfinished attempt per student and test
        Index(
            "uq_attempt_one_in_progress", "test_id", "student_id",
            unique=True, postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # 1, 2, ... per student
    status: Mapped[AttemptStatus] = mapped_column(
        str_enum(AttemptStatus, "attempt_status"), default=AttemptStatus.IN_PROGRESS
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    # audio blocks: {question_id: times started} (for the listening limit)
    plays: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict, server_default="{}")

    test: Mapped[Test] = relationship(back_populates="attempts")
    student: Mapped[StudentProfile] = relationship()
    answers: Mapped[list["TestAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class TestAnswer(Base):
    __test__ = False
    __tablename__ = "test_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("test_questions.id", ondelete="CASCADE"), index=True
    )
    answer: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_correct: Mapped[bool | None] = mapped_column()
    points_awarded: Mapped[float | None] = mapped_column(Float)
    teacher_comment: Mapped[str | None] = mapped_column(Text)

    attempt: Mapped[TestAttempt] = relationship(back_populates="answers")
    question: Mapped[TestQuestion] = relationship()


class TestSection(Base, TimestampMixin):
    """Library section; sections nest (Grammar -> Present Simple). A test may sit
    in several sections."""
    __test__ = False
    __tablename__ = "test_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("test_sections.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


test_section_links = Table(
    "test_section_links",
    Base.metadata,
    Column("test_id", ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    Column("section_id", ForeignKey("test_sections.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class TestTag(Base):
    __test__ = False
    __tablename__ = "test_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)  # stored lower-case


test_tag_links = Table(
    "test_tag_links",
    Base.metadata,
    Column("test_id", ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("test_tags.id", ondelete="CASCADE"), primary_key=True, index=True),
)

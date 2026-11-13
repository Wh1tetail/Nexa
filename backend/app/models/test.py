from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import AttemptStatus, QuestionType, str_enum
from app.models.user import StudentProfile, TeacherProfile

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
)


class Test(Base, TimestampMixin):
    __test__ = False  # not a pytest test class
    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes > 0", name="time_limit_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    teacher: Mapped[TeacherProfile] = relationship()
    questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="TestQuestion.position"
    )
    students: Mapped[list[StudentProfile]] = relationship(secondary=test_assignments)
    attempts: Mapped[list["TestAttempt"]] = relationship(
        back_populates="test", cascade="all, delete-orphan"
    )


class TestQuestion(Base):
    __test__ = False
    """options: [{"id": "a", "text": "..."}] for choice questions.
    correct_answer: list of option ids (choice / true_false) or
    list of accepted strings (short_answer; used as a hint for manual review
    and for automatic exact-match checking)."""

    __tablename__ = "test_questions"
    __table_args__ = (CheckConstraint("points > 0", name="points_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[QuestionType] = mapped_column(str_enum(QuestionType, "question_type"))
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    correct_answer: Mapped[list[str]] = mapped_column(JSONB, default=list)
    points: Mapped[int] = mapped_column(Integer, default=1)

    test: Mapped[Test] = relationship(back_populates="questions")


class TestAttempt(Base):
    __test__ = False
    __tablename__ = "test_attempts"
    __table_args__ = (UniqueConstraint("test_id", "student_id", name="uq_attempt_test_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[AttemptStatus] = mapped_column(
        str_enum(AttemptStatus, "attempt_status"), default=AttemptStatus.IN_PROGRESS
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float, default=0)

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

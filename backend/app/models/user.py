from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import EnglishLevel, UserRole, str_enum


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole, "user_role"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Incremented on logout / password change -> invalidates all issued tokens.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locale: Mapped[str] = mapped_column(String(5), default="ru", server_default="ru")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    teacher_profile: Mapped["TeacherProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class TeacherProfile(Base, TimestampMixin):
    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    bio: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="teacher_profile")
    students: Mapped[list["StudentProfile"]] = relationship(back_populates="teacher")
    groups: Mapped[list["Group"]] = relationship(back_populates="teacher")


group_students = Table(
    "group_students",
    Base.metadata,
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "student_id",
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="SET NULL"), index=True
    )
    english_level: Mapped[EnglishLevel] = mapped_column(
        str_enum(EnglishLevel, "english_level"), default=EnglishLevel.A1
    )
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="student_profile")
    teacher: Mapped[TeacherProfile | None] = relationship(back_populates="students")
    groups: Mapped[list["Group"]] = relationship(
        secondary=group_students, back_populates="students"
    )


class Group(Base, TimestampMixin):
    __tablename__ = "groups"
    __table_args__ = (Index("uq_groups_teacher_name", "teacher_id", "name", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    level: Mapped[EnglishLevel | None] = mapped_column(
        str_enum(EnglishLevel, "group_level")
    )
    description: Mapped[str | None] = mapped_column(Text)

    teacher: Mapped[TeacherProfile] = relationship(back_populates="groups")
    students: Mapped[list[StudentProfile]] = relationship(
        secondary=group_students, back_populates="groups"
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.timezones import is_valid_timezone
from app.models.enums import EnglishLevel, SubscriptionStatus, UserRole
from app.schemas.auth import validate_password
from app.schemas.common import ORMModel


def _optional_password(v: str | None) -> str | None:
    return None if v in (None, "") else validate_password(v)


def _password_or_invite(m):
    if not m.password and not m.send_invite:
        raise ValueError("Укажите пароль или отправьте приглашение на email")
    return m


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    locale: str
    timezone: str | None = None  # IANA name; None = not chosen yet
    created_at: datetime


class MeOut(UserOut):
    # effective e-mail notification settings: {"messages": true, "homework": true, ...}
    email_prefs: dict[str, bool] = {}
    student_id: int | None = None
    teacher_id: int | None = None
    english_level: EnglishLevel | None = None
    teacher_name: str | None = None


class UpdateMeRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    locale: str | None = Field(default=None, pattern="^(ru|en|kk)$")
    timezone: str | None = Field(default=None, max_length=64)
    # partial update: only the categories sent are changed
    email_prefs: dict[str, bool] | None = None

    @field_validator("email_prefs")
    @classmethod
    def known_categories(cls, v: dict[str, bool] | None) -> dict[str, bool] | None:
        from app.services.email_outbox import CATEGORIES

        if v is not None and not set(v) <= set(CATEGORIES):
            raise ValueError("Неизвестный тип уведомлений")
        return v

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_timezone(v):
            raise ValueError("Неизвестный часовой пояс")
        return v


class GroupBrief(ORMModel):
    id: int
    name: str


class StudentBrief(BaseModel):
    """Compact row for lists / pickers."""
    id: int
    user_id: int
    full_name: str
    email: str
    phone: str | None
    english_level: EnglishLevel
    is_active: bool
    created_at: datetime
    groups: list[GroupBrief] = []
    subscription_status: SubscriptionStatus | None = None
    lessons_left: int | None = None
    days_left: int | None = None
    subscription_end: date | None = None


class StudentCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    english_level: EnglishLevel = EnglishLevel.A1
    password: str | None = Field(default=None, max_length=128)
    send_invite: bool = False  # e-mail a link to set the password
    notes: str | None = None
    group_ids: list[int] = []
    teacher_id: int | None = None  # admin only

    _v = field_validator("password")(_optional_password)
    _c = model_validator(mode="after")(_password_or_invite)


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    english_level: EnglishLevel | None = None
    notes: str | None = None
    is_active: bool | None = None
    group_ids: list[int] | None = None


class StudentCreated(BaseModel):
    student: StudentBrief


class TeacherCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    password: str | None = Field(default=None, max_length=128)
    send_invite: bool = False
    bio: str | None = None

    _v = field_validator("password")(_optional_password)
    _c = model_validator(mode="after")(_password_or_invite)


class TeacherOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    students_count: int


class StudentProfileOut(StudentBrief):
    notes: str | None = None
    teacher_name: str | None = None
    # Set-password link, returned only in DEBUG (no mail server in development)
    dev_invite_url: str | None = None


class InviteResponse(BaseModel):
    detail: str
    dev_invite_url: str | None = None

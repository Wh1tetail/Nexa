from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import EnglishLevel, UserRole
from app.schemas.auth import validate_password


class AdminUserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    # student
    student_id: int | None = None
    english_level: EnglishLevel | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    # teacher
    teacher_profile_id: int | None = None
    students_count: int | None = None


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class AdminPasswordRequest(BaseModel):
    """Either set a password directly or e-mail the user a reset link."""
    password: str | None = Field(default=None, max_length=128)
    send_link: bool = False

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str | None) -> str | None:
        return None if v in (None, "") else validate_password(v)

    @model_validator(mode="after")
    def _one(self):
        if bool(self.password) == self.send_link:
            raise ValueError("Укажите новый пароль или выберите отправку ссылки")
        return self


class AdminStats(BaseModel):
    teachers: int
    students: int
    active_students: int
    unassigned_students: int
    active_subscriptions: int
    lessons_this_month: int

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SubscriptionStatus


class SubscriptionCreate(BaseModel):
    student_id: int
    title: str | None = Field(default=None, max_length=200)
    start_date: date
    end_date: date
    total_lessons: int = Field(gt=0, le=1000)
    used_lessons: int = Field(default=0, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.end_date < self.start_date:
            raise ValueError("Дата окончания не может быть раньше даты начала")
        if self.used_lessons > self.total_lessons:
            raise ValueError("Использованных занятий больше, чем оплачено")
        return self


class SubscriptionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    total_lessons: int | None = Field(default=None, gt=0, le=1000)
    used_lessons: int | None = Field(default=None, ge=0)
    notes: str | None = None


class SubscriptionExtend(BaseModel):
    new_end_date: date | None = None
    add_days: int | None = Field(default=None, gt=0, le=3650)
    add_lessons: int = Field(default=0, ge=0, le=1000)

    @model_validator(mode="after")
    def _check(self):
        if self.new_end_date is None and self.add_days is None and self.add_lessons == 0:
            raise ValueError("Укажите новую дату окончания, дни или занятия")
        return self


class UseLessonRequest(BaseModel):
    count: int = Field(default=1, ge=-50, le=50, description="Negative to return lessons")


class SubscriptionOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    title: str | None
    start_date: date
    end_date: date
    total_lessons: int
    used_lessons: int
    lessons_left: int
    days_left: int
    total_days: int
    progress_percent: int  # elapsed share of the period, 0..100
    status: SubscriptionStatus
    is_frozen: bool
    frozen_at: date | None
    notes: str | None
    created_at: datetime

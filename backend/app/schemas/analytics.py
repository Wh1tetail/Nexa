from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import EnglishLevel, SubscriptionStatus

RiskReason = Literal["low_attendance", "low_tests", "overdue_homework", "subscription_expired", "inactive"]


class ScorePoint(BaseModel):
    """One graded test attempt or reviewed homework, as a percentage."""
    date: datetime
    title: str
    percent: int
    passed: bool | None = None  # tests with a passing score only


class AttendanceMonth(BaseModel):
    month: date  # first day of the month (viewer's time zone)
    present: int
    late: int
    absent: int
    excused: int
    rate: int | None  # (present + late) / marked; None when nothing was marked


class ProgressSummary(BaseModel):
    avg_test: int | None
    avg_homework: int | None
    attendance_rate: int | None
    tests_count: int
    homework_count: int
    on_time_rate: int | None  # share of submitted homework handed in before the due date
    test_trend: int | None  # avg of the last 3 tests minus the 3 before them (needs >= 4)


class StudentProgress(BaseModel):
    student_id: int
    full_name: str
    english_level: EnglishLevel
    summary: ProgressSummary
    tests: list[ScorePoint]  # oldest first
    homework: list[ScorePoint]  # oldest first
    attendance: list[AttendanceMonth]  # the last 6 months, oldest first


class StudentOverviewRow(BaseModel):
    student_id: int
    full_name: str
    english_level: EnglishLevel
    groups: list[str]
    avg_test: int | None
    avg_homework: int | None
    attendance_rate: int | None
    overdue_homework: int
    last_activity: datetime | None
    subscription_status: SubscriptionStatus | None
    risks: list[RiskReason]


class TeacherOverview(BaseModel):
    period_days: int
    students: int
    at_risk: int
    avg_test: int | None
    avg_homework: int | None
    attendance_rate: int | None
    rows: list[StudentOverviewRow]  # students needing attention first

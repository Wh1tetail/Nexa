from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EnglishLevel
from app.schemas.lesson import AttendanceStats, MyLesson
from app.schemas.notification import NotificationOut
from app.schemas.subscription import SubscriptionOut
from app.schemas.test import StudentTestItem


class StudentDashboard(BaseModel):
    full_name: str
    english_level: EnglishLevel
    teacher_name: str | None
    homework_done: int
    homework_upcoming: int
    homework_needs_revision: int
    subscription: SubscriptionOut | None
    recent_tests: list[StudentTestItem]
    pending_tests: int
    attendance: AttendanceStats
    next_lessons: list[MyLesson]
    notifications: list[NotificationOut]


class UpcomingLesson(BaseModel):
    id: int
    title: str
    starts_at: datetime
    duration_minutes: int
    participants: int
    group_name: str | None


class ActivityItem(BaseModel):
    kind: str  # homework_submitted | test_completed
    student_id: int
    student_name: str
    title: str
    at: datetime
    link: str


class TeacherDashboard(BaseModel):
    full_name: str
    students_total: int
    subscriptions_active: int
    subscriptions_expiring: int
    subscriptions_expired: int
    homework_to_review: int
    tests_to_review: int
    upcoming_lessons: list[UpcomingLesson]
    expiring_subscriptions: list[SubscriptionOut]
    recent_activity: list[ActivityItem]

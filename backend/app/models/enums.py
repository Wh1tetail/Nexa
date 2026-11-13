from enum import StrEnum

import sqlalchemy as sa


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class EnglishLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class SubscriptionStatus(StrEnum):
    """Derived (not stored) status of a subscription."""
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    FROZEN = "frozen"


class LessonStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class SubmissionStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    NEEDS_REVISION = "needs_revision"


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"  # has short answers awaiting manual check
    GRADED = "graded"


class NotificationType(StrEnum):
    HOMEWORK_ASSIGNED = "homework_assigned"
    HOMEWORK_SUBMITTED = "homework_submitted"
    HOMEWORK_REVIEWED = "homework_reviewed"
    TEST_ASSIGNED = "test_assigned"
    TEST_COMPLETED = "test_completed"
    TEST_GRADED = "test_graded"
    LESSON_CHANGED = "lesson_changed"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SYSTEM = "system"


def str_enum(enum_cls: type[StrEnum], name: str) -> sa.Enum:
    """Stored as VARCHAR + CHECK constraint (easier to migrate than native PG enums)."""
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )

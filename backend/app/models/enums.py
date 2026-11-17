from enum import StrEnum

import sqlalchemy as sa


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"
    METHODIST = "methodist"  # curriculum author: shared test library (and later courses)


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
    FILL_GAPS = "fill_gaps"  # text with gaps; per-gap points
    MATCHING = "matching"  # pairs left -> right; partial credit
    # content blocks (not scored): the following questions refer to them
    AUDIO = "audio"
    READING = "reading"


CONTENT_TYPES = frozenset({QuestionType.AUDIO, QuestionType.READING})


class LessonBlockType(StrEnum):
    """Blocks of a course lesson (see services/lesson_blocks.py)."""
    TEXT = "text"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    READING = "reading"  # text + questions
    LISTENING = "listening"  # audio + questions
    QUIZ = "quiz"  # several questions of any kind
    FILL_GAPS = "fill_gaps"
    MULTIPLE_CHOICE = "multiple_choice"
    MATCHING = "matching"


class XPReason(StrEnum):
    """What XP is given for; each (student, reason, object) is paid once."""
    LESSON = "lesson"  # a course lesson completed
    TEST = "test"  # a test graded (once per test)
    TEST_BONUS = "test_bonus"  # a test result at or above the bonus threshold
    MODULE = "module"  # every lesson of a module completed
    LEVEL = "level"  # every lesson of a course level completed


class AchievementCode(StrEnum):
    FIRST_LESSON = "first_lesson"
    FIRST_TEST = "first_test"
    PERFECT_SCORE = "perfect_score"
    STREAK_7 = "streak_7"
    LESSONS_10 = "lessons_10"
    LEVEL_COMPLETED = "level_completed"


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
    COURSE_ASSIGNED = "course_assigned"
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

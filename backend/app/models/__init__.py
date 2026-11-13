"""Import all models so Alembic autogenerate & relationship resolution see them."""
from app.models.file import Attachment
from app.models.homework import Homework, HomeworkSubmission
from app.models.lesson import Attendance, Lesson
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.models.test import Test, TestAnswer, TestAttempt, TestQuestion, test_assignments
from app.models.user import (
    Group,
    PasswordResetToken,
    StudentProfile,
    TeacherProfile,
    User,
    group_students,
)

__all__ = [
    "Attachment",
    "Attendance",
    "Group",
    "Homework",
    "HomeworkSubmission",
    "Lesson",
    "Notification",
    "PasswordResetToken",
    "StudentProfile",
    "Subscription",
    "TeacherProfile",
    "Test",
    "TestAnswer",
    "TestAttempt",
    "TestQuestion",
    "User",
    "group_students",
    "test_assignments",
]

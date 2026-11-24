"""Import all models so Alembic autogenerate & relationship resolution see them."""
from app.models.book import Book, BookChapter, BookJob, BookPage, QuestionDraft
from app.models.course import (
    Course,
    CourseAssignment,
    CourseAssignmentStudent,
    CourseLesson,
    CourseLevel,
    CourseModule,
    LessonBlock,
    LessonProgress,
)
from app.models.file import Attachment
from app.models.gamification import AppSetting, StudentAchievement, StudentActivityDay, XPTransaction
from app.models.homework import Homework, HomeworkSubmission
from app.models.lesson import Attendance, Lesson
from app.models.message import AuthAttempt, Message
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.models.test import (
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    TestSection,
    TestTag,
    test_assignments,
    test_section_links,
    test_tag_links,
)
from app.models.user import (
    Group,
    PasswordResetToken,
    StudentProfile,
    TeacherProfile,
    User,
    group_students,
)

__all__ = [
    "AppSetting",
    "Attachment",
    "AuthAttempt",
    "Attendance",
    "Book",
    "BookChapter",
    "BookJob",
    "BookPage",
    "Course",
    "CourseAssignment",
    "CourseAssignmentStudent",
    "CourseLesson",
    "CourseLevel",
    "CourseModule",
    "Group",
    "Homework",
    "HomeworkSubmission",
    "Lesson",
    "LessonBlock",
    "LessonProgress",
    "Message",
    "Notification",
    "PasswordResetToken",
    "QuestionDraft",
    "StudentAchievement",
    "StudentActivityDay",
    "StudentProfile",
    "Subscription",
    "TeacherProfile",
    "Test",
    "TestAnswer",
    "TestAttempt",
    "TestQuestion",
    "TestSection",
    "TestTag",
    "User",
    "XPTransaction",
    "group_students",
    "test_assignments",
    "test_section_links",
    "test_tag_links",
]

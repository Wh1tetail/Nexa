from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    analytics,
    auth,
    books,
    course_assignments,
    courses,
    dashboard,
    files,
    gamification,
    groups,
    homework,
    library,
    lessons,
    messages,
    notifications,
    student,
    student_courses,
    students,
    subscriptions,
    tests,
)

api_router = APIRouter()
for module in (
    auth, dashboard, students, groups, subscriptions, lessons,
    homework, tests, student, notifications, messages, files, admin, analytics, library, courses,
    course_assignments, student_courses, gamification, books,
):
    api_router.include_router(module.router)

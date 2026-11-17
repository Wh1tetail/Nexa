from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    analytics,
    auth,
    courses,
    dashboard,
    files,
    groups,
    homework,
    library,
    lessons,
    messages,
    notifications,
    student,
    students,
    subscriptions,
    tests,
)

api_router = APIRouter()
for module in (
    auth, dashboard, students, groups, subscriptions, lessons,
    homework, tests, student, notifications, messages, files, admin, analytics, library, courses,
):
    api_router.include_router(module.router)

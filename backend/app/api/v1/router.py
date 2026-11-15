from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    analytics,
    auth,
    dashboard,
    files,
    groups,
    homework,
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
    homework, tests, student, notifications, messages, files, admin, analytics,
):
    api_router.include_router(module.router)

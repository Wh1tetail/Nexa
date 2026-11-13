from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    dashboard,
    files,
    groups,
    homework,
    lessons,
    notifications,
    student,
    students,
    subscriptions,
    tests,
)

api_router = APIRouter()
for module in (
    auth, dashboard, students, groups, subscriptions, lessons,
    homework, tests, student, notifications, files, admin,
):
    api_router.include_router(module.router)

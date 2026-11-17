"""FastAPI dependencies: DB session, current user, role guards, ownership checks."""
from typing import Annotated

import jwt
from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BadRequest, Forbidden, NotFound, Unauthorized
from app.core.security import decode_token
from app.models import Group, StudentProfile, TeacherProfile, User
from app.models.enums import UserRole

bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB, creds: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> User:
    if creds is None:
        raise Unauthorized()
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Срок действия токена истёк") from None
    except jwt.PyJWTError:
        raise Unauthorized("Недействительный токен") from None
    if payload.get("type") != "access":
        raise Unauthorized("Неверный тип токена")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active or user.token_version != payload.get("ver"):
        raise Unauthorized("Сессия недействительна")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    def guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise Forbidden()
        return user

    return guard


def get_current_teacher(
    user: Annotated[User, Depends(require_roles(UserRole.TEACHER))],
) -> TeacherProfile:
    if user.teacher_profile is None:
        raise Forbidden("Профиль преподавателя не найден")
    return user.teacher_profile


def get_current_student(
    user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
) -> StudentProfile:
    if user.student_profile is None:
        raise Forbidden("Профиль ученика не найден")
    return user.student_profile


CurrentTeacher = Annotated[TeacherProfile, Depends(get_current_teacher)]


def get_acting_teacher(
    user: CurrentUser,
    db: DB,
    teacher_id: int | None = Query(None, description="admin only: whose students, groups and lessons"),
    x_teacher_id: int | None = Header(None, description="admin only: same as ?teacher_id="),
) -> TeacherProfile:
    """A teacher works with their own data; an administrator works with a chosen
    teacher's data (?teacher_id=). Everything below still checks ownership
    against the returned profile, so a teacher can never reach another one."""
    if user.role == UserRole.TEACHER and user.teacher_profile is not None:
        return user.teacher_profile
    if user.role == UserRole.ADMIN:
        teacher_id = teacher_id if teacher_id is not None else x_teacher_id
        if teacher_id is None:
            raise BadRequest("Выберите преподавателя")
        profile = db.get(TeacherProfile, teacher_id)
        if profile is None:
            raise NotFound("Преподаватель не найден")
        return profile
    raise Forbidden()


def get_admin_acting_teacher(
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: DB,
    teacher_id: int | None = Query(None, description="whose students, groups and lessons"),
    x_teacher_id: int | None = Header(None, description="same as ?teacher_id="),
) -> TeacherProfile:
    """Creating students and groups, scheduling, rescheduling and deleting
    lessons are administrator-only; the admin acts for a chosen teacher."""
    return get_acting_teacher(user, db, teacher_id, x_teacher_id)


# teacher (own data) or admin (?teacher_id=)
ActingTeacher = Annotated[TeacherProfile, Depends(get_acting_teacher)]
# admin only (?teacher_id=)
AdminForTeacher = Annotated[TeacherProfile, Depends(get_admin_acting_teacher)]
CurrentStudent = Annotated[StudentProfile, Depends(get_current_student)]


def get_student_with_access(student: CurrentStudent, db: DB) -> StudentProfile:
    """A student whose subscription is active: lessons, homework and tests."""
    from app.services.subscription_service import has_access

    if not has_access(db, student.id):
        raise Forbidden("Доступ к занятиям, заданиям и тестам откроется после продления абонемента",
                        code="subscription_required")
    return student


StudentWithAccess = Annotated[StudentProfile, Depends(get_student_with_access)]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
# shared test library: methodists and admins edit; teachers also read (and copy)
LibraryEditor = Annotated[User, Depends(require_roles(UserRole.METHODIST, UserRole.ADMIN))]
LibraryReader = Annotated[User, Depends(require_roles(UserRole.TEACHER, UserRole.METHODIST, UserRole.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))]


# ---------- ownership helpers ----------

def get_owned_student(db: Session, teacher: TeacherProfile, student_id: int) -> StudentProfile:
    """Return the student only if it belongs to this teacher (404 otherwise,
    so other teachers' student ids are not even revealed)."""
    student = db.get(StudentProfile, student_id)
    if student is None or student.teacher_id != teacher.id:
        raise NotFound("Ученик не найден")
    return student


def get_owned_students(
    db: Session, teacher: TeacherProfile, student_ids: list[int]
) -> list[StudentProfile]:
    if not student_ids:
        return []
    ids = set(student_ids)
    students = db.scalars(
        select(StudentProfile).where(
            StudentProfile.id.in_(ids), StudentProfile.teacher_id == teacher.id
        )
    ).all()
    if len(students) != len(ids):
        raise Forbidden("Можно назначать только своих учеников")
    return list(students)


def get_owned_group(db: Session, teacher: TeacherProfile, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise NotFound("Группа не найдена")
    return group


def resolve_recipients(
    db: Session,
    teacher: TeacherProfile,
    student_ids: list[int],
    group_ids: list[int],
) -> list[StudentProfile]:
    """Union of explicitly selected students and members of selected groups."""
    result: dict[int, StudentProfile] = {s.id: s for s in get_owned_students(db, teacher, student_ids)}
    for gid in set(group_ids):
        for s in get_owned_group(db, teacher, gid).students:
            result[s.id] = s
    return list(result.values())

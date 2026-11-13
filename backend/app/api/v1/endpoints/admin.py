"""Administrator console: all users, teachers, students and their assignment."""
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.api.deps import DB, AdminUser
from app.core.config import settings
from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.security import hash_password
from app.models import Lesson, StudentProfile, Subscription, TeacherProfile, User
from app.models.enums import UserRole
from app.repositories import student_repository as repo
from app.schemas.admin import AdminPasswordRequest, AdminStats, AdminUserOut, AdminUserUpdate
from app.schemas.user import (
    InviteResponse,
    StudentBrief,
    StudentCreate,
    StudentProfileOut,
    TeacherCreate,
    TeacherOut,
)
from app.services import account_service, email_service, student_service
from app.services import subscription_service as sub_svc

router = APIRouter(prefix="/admin", tags=["admin"])


def _students_per_teacher(db) -> dict[int, int]:
    rows = db.execute(
        select(StudentProfile.teacher_id, func.count()).group_by(StudentProfile.teacher_id)
    ).all()
    return {tid: n for tid, n in rows if tid is not None}


def _user_out(u: User, counts: dict[int, int]) -> AdminUserOut:
    out = AdminUserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        phone=u.phone,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )
    if u.student_profile:
        sp = u.student_profile
        out.student_id = sp.id
        out.english_level = sp.english_level
        out.teacher_id = sp.teacher_id
        out.teacher_name = sp.teacher.user.full_name if sp.teacher else None
    if u.teacher_profile:
        out.teacher_profile_id = u.teacher_profile.id
        out.students_count = counts.get(u.teacher_profile.id, 0)
    return out


def _get_user(db, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("Пользователь не найден")
    return user


@router.get("/stats", response_model=AdminStats)
def stats(_: AdminUser, db: DB) -> AdminStats:
    by_role = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    active_students = db.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.STUDENT, User.is_active.is_(True))
    )
    unassigned = db.scalar(select(func.count()).select_from(StudentProfile).where(StudentProfile.teacher_id.is_(None)))
    today = sub_svc.today()
    active_subs = db.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.start_date <= today, Subscription.end_date >= today, Subscription.is_frozen.is_(False)
        )
    )
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lessons = db.scalar(select(func.count()).select_from(Lesson).where(Lesson.starts_at >= month_start))
    return AdminStats(
        teachers=by_role.get(UserRole.TEACHER, 0),
        students=by_role.get(UserRole.STUDENT, 0),
        active_students=active_students or 0,
        unassigned_students=unassigned or 0,
        active_subscriptions=active_subs or 0,
        lessons_this_month=lessons or 0,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _: AdminUser,
    db: DB,
    role: UserRole | None = None,
    search: str | None = None,
    active: bool | None = None,
    teacher_id: int | None = None,
) -> list[AdminUserOut]:
    q = select(User).options(
        joinedload(User.student_profile).joinedload(StudentProfile.teacher).joinedload(TeacherProfile.user),
        joinedload(User.teacher_profile),
    )
    if role:
        q = q.where(User.role == role)
    if active is not None:
        q = q.where(User.is_active.is_(active))
    if search:
        pattern = f"%{search.strip().lower()}%"
        q = q.where(or_(func.lower(User.full_name).like(pattern), func.lower(User.email).like(pattern)))
    if teacher_id is not None:
        q = q.join(StudentProfile, StudentProfile.user_id == User.id).where(StudentProfile.teacher_id == teacher_id)
    users = db.scalars(q.order_by(User.role, User.full_name)).unique().all()
    counts = _students_per_teacher(db)
    return [_user_out(u, counts) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: AdminUserUpdate, admin: AdminUser, db: DB) -> AdminUserOut:
    user = _get_user(db, user_id)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("is_active") is False and user.id == admin.id:
        raise BadRequest("Нельзя деактивировать собственный аккаунт")
    if payload.get("full_name"):
        user.full_name = payload["full_name"].strip()
    if "phone" in payload:
        user.phone = payload["phone"] or None
    if payload.get("is_active") is not None and payload["is_active"] != user.is_active:
        user.is_active = payload["is_active"]
        if not user.is_active:
            user.token_version += 1  # sign out everywhere
    db.commit()
    return _user_out(user, _students_per_teacher(db))


@router.post("/users/{user_id}/password", response_model=InviteResponse)
def set_password(
    user_id: int, data: AdminPasswordRequest, _: AdminUser, db: DB, background: BackgroundTasks
) -> InviteResponse:
    user = _get_user(db, user_id)
    if data.password:
        user.password_hash = hash_password(data.password)
        user.token_version += 1
        db.commit()
        return InviteResponse(detail="Пароль изменён")
    url = account_service.reset_link(db, user)
    db.commit()
    background.add_task(email_service.password_reset, user.email, user.full_name, url)
    return InviteResponse(
        detail=f"Ссылка для смены пароля отправлена на {user.email}",
        dev_invite_url=url if settings.DEBUG else None,
    )


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(_: AdminUser, db: DB) -> list[TeacherOut]:
    teachers = db.scalars(
        select(TeacherProfile).join(TeacherProfile.user).options(joinedload(TeacherProfile.user)).order_by(User.full_name)
    ).all()
    counts = _students_per_teacher(db)
    return [
        TeacherOut(id=t.id, user_id=t.user_id, full_name=t.user.full_name, email=t.user.email, students_count=counts.get(t.id, 0))
        for t in teachers
    ]


@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(data: TeacherCreate, _: AdminUser, db: DB, background: BackgroundTasks) -> TeacherOut:
    if student_service.email_taken(db, data.email):
        raise Conflict("Пользователь с таким email уже существует")
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password or secrets.token_urlsafe(32)),
        full_name=data.full_name.strip(),
        phone=data.phone,
        role=UserRole.TEACHER,
    )
    profile = TeacherProfile(user=user, bio=data.bio)
    db.add_all([user, profile])
    db.flush()
    if data.send_invite:
        student_service.send_invitation(db, user, None, background)
    db.commit()
    return TeacherOut(id=profile.id, user_id=user.id, full_name=user.full_name, email=user.email, students_count=0)


@router.get("/students", response_model=list[StudentBrief])
def list_all_students(_: AdminUser, db: DB, search: str | None = None) -> list[StudentBrief]:
    return student_service.briefs(db, repo.list_for_teacher(db, None, search))


@router.post("/students", response_model=StudentProfileOut, status_code=status.HTTP_201_CREATED)
def create_student(data: StudentCreate, _: AdminUser, db: DB, background: BackgroundTasks) -> StudentProfileOut:
    teacher = db.get(TeacherProfile, data.teacher_id) if data.teacher_id else None
    if data.teacher_id and teacher is None:
        raise NotFound("Преподаватель не найден")
    student = student_service.create_student(db, data, teacher)
    db.flush()
    url = None
    if data.send_invite:
        url = student_service.send_invitation(db, student.user, teacher.user.full_name if teacher else None, background)
    db.commit()
    db.refresh(student)
    out = student_service.to_profile(db, student)
    out.dev_invite_url = url if settings.DEBUG else None
    return out


@router.post("/students/{student_id}/teacher/{teacher_id}", response_model=StudentProfileOut)
def reassign_student(student_id: int, teacher_id: int, _: AdminUser, db: DB) -> StudentProfileOut:
    """Move a student to another teacher (group memberships of the old teacher are removed)."""
    student = db.get(StudentProfile, student_id)
    teacher = db.get(TeacherProfile, teacher_id)
    if not student or not teacher:
        raise NotFound()
    if student.teacher_id != teacher.id:
        student.teacher_id = teacher.id
        student.groups = []
        db.commit()
        db.refresh(student)
    return student_service.to_profile(db, student)

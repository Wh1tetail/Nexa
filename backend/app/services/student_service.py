import secrets

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict
from app.core.security import hash_password
from app.models import StudentProfile, Subscription, TeacherProfile, User
from app.models.enums import UserRole
from app.repositories import student_repository as repo
from app.services import account_service, email_service
from app.schemas.user import GroupBrief, StudentBrief, StudentCreate, StudentProfileOut
from app.services import subscription_service as subs


def pick_current(sub_list: list[Subscription]) -> Subscription | None:
    if not sub_list:
        return None
    ref = subs.today()
    started = [s for s in sub_list if s.start_date <= ref]
    return started[0] if started else sub_list[-1]


def to_brief(student: StudentProfile, sub: Subscription | None) -> StudentBrief:
    return StudentBrief(
        id=student.id,
        user_id=student.user_id,
        full_name=student.user.full_name,
        email=student.user.email,
        phone=student.user.phone,
        english_level=student.english_level,
        is_active=student.user.is_active,
        created_at=student.user.created_at,
        groups=[GroupBrief(id=g.id, name=g.name) for g in student.groups],
        subscription_status=subs.compute_status(sub) if sub else None,
        lessons_left=(sub.total_lessons - sub.used_lessons) if sub else None,
        days_left=subs.days_left(sub) if sub else None,
        subscription_end=sub.end_date if sub else None,
    )


def to_profile(db: Session, student: StudentProfile) -> StudentProfileOut:
    sub = subs.current_subscription(db, student.id)
    brief = to_brief(student, sub)
    return StudentProfileOut(
        **brief.model_dump(),
        notes=student.notes,
        teacher_name=student.teacher.user.full_name if student.teacher else None,
    )


def briefs(db: Session, students: list[StudentProfile]) -> list[StudentBrief]:
    by_student = repo.subscriptions_by_student(db, [s.id for s in students])
    return [to_brief(s, pick_current(by_student.get(s.id, []))) for s in students]


def email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(func.lower(User.email) == email.lower())) is not None


def create_student(db: Session, data: StudentCreate, teacher: TeacherProfile | None) -> StudentProfile:
    if email_taken(db, data.email):
        raise Conflict("Пользователь с таким email уже существует")
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password or secrets.token_urlsafe(32)),
        full_name=data.full_name.strip(),
        phone=data.phone,
        role=UserRole.STUDENT,
    )
    profile = StudentProfile(
        user=user,
        teacher_id=teacher.id if teacher else None,
        english_level=data.english_level,
        notes=data.notes,
    )
    db.add_all([user, profile])
    return profile


def send_invitation(db: Session, user: User, teacher_name: str | None, background: BackgroundTasks) -> str:
    """Issue a set-password link and e-mail it in the background. Caller commits."""
    url = account_service.invite_link(db, user)
    background.add_task(email_service.invitation, user.email, user.full_name, url, teacher_name)
    return url

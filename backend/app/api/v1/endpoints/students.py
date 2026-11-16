from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.i18n import tr
from app.core.config import settings
from app.api.deps import DB, ActingTeacher, AdminForTeacher, get_owned_group, get_owned_student
from app.models import StudentProfile, Subscription
from app.models.enums import EnglishLevel, SubscriptionStatus
from app.repositories import student_repository as repo
from app.schemas.subscription import SubscriptionOut
from app.schemas.user import InviteResponse, StudentBrief, StudentCreate, StudentProfileOut, StudentUpdate
from app.services import participation
from app.services import student_service, subscription_service

router = APIRouter(prefix="/students", tags=["students (teacher)"])


@router.get("", response_model=list[StudentBrief])
def list_students(
    teacher: ActingTeacher,
    db: DB,
    search: str | None = None,
    level: EnglishLevel | None = None,
    group_id: int | None = None,
    subscription_status: SubscriptionStatus | None = None,
    active: bool | None = None,
) -> list[StudentBrief]:
    students = repo.list_for_teacher(db, teacher.id, search, level, group_id, active)
    items = student_service.briefs(db, students)
    if subscription_status:
        items = [i for i in items if i.subscription_status == subscription_status]
    return items


@router.post("", response_model=StudentProfileOut, status_code=status.HTTP_201_CREATED)
def create_student(
    data: StudentCreate, teacher: AdminForTeacher, db: DB, background: BackgroundTasks
) -> StudentProfileOut:
    groups = [get_owned_group(db, teacher, gid) for gid in set(data.group_ids)]
    student = student_service.create_student(db, data, teacher)
    student.groups = groups
    db.flush()
    for g in groups:  # a new group member joins the group's upcoming lessons
        participation.assign_group_lessons(db, g, [student])
    url = None
    if data.send_invite:
        url = student_service.send_invitation(db, student.user, teacher.user.full_name, background)
    db.commit()
    db.refresh(student)
    out = student_service.to_profile(db, student)
    out.dev_invite_url = url if settings.DEBUG else None
    return out


@router.post("/{student_id}/invite", response_model=InviteResponse)
def resend_invite(student_id: int, teacher: ActingTeacher, db: DB, background: BackgroundTasks) -> InviteResponse:
    """(Re)send an e-mail with a link to set the password."""
    student = get_owned_student(db, teacher, student_id)
    url = student_service.send_invitation(db, student.user, teacher.user.full_name, background)
    db.commit()
    return InviteResponse(
        detail=tr("Приглашение отправлено на {email}", email=student.user.email),
        dev_invite_url=url if settings.DEBUG else None,
    )


@router.get("/{student_id}", response_model=StudentProfileOut)
def get_student(student_id: int, teacher: ActingTeacher, db: DB) -> StudentProfileOut:
    return student_service.to_profile(db, get_owned_student(db, teacher, student_id))


@router.patch("/{student_id}", response_model=StudentProfileOut)
def update_student(
    student_id: int, data: StudentUpdate, teacher: ActingTeacher, db: DB
) -> StudentProfileOut:
    student = get_owned_student(db, teacher, student_id)
    payload = data.model_dump(exclude_unset=True)
    if "full_name" in payload and payload["full_name"]:
        student.user.full_name = payload["full_name"].strip()
    if "phone" in payload:
        student.user.phone = payload["phone"]
    if "is_active" in payload and payload["is_active"] is not None:
        student.user.is_active = payload["is_active"]
        if not payload["is_active"]:
            student.user.token_version += 1
    if payload.get("english_level"):
        student.english_level = payload["english_level"]
    if "notes" in payload:
        student.notes = payload["notes"]
    if payload.get("group_ids") is not None:
        student.groups = [get_owned_group(db, teacher, g) for g in set(payload["group_ids"])]
    db.commit()
    db.refresh(student)
    return student_service.to_profile(db, student)


@router.get("/{student_id}/subscriptions", response_model=list[SubscriptionOut])
def student_subscriptions(student_id: int, teacher: ActingTeacher, db: DB) -> list[SubscriptionOut]:
    get_owned_student(db, teacher, student_id)
    subs = db.scalars(
        select(Subscription)
        .options(joinedload(Subscription.student).joinedload(StudentProfile.user))
        .where(Subscription.student_id == student_id)
        .order_by(Subscription.start_date.desc())
    ).all()
    return [subscription_service.to_out(s) for s in subs]

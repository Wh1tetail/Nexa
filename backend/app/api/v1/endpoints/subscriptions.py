from datetime import timedelta

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import DB, ActingTeacher, AdminForTeacher, get_owned_student
from app.core.exceptions import BadRequest, NotFound
from app.models import StudentProfile, Subscription, TeacherProfile
from app.models.enums import SubscriptionStatus
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionExtend,
    SubscriptionOut,
    SubscriptionUpdate,
    UseLessonRequest,
)
from app.services import subscription_service as svc

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Teachers only view subscriptions; creating and every change is admin-only
# (the admin acts for the teacher chosen with X-Teacher-Id / ?teacher_id=).


def _get_owned(db: Session, teacher: TeacherProfile, sub_id: int) -> Subscription:
    sub = db.get(Subscription, sub_id)
    if sub is None or sub.student.teacher_id != teacher.id:
        raise NotFound("Абонемент не найден")
    return sub


@router.get("", response_model=list[SubscriptionOut])
def list_subscriptions(
    teacher: ActingTeacher,
    db: DB,
    status_filter: SubscriptionStatus | None = None,
    student_id: int | None = None,
    current_only: bool = True,
) -> list[SubscriptionOut]:
    q = (
        select(Subscription)
        .join(Subscription.student)
        .options(joinedload(Subscription.student).joinedload(StudentProfile.user))
        .where(StudentProfile.teacher_id == teacher.id)
        .order_by(Subscription.end_date.asc())
    )
    if student_id:
        q = q.where(Subscription.student_id == student_id)
    subs = list(db.scalars(q).unique().all())
    if current_only and not student_id:
        latest: dict[int, Subscription] = {}
        ref = svc.today()
        for s in sorted(subs, key=lambda s: (s.start_date <= ref, s.end_date), reverse=True):
            latest.setdefault(s.student_id, s)
        subs = sorted(latest.values(), key=lambda s: s.end_date)
    items = [svc.to_out(s) for s in subs]
    if status_filter:
        items = [i for i in items if i.status == status_filter]
    return items


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(data: SubscriptionCreate, teacher: AdminForTeacher, db: DB) -> SubscriptionOut:
    get_owned_student(db, teacher, data.student_id)
    sub = Subscription(teacher_id=teacher.id, **data.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return svc.to_out(sub)


@router.get("/{sub_id}", response_model=SubscriptionOut)
def get_subscription(sub_id: int, teacher: ActingTeacher, db: DB) -> SubscriptionOut:
    return svc.to_out(_get_owned(db, teacher, sub_id))


@router.patch("/{sub_id}", response_model=SubscriptionOut)
def update_subscription(
    sub_id: int, data: SubscriptionUpdate, teacher: AdminForTeacher, db: DB
) -> SubscriptionOut:
    sub = _get_owned(db, teacher, sub_id)
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        if v is not None or k in ("title", "notes"):
            setattr(sub, k, v)
    if sub.end_date < sub.start_date:
        raise BadRequest("Дата окончания не может быть раньше даты начала")
    if sub.used_lessons > sub.total_lessons:
        raise BadRequest("Использованных занятий больше, чем оплачено")
    if "end_date" in payload:
        svc.reset_notification_flags(sub)
    db.commit()
    return svc.to_out(sub)


@router.post("/{sub_id}/extend", response_model=SubscriptionOut)
def extend_subscription(
    sub_id: int, data: SubscriptionExtend, teacher: AdminForTeacher, db: DB
) -> SubscriptionOut:
    sub = _get_owned(db, teacher, sub_id)
    if data.new_end_date:
        if data.new_end_date < sub.start_date:
            raise BadRequest("Новая дата окончания раньше даты начала")
        sub.end_date = data.new_end_date
    elif data.add_days:
        base = max(sub.end_date, svc.today())
        sub.end_date = base + timedelta(days=data.add_days)
    sub.total_lessons += data.add_lessons
    svc.reset_notification_flags(sub)
    db.commit()
    return svc.to_out(sub)


@router.post("/{sub_id}/use-lesson", response_model=SubscriptionOut)
def use_lesson(sub_id: int, data: UseLessonRequest, teacher: AdminForTeacher, db: DB) -> SubscriptionOut:
    sub = _get_owned(db, teacher, sub_id)
    svc.use_lessons(sub, data.count)
    db.commit()
    return svc.to_out(sub)


@router.post("/{sub_id}/freeze", response_model=SubscriptionOut)
def freeze(sub_id: int, teacher: AdminForTeacher, db: DB) -> SubscriptionOut:
    sub = _get_owned(db, teacher, sub_id)
    if not sub.is_frozen:
        sub.is_frozen = True
        sub.frozen_at = svc.today()
        db.commit()
    return svc.to_out(sub)


@router.post("/{sub_id}/unfreeze", response_model=SubscriptionOut)
def unfreeze(sub_id: int, teacher: AdminForTeacher, db: DB) -> SubscriptionOut:
    sub = _get_owned(db, teacher, sub_id)
    if sub.is_frozen:
        # The frozen period is added to the end date.
        if sub.frozen_at:
            sub.end_date += timedelta(days=max((svc.today() - sub.frozen_at).days, 0))
        sub.is_frozen = False
        sub.frozen_at = None
        svc.reset_notification_flags(sub)
        db.commit()
    return svc.to_out(sub)


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(sub_id: int, teacher: AdminForTeacher, db: DB) -> Response:
    db.delete(_get_owned(db, teacher, sub_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

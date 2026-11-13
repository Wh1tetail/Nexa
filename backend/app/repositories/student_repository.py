"""Query helpers for students (kept out of the API layer)."""
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Group, StudentProfile, Subscription, User, group_students
from app.models.enums import EnglishLevel


def base_query() -> Select[tuple[StudentProfile]]:
    return select(StudentProfile).join(StudentProfile.user).options(
        joinedload(StudentProfile.user),
        selectinload(StudentProfile.groups),
        joinedload(StudentProfile.teacher),
    )


def list_for_teacher(
    db: Session,
    teacher_id: int | None,
    search: str | None = None,
    level: EnglishLevel | None = None,
    group_id: int | None = None,
    active: bool | None = None,
) -> list[StudentProfile]:
    q = base_query()
    if teacher_id is not None:
        q = q.where(StudentProfile.teacher_id == teacher_id)
    if search:
        # Bound parameters -> safe from SQL injection
        pattern = f"%{search.strip().lower()}%"
        q = q.where(
            or_(
                func.lower(User.full_name).like(pattern),
                func.lower(User.email).like(pattern),
                User.phone.like(pattern),
            )
        )
    if level:
        q = q.where(StudentProfile.english_level == level)
    if group_id:
        q = q.where(
            StudentProfile.id.in_(
                select(group_students.c.student_id).where(group_students.c.group_id == group_id)
            )
        )
    if active is not None:
        q = q.where(User.is_active.is_(active))
    return list(db.scalars(q.order_by(User.full_name)).unique().all())


def subscriptions_by_student(db: Session, student_ids: list[int]) -> dict[int, list[Subscription]]:
    if not student_ids:
        return {}
    rows = db.scalars(
        select(Subscription)
        .where(Subscription.student_id.in_(student_ids))
        .order_by(Subscription.end_date.desc(), Subscription.id.desc())
    ).all()
    out: dict[int, list[Subscription]] = {}
    for s in rows:
        out.setdefault(s.student_id, []).append(s)
    return out


def groups_for_teacher(db: Session, teacher_id: int) -> list[Group]:
    return list(
        db.scalars(
            select(Group)
            .options(selectinload(Group.students).joinedload(StudentProfile.user))
            .where(Group.teacher_id == teacher_id)
            .order_by(Group.name)
        ).all()
    )

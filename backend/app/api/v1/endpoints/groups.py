from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, ActingTeacher, AdminForTeacher, get_owned_group, get_owned_students
from app.core.exceptions import Conflict
from app.models import Attendance, Group, Lesson
from app.models.enums import LessonStatus
from app.repositories import student_repository as repo
from app.schemas.group import GroupCreate, GroupMember, GroupOut, GroupUpdate
from app.services import participation

router = APIRouter(prefix="/groups", tags=["groups"])


def _upcoming(db, group_ids: list[int]) -> dict[int, int]:
    if not group_ids:
        return {}
    rows = db.execute(
        select(Lesson.group_id, func.count()).where(
            Lesson.group_id.in_(group_ids), Lesson.status == LessonStatus.SCHEDULED,
            Lesson.starts_at >= datetime.now(UTC),
        ).group_by(Lesson.group_id)
    ).all()
    return dict(rows)


def to_out(g: Group, upcoming: int = 0) -> GroupOut:
    return GroupOut(
        upcoming_lessons=upcoming,
        id=g.id,
        name=g.name,
        level=g.level,
        description=g.description,
        created_at=g.created_at,
        students=sorted(
            (GroupMember(id=s.id, full_name=s.user.full_name, english_level=s.english_level) for s in g.students),
            key=lambda m: m.full_name,
        ),
    )


@router.get("", response_model=list[GroupOut])
def list_groups(teacher: ActingTeacher, db: DB) -> list[GroupOut]:
    groups = repo.groups_for_teacher(db, teacher.id)
    upcoming = _upcoming(db, [g.id for g in groups])
    return [to_out(g, upcoming.get(g.id, 0)) for g in groups]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(data: GroupCreate, teacher: AdminForTeacher, db: DB) -> GroupOut:
    group = Group(teacher_id=teacher.id, name=data.name.strip(), level=data.level, description=data.description)
    group.students = get_owned_students(db, teacher, data.student_ids)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("Группа с таким названием уже существует") from None
    return to_out(group)


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(group_id: int, data: GroupUpdate, teacher: ActingTeacher, db: DB) -> GroupOut:
    group = get_owned_group(db, teacher, group_id)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("name"):
        group.name = payload["name"].strip()
    if "level" in payload:
        group.level = payload["level"]
    if "description" in payload:
        group.description = payload["description"]
    assigned = released = None
    if payload.get("student_ids") is not None:
        before = _upcoming_places(db, group)
        added, removed = participation.change_group_members(
            db, group, get_owned_students(db, teacher, payload["student_ids"]),
            assign_lessons=data.assign_lessons, lessons_from=data.lessons_from,
        )
        after = _upcoming_places(db, group)
        assigned = sum(max(after.get(s.id, 0) - before.get(s.id, 0), 0) for s in added)
        released = sum(before.get(sid, 0) - after.get(sid, 0) for sid in removed)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("Группа с таким названием уже существует") from None
    out = to_out(group, _upcoming(db, [group.id]).get(group.id, 0))
    out.lessons_assigned, out.lessons_released = assigned, released
    return out


def _upcoming_places(db, group: Group) -> dict[int, int]:
    """student_id -> number of the group's upcoming lessons they take part in."""
    rows = db.execute(
        select(Attendance.student_id, func.count())
        .join(Lesson, Lesson.id == Attendance.lesson_id)
        .where(
            Lesson.group_id == group.id, Lesson.status == LessonStatus.SCHEDULED,
            Lesson.starts_at >= datetime.now(UTC), Attendance.removed_at.is_(None),
        )
        .group_by(Attendance.student_id)
    ).all()
    return dict(rows)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, teacher: AdminForTeacher, db: DB) -> Response:
    db.delete(get_owned_group(db, teacher, group_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from fastapi import APIRouter, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentTeacher, get_owned_group, get_owned_students
from app.core.exceptions import Conflict
from app.models import Group
from app.repositories import student_repository as repo
from app.schemas.group import GroupCreate, GroupMember, GroupOut, GroupUpdate

router = APIRouter(prefix="/groups", tags=["groups"])


def to_out(g: Group) -> GroupOut:
    return GroupOut(
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
def list_groups(teacher: CurrentTeacher, db: DB) -> list[GroupOut]:
    return [to_out(g) for g in repo.groups_for_teacher(db, teacher.id)]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(data: GroupCreate, teacher: CurrentTeacher, db: DB) -> GroupOut:
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
def update_group(group_id: int, data: GroupUpdate, teacher: CurrentTeacher, db: DB) -> GroupOut:
    group = get_owned_group(db, teacher, group_id)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("name"):
        group.name = payload["name"].strip()
    if "level" in payload:
        group.level = payload["level"]
    if "description" in payload:
        group.description = payload["description"]
    if payload.get("student_ids") is not None:
        group.students = get_owned_students(db, teacher, payload["student_ids"])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("Группа с таким названием уже существует") from None
    return to_out(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, teacher: CurrentTeacher, db: DB) -> Response:
    db.delete(get_owned_group(db, teacher, group_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

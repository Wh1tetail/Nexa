"""Teachers assign course levels / modules to students and groups and follow their progress."""
from fastapi import APIRouter, Response, status

from app.api.deps import DB, ActingTeacher, get_owned_group, get_owned_student, get_owned_students
from app.core.exceptions import BadRequest, NotFound
from app.models import CourseLevel, CourseModule
from app.schemas.course_assignment import (
    AssignIn,
    AssignmentDetail,
    AssignmentItem,
    AssignmentUpdate,
    AssignResult,
    CourseProgressOut,
    StudentIdsIn,
    StudentProgressRow,
)
from app.services import course_progress as cp
from app.services import course_service as cs

router = APIRouter(prefix="/course-assignments", tags=["course-assignments"])


@router.post("", response_model=AssignResult, status_code=status.HTTP_201_CREATED)
def assign(data: AssignIn, teacher: ActingTeacher, db: DB) -> AssignResult:
    """Give a level or a module of a published course to students and/or groups."""
    course = cs.get_course(db, teacher.user, data.course_id)  # teachers: published courses only
    level = module = None
    if data.level_id is not None:
        level = db.get(CourseLevel, data.level_id)
        if level is None or level.course_id != course.id:
            raise NotFound("Уровень не найден")
    else:
        module = db.get(CourseModule, data.module_id)
        if module is None or module.level.course_id != course.id:
            raise NotFound("Модуль не найден")
    students = get_owned_students(db, teacher, data.student_ids)
    groups = [get_owned_group(db, teacher, gid) for gid in dict.fromkeys(data.group_ids)]
    result = cp.assign(db, teacher, course, level, module, students, groups, data.starts_at, data.due_at)
    db.commit()
    return result


@router.get("", response_model=list[AssignmentItem])
def list_assignments(teacher: ActingTeacher, db: DB, include_removed: bool = False) -> list[AssignmentItem]:
    return [cp.assignment_item(db, a) for a in cp.teacher_assignments(db, teacher, include_removed)]


@router.get("/students", response_model=list[StudentProgressRow])
def students_progress(teacher: ActingTeacher, db: DB) -> list[StudentProgressRow]:
    """The teacher's students and how far they are in their assigned courses."""
    return cp.students_overview(db, teacher)


@router.get("/students/{student_id}/progress", response_model=CourseProgressOut)
def student_progress(student_id: int, teacher: ActingTeacher, db: DB) -> CourseProgressOut:
    return cp.course_progress(db, get_owned_student(db, teacher, student_id))


@router.get("/{assignment_id}", response_model=AssignmentDetail)
def get_assignment(assignment_id: int, teacher: ActingTeacher, db: DB) -> AssignmentDetail:
    return cp.assignment_detail(db, cp.get_teacher_assignment(db, teacher, assignment_id))


@router.patch("/{assignment_id}", response_model=AssignmentDetail)
def update_assignment(assignment_id: int, data: AssignmentUpdate, teacher: ActingTeacher, db: DB) -> AssignmentDetail:
    a = cp.get_teacher_assignment(db, teacher, assignment_id)
    if data.starts_at is not None:
        a.starts_at = data.starts_at
    if data.clear_due:
        a.due_at = None
    elif data.due_at is not None:
        a.due_at = data.due_at
    if a.due_at and a.due_at <= a.starts_at:
        raise BadRequest("Срок должен быть позже даты начала")
    db.commit()
    return cp.assignment_detail(db, a)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_assignment(assignment_id: int, teacher: ActingTeacher, db: DB) -> Response:
    """Students stop seeing it; their progress is kept."""
    a = cp.get_teacher_assignment(db, teacher, assignment_id)
    if a.removed_at is None:
        a.removed_at = cp.now()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{assignment_id}/students", response_model=AssignmentDetail)
def add_students(assignment_id: int, data: StudentIdsIn, teacher: ActingTeacher, db: DB) -> AssignmentDetail:
    a = cp.get_teacher_assignment(db, teacher, assignment_id)
    if a.removed_at is not None:
        raise NotFound("Назначение не найдено")
    cp.add_members(db, a, get_owned_students(db, teacher, data.student_ids))
    db.commit()
    return cp.assignment_detail(db, a)


@router.delete("/{assignment_id}/students/{student_id}", response_model=AssignmentDetail)
def remove_student(assignment_id: int, student_id: int, teacher: ActingTeacher, db: DB) -> AssignmentDetail:
    """Take one student off (their progress stays)."""
    a = cp.get_teacher_assignment(db, teacher, assignment_id)
    cp.remove_members(a, {student_id})
    db.commit()
    return cp.assignment_detail(db, a)

from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentStudent, CurrentTeacher, get_owned_group, get_owned_student
from app.schemas.analytics import StudentProgress, TeacherOverview
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=TeacherOverview)
def overview(
    teacher: CurrentTeacher,
    db: DB,
    period: int = Query(90, ge=7, le=365, description="days"),
    group_id: int | None = None,
) -> TeacherOverview:
    """All of the teacher's active students over the period, those needing attention first."""
    if group_id is not None:
        get_owned_group(db, teacher, group_id)  # 404 for someone else's group
    return analytics_service.teacher_overview(db, teacher.id, period, group_id)


@router.get("/students/{student_id}", response_model=StudentProgress)
def student_progress(student_id: int, teacher: CurrentTeacher, db: DB) -> StudentProgress:
    student = get_owned_student(db, teacher, student_id)
    return analytics_service.student_progress(db, student, teacher.user)


@router.get("/me", response_model=StudentProgress)
def my_progress(student: CurrentStudent, db: DB) -> StudentProgress:
    return analytics_service.student_progress(db, student, student.user)

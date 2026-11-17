"""Student side of courses: assigned courses, lessons, exercises and progress.
Like other learning content, it needs an active subscription."""
from fastapi import APIRouter

from app.api.deps import DB, StudentWithAccess
from app.schemas.course import CheckRequest, CheckResult
from app.schemas.course_assignment import (
    CourseProgressOut,
    PlayOut,
    StudentCourseDetail,
    StudentCourseItem,
    StudentLessonRow,
    StudentLessonView,
)
from app.schemas.gamification import Awards
from app.services import course_progress as cp
from app.services import gamification

router = APIRouter(prefix="/me", tags=["student-courses"])


@router.get("/courses", response_model=list[StudentCourseItem])
def my_courses(student: StudentWithAccess, db: DB) -> list[StudentCourseItem]:
    return cp.student_courses(db, student)


@router.get("/courses/{assignment_id}", response_model=StudentCourseDetail)
def my_course(assignment_id: int, student: StudentWithAccess, db: DB) -> StudentCourseDetail:
    return cp.student_course(db, student, assignment_id)


@router.get("/course-lessons", response_model=list[StudentLessonRow])
def my_lessons(student: StudentWithAccess, db: DB) -> list[StudentLessonRow]:
    return cp.student_lessons(db, student)


@router.get("/course-lessons/{lesson_id}", response_model=StudentLessonView)
def my_lesson(lesson_id: int, student: StudentWithAccess, db: DB) -> StudentLessonView:
    return cp.lesson_view(db, student, lesson_id)


@router.post("/course-lessons/{lesson_id}/blocks/{block_id}/check", response_model=CheckResult)
def check(lesson_id: int, block_id: int, data: CheckRequest, student: StudentWithAccess, db: DB) -> CheckResult:
    """Grade the answers and remember them (the best result counts)."""
    result = cp.check_block(db, student, lesson_id, block_id, data.answers)
    db.commit()
    return result


@router.post("/course-lessons/{lesson_id}/plays/{block_id}", response_model=PlayOut)
def play(lesson_id: int, block_id: int, student: StudentWithAccess, db: DB) -> PlayOut:
    plays, limit = cp.count_play(db, student, lesson_id, block_id)
    db.commit()
    return PlayOut(plays=plays, max_plays=limit)


@router.post("/course-lessons/{lesson_id}/complete", response_model=StudentLessonView)
def complete(lesson_id: int, student: StudentWithAccess, db: DB) -> StudentLessonView:
    """Finish the lesson once all its exercises are checked (repeating it changes nothing)."""
    first = cp.complete_lesson(db, student, lesson_id)
    awards = Awards()
    if first:
        les, _ = cp.lesson_access(db, student, lesson_id)
        awards = gamification.on_lesson_completed(db, student, les)
    db.commit()
    view = cp.lesson_view(db, student, lesson_id)
    view.awards = awards
    return view


@router.get("/course-progress", response_model=CourseProgressOut)
def my_progress(student: StudentWithAccess, db: DB) -> CourseProgressOut:
    return cp.course_progress(db, student)

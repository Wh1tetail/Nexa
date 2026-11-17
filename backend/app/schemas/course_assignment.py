from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EnglishLevel
from app.schemas.course import CheckResult, LessonView

LessonState = Literal["not_started", "in_progress", "completed"]
Scope = Literal["level", "module"]


# ---------- teacher ----------

class AssignIn(BaseModel):
    course_id: int
    level_id: int | None = None  # a whole level ...
    module_id: int | None = None  # ... or one module
    student_ids: list[int] = Field(default_factory=list, max_length=500)
    group_ids: list[int] = Field(default_factory=list, max_length=100)
    starts_at: datetime | None = None  # default: now
    due_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self):
        if (self.level_id is None) == (self.module_id is None):
            raise ValueError("Выберите уровень или модуль")
        if not self.student_ids and not self.group_ids:
            raise ValueError("Выберите учеников или группы")
        if self.due_at and self.starts_at and self.due_at <= self.starts_at:
            raise ValueError("Срок должен быть позже даты начала")
        return self


class AssignResult(BaseModel):
    assignment_ids: list[int]
    assigned: int  # students who got it now
    skipped: int  # already had this part of the course from this teacher


class AssignmentUpdate(BaseModel):
    starts_at: datetime | None = None
    due_at: datetime | None = None
    clear_due: bool = False


class StudentIdsIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=500)


class AssignmentItem(BaseModel):
    id: int
    course_id: int
    course_title: str
    scope: Scope
    scope_title: str
    level: EnglishLevel
    group_id: int | None
    group_name: str | None
    students_count: int  # active
    starts_at: datetime
    due_at: datetime | None
    removed_at: datetime | None
    created_at: datetime
    lessons_total: int
    avg_percent: int | None  # mean completion of the active students
    completed_count: int  # students who finished every lesson


class AssignmentStudentRow(BaseModel):
    student_id: int
    full_name: str
    removed_at: datetime | None
    lessons_completed: int
    lessons_total: int
    percent: int
    avg_score: int | None  # mean exercise result in these lessons, %
    last_activity: datetime | None


class AssignmentDetail(AssignmentItem):
    students: list[AssignmentStudentRow]


class StudentProgressRow(BaseModel):
    """One student across the teacher's course assignments."""
    student_id: int
    full_name: str
    english_level: EnglishLevel
    assignments: int
    lessons_completed: int
    lessons_total: int
    percent: int
    avg_score: int | None
    last_activity: datetime | None


# ---------- student ----------

class StudentLessonItem(BaseModel):
    id: int
    title: str
    duration_minutes: int | None
    status: LessonState
    score_percent: int | None
    completed_at: datetime | None


class StudentModule(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    lessons: list[StudentLessonItem]


class StudentCourseItem(BaseModel):
    assignment_id: int
    course_id: int
    course_title: str
    course_description: str | None
    scope: Scope
    scope_title: str
    level: EnglishLevel
    teacher_name: str | None
    starts_at: datetime
    due_at: datetime | None
    started: bool  # starts_at has come
    overdue: bool
    lessons_total: int
    lessons_completed: int
    percent: int
    next_lesson_id: int | None  # first unfinished lesson


class StudentCourseDetail(StudentCourseItem):
    modules: list[StudentModule]


class StudentLessonRow(StudentLessonItem):
    """A lesson in "My lessons" (all assigned lessons)."""
    assignment_id: int
    course_title: str
    module_title: str
    level: EnglishLevel


class BlockState(BaseModel):
    block_id: int
    answers: dict[int, list[str]]
    result: CheckResult | None  # the last check (with answers revealed)
    attempts: int
    best_percent: int | None


class StudentLessonView(BaseModel):
    lesson: LessonView  # path.prev_id / next_id follow the assignment
    assignment_id: int
    status: LessonState
    completed_at: datetime | None
    score_percent: int | None
    exercises_total: int
    exercises_done: int
    blocks: list[BlockState]
    plays: dict[int, int]


class PlayOut(BaseModel):
    plays: int
    max_plays: int | None


class CourseProgressItem(BaseModel):
    """Progress in one level of one course (the assigned lessons of it)."""
    course_id: int
    course_title: str
    level: EnglishLevel
    level_title: str
    lessons_total: int
    lessons_completed: int
    percent: int
    modules_total: int
    modules_completed: int
    avg_score: int | None
    modules: list[StudentModule]  # the course map


class CourseProgressOut(BaseModel):
    english_level: EnglishLevel
    lessons_completed: int
    lessons_remaining: int
    modules_completed: int
    exercises_done: int
    avg_score: int | None  # mean result of checked exercises, %
    items: list[CourseProgressItem]

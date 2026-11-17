from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EnglishLevel, LessonBlockType
from app.schemas.homework import AttachmentOut
from app.schemas.test import QuestionIn, QuestionOut
from app.services import lesson_blocks

LEVEL_TITLES = {
    EnglishLevel.A1: "A1 Beginner",
    EnglishLevel.A2: "A2 Elementary",
    EnglishLevel.B1: "B1 Intermediate",
    EnglishLevel.B2: "B2 Upper-Intermediate",
    EnglishLevel.C1: "C1 Advanced",
    EnglishLevel.C2: "C2 Proficiency",
}


def _clean(s: str | None) -> str | None:
    return (s or "").strip() or None


# ---------- input ----------

class CourseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    published: bool = False
    # levels created with the course (each gets its standard title)
    levels: list[EnglishLevel] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _norm(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Введите название")
        self.description = _clean(self.description)
        self.levels = list(dict.fromkeys(self.levels))
        return self


class LevelIn(BaseModel):
    level: EnglishLevel
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class LevelUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    position: int | None = Field(default=None, ge=0, le=1000)


class ModuleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class ModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    position: int | None = Field(default=None, ge=0, le=1000)
    level_id: int | None = None  # move to another level of the same course


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class LessonUpdate(BaseModel):
    """Quick changes from the course page (the builder saves the whole lesson with PUT)."""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    published: bool | None = None
    position: int | None = Field(default=None, ge=0, le=1000)
    module_id: int | None = None  # move to another module of the same course


class CopyRequest(BaseModel):
    """Where the copy goes: a module (for a lesson) or a level (for a module); default: next to the original."""
    target_id: int | None = None


class BlockIn(BaseModel):
    id: int | None = None  # an existing block of this lesson keeps its id
    type: LessonBlockType
    title: str | None = Field(default=None, max_length=200)
    content: dict[str, Any] = Field(default_factory=dict)
    questions: list[QuestionIn] = Field(default_factory=list, max_length=lesson_blocks.MAX_QUESTIONS)

    @model_validator(mode="after")
    def _validate(self):
        self.title = _clean(self.title)
        questions = [q.model_dump(mode="json") for q in self.questions]
        self.content = lesson_blocks.normalize(self.type, self.content, questions)
        return self


class LessonIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    published: bool = False
    blocks: list[BlockIn] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _norm(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Введите название")
        self.description = _clean(self.description)
        if self.published and not self.blocks:
            raise ValueError("Добавьте в урок хотя бы один блок, прежде чем публиковать")
        return self


class CheckRequest(BaseModel):
    # question index in the block -> answer (option ids / gap texts / chosen pairs)
    answers: dict[int, list[str]] = Field(default_factory=dict)


# ---------- output ----------

class LessonSummary(BaseModel):
    id: int
    title: str
    published: bool
    position: int
    duration_minutes: int | None
    blocks_count: int
    updated_at: datetime | None


class ModuleOut(BaseModel):
    id: int
    level_id: int
    title: str
    description: str | None
    position: int
    lessons: list[LessonSummary]


class LevelOut(BaseModel):
    id: int
    course_id: int
    level: EnglishLevel
    title: str
    description: str | None
    position: int
    modules: list[ModuleOut]


class CourseItem(BaseModel):
    id: int
    title: str
    description: str | None
    published: bool
    author_name: str | None
    level_codes: list[EnglishLevel]
    modules_count: int
    lessons_count: int  # visible to the viewer (teachers: published only)
    draft_lessons_count: int  # 0 for teachers
    created_at: datetime
    updated_at: datetime | None


class CourseDetail(CourseItem):
    levels: list[LevelOut]


class LessonPath(BaseModel):
    """Where a lesson sits; prev/next follow the course order (visible lessons only)."""
    course_id: int
    course_title: str
    course_published: bool
    level_id: int
    level: EnglishLevel
    level_title: str
    module_id: int
    module_title: str
    prev_id: int | None = None
    next_id: int | None = None


class BlockEdit(BaseModel):
    id: int
    position: int
    type: LessonBlockType
    title: str | None
    content: dict[str, Any]  # without questions
    questions: list[dict[str, Any]]  # QuestionIn shape, with answers


class BlockView(BaseModel):
    id: int
    position: int
    type: LessonBlockType
    title: str | None
    content: dict[str, Any]  # without questions
    questions: list[QuestionOut]  # no answers


class LessonDetail(BaseModel):
    id: int
    title: str
    description: str | None
    duration_minutes: int | None
    published: bool
    updated_at: datetime | None
    path: LessonPath
    files: list[AttachmentOut]
    blocks: list[BlockEdit]


class LessonView(BaseModel):
    id: int
    title: str
    description: str | None
    duration_minutes: int | None
    published: bool
    path: LessonPath
    files: list[AttachmentOut]
    blocks: list[BlockView]


class QuestionResult(BaseModel):
    question_id: int
    answer: list[str]
    is_correct: bool
    points_awarded: float
    max_points: int


class CheckResult(BaseModel):
    results: list[QuestionResult]
    questions: list[QuestionOut]  # with the correct answers and explanations
    score: float
    max_score: int

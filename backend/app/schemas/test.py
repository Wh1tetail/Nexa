from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AttemptStatus, QuestionType
from app.schemas.homework import AttachmentOut


class OptionIn(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=1000)


class QuestionIn(BaseModel):
    type: QuestionType
    text: str = Field(min_length=1, max_length=5000)
    options: list[OptionIn] = []
    correct_answer: list[str] = []
    points: int = Field(default=1, gt=0, le=100)
    explanation: str | None = Field(default=None, max_length=5000)
    # ids of the test's files shown with this question (picture, audio)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _validate(self):
        t = self.type
        if t == QuestionType.TRUE_FALSE:
            # Normalize options for true/false
            self.options = [OptionIn(id="true", text="True"), OptionIn(id="false", text="False")]
            if len(self.correct_answer) != 1 or self.correct_answer[0] not in ("true", "false"):
                raise ValueError("Для вопроса True/False укажите правильный ответ")
        elif t in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
            if len(self.options) < 2:
                raise ValueError("Добавьте минимум два варианта ответа")
            ids = [o.id for o in self.options]
            if len(set(ids)) != len(ids):
                raise ValueError("Идентификаторы вариантов должны быть уникальными")
            if not self.correct_answer or not set(self.correct_answer) <= set(ids):
                raise ValueError("Отметьте правильный ответ")
            if t == QuestionType.SINGLE_CHOICE and len(self.correct_answer) != 1:
                raise ValueError("В вопросе с одним ответом должен быть ровно один правильный вариант")
        elif t == QuestionType.SHORT_ANSWER:
            self.options = []
            self.correct_answer = [a.strip() for a in self.correct_answer if a.strip()]
        self.explanation = (self.explanation or "").strip() or None
        self.attachment_ids = list(dict.fromkeys(self.attachment_ids))
        return self


class TestSettings(BaseModel):
    available_from: datetime | None = None
    shuffle_questions: bool = False
    shuffle_options: bool = False
    show_correct_answers: bool = True
    passing_percent: int | None = Field(default=None, ge=1, le=100)
    # attempts per student; the best result counts
    max_attempts: int = Field(default=1, ge=1, le=10)


class TestCreate(TestSettings):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    time_limit_minutes: int | None = Field(default=None, gt=0, le=600)
    due_at: datetime | None = None
    questions: list[QuestionIn] = Field(min_length=1, max_length=200)
    student_ids: list[int] = []
    group_ids: list[int] = []

    @model_validator(mode="after")
    def _dates(self):
        if self.available_from and self.due_at and self.available_from >= self.due_at:
            raise ValueError("Дата открытия теста должна быть раньше срока сдачи")
        return self


class TestUpdate(TestCreate):
    pass


class AssignRequest(BaseModel):
    student_ids: list[int] = []
    group_ids: list[int] = []


class QuestionOut(BaseModel):
    id: int
    position: int
    type: QuestionType
    text: str
    options: list[OptionIn]
    correct_answer: list[str] | None = None  # hidden for students before grading
    points: int
    explanation: str | None = None  # same visibility as correct_answer
    attachment_ids: list[int] = []


class TestListItem(TestSettings):
    id: int
    title: str
    description: str | None
    time_limit_minutes: int | None
    due_at: datetime | None
    created_at: datetime
    files_count: int = 0
    questions_count: int
    assigned_count: int
    completed_count: int
    pending_review_count: int


class TestDetail(TestSettings):
    id: int
    title: str
    description: str | None
    time_limit_minutes: int | None
    due_at: datetime | None
    created_at: datetime
    questions: list[QuestionOut]
    student_ids: list[int]
    has_attempts: bool
    files: list[AttachmentOut] = []


class AnswerOut(BaseModel):
    id: int
    question_id: int
    answer: list[str]
    is_correct: bool | None
    points_awarded: float | None
    teacher_comment: str | None


class AttemptSummary(BaseModel):
    id: int
    test_id: int
    test_title: str
    student_id: int
    student_name: str
    number: int = 1  # attempt No. for this student and test
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    score: float | None
    max_score: float
    percent: int | None
    passed: bool | None = None  # None: not graded yet or no passing score set


class AttemptDetail(AttemptSummary):
    time_limit_minutes: int | None
    deadline_at: datetime | None
    passing_percent: int | None = None
    show_correct_answers: bool = True
    # questions come in the order the student sees them (may be shuffled)
    questions: list[QuestionOut]
    answers: list[AnswerOut]
    files: list[AttachmentOut] = []


class AnswerIn(BaseModel):
    question_id: int
    answer: list[str] = Field(default_factory=list, max_length=50)


class SubmitAttempt(BaseModel):
    answers: list[AnswerIn]


class SaveProgress(SubmitAttempt):
    pass


class GradeAnswer(BaseModel):
    answer_id: int
    points_awarded: float = Field(ge=0)
    teacher_comment: str | None = Field(default=None, max_length=2000)


class GradeRequest(BaseModel):
    answers: list[GradeAnswer]


class StudentTestItem(BaseModel):
    test_id: int
    title: str
    description: str | None
    time_limit_minutes: int | None
    due_at: datetime | None
    available_from: datetime | None = None
    is_available: bool = True  # False until available_from
    passing_percent: int | None = None
    passed: bool | None = None
    questions_count: int
    is_overdue: bool
    attempt_id: int | None
    attempt_status: AttemptStatus | None
    score: float | None
    max_score: float | None
    percent: int | None
    submitted_at: datetime | None
    # attempts: the fields above describe the latest one
    attempts_used: int = 0
    attempts_allowed: int = 1
    can_retake: bool = False  # another attempt can be started now
    best_percent: int | None = None

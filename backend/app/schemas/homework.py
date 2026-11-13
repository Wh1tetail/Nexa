from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SubmissionStatus
from app.schemas.common import ORMModel


class AttachmentOut(ORMModel):
    id: int
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class HomeworkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    due_at: datetime | None = None
    max_grade: int = Field(default=10, gt=0, le=100)
    student_ids: list[int] = []
    group_ids: list[int] = []

    @model_validator(mode="after")
    def _recipients(self):
        if not self.student_ids and not self.group_ids:
            raise ValueError("Выберите хотя бы одного ученика или группу")
        return self


class HomeworkUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    due_at: datetime | None = None
    max_grade: int | None = Field(default=None, gt=0, le=100)
    add_student_ids: list[int] = []
    add_group_ids: list[int] = []


class SubmissionCounts(BaseModel):
    total: int = 0
    new: int = 0
    in_progress: int = 0
    submitted: int = 0
    reviewed: int = 0
    needs_revision: int = 0


class HomeworkListItem(BaseModel):
    id: int
    title: str
    due_at: datetime | None
    created_at: datetime
    max_grade: int
    counts: SubmissionCounts


class SubmissionOut(BaseModel):
    id: int
    homework_id: int
    student_id: int
    student_name: str
    status: SubmissionStatus
    student_comment: str | None
    teacher_comment: str | None
    grade: int | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    files: list[AttachmentOut]


class HomeworkDetail(BaseModel):
    id: int
    title: str
    description: str | None
    due_at: datetime | None
    max_grade: int
    created_at: datetime
    attachments: list[AttachmentOut]
    submissions: list[SubmissionOut]


class ReviewRequest(BaseModel):
    status: SubmissionStatus = SubmissionStatus.REVIEWED
    grade: int | None = Field(default=None, ge=0, le=100)
    teacher_comment: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _status(self):
        if self.status not in (
            SubmissionStatus.REVIEWED,
            SubmissionStatus.NEEDS_REVISION,
            SubmissionStatus.SUBMITTED,
            SubmissionStatus.IN_PROGRESS,
            SubmissionStatus.NEW,
        ):
            raise ValueError("Недопустимый статус")
        return self


# ---- student side ----

class StudentHomework(BaseModel):
    """A homework as seen by the student = their submission + homework info."""
    submission_id: int
    homework_id: int
    title: str
    description: str | None
    due_at: datetime | None
    max_grade: int
    teacher_name: str
    status: SubmissionStatus
    is_overdue: bool
    student_comment: str | None
    teacher_comment: str | None
    grade: int | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime
    attachments: list[AttachmentOut]
    files: list[AttachmentOut]


class SubmitRequest(BaseModel):
    student_comment: str | None = Field(default=None, max_length=5000)

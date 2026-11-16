from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import AttendanceStatus, LessonStatus


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str | None = None
    starts_at: datetime
    duration_minutes: int = Field(default=60, gt=0, le=600)
    meeting_url: str | None = Field(default=None, max_length=500)
    group_id: int | None = None
    student_ids: list[int] = []
    # Create the lesson plus N weekly copies (same weekday/time and participants).
    repeat_weeks: int = Field(default=0, ge=0, le=52)


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = None
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=600)
    meeting_url: str | None = Field(default=None, max_length=500)
    status: LessonStatus | None = None
    student_ids: list[int] | None = None


class SeriesExtend(BaseModel):
    weeks: int = Field(ge=1, le=52)


class AttendanceRow(BaseModel):
    id: int
    student_id: int
    student_name: str
    status: AttendanceStatus | None
    comment: str | None


class RemovedParticipant(BaseModel):
    """Taken off the lesson; the attendance mark is kept and returns on re-adding."""
    student_id: int
    student_name: str
    status: AttendanceStatus | None
    removed_at: datetime


class ParticipantsChange(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=200)


class LessonOut(BaseModel):
    id: int
    title: str
    topic: str | None
    starts_at: datetime
    duration_minutes: int
    meeting_url: str | None
    status: LessonStatus
    group_id: int | None
    group_name: str | None
    series_id: str | None = None
    series_position: int | None = None  # 1-based index of this lesson in its series
    series_total: int | None = None
    attendance: list[AttendanceRow]
    removed: list[RemovedParticipant] = []  # only in the single-lesson views


class AttendanceMark(BaseModel):
    student_id: int
    status: AttendanceStatus | None
    comment: str | None = Field(default=None, max_length=1000)


class AttendanceBulk(BaseModel):
    marks: list[AttendanceMark]
    complete_lesson: bool = True


class AttendanceRecord(BaseModel):
    """Flat attendance record for tables & history."""
    id: int
    lesson_id: int
    lesson_title: str
    starts_at: datetime
    lesson_status: LessonStatus
    student_id: int
    student_name: str
    status: AttendanceStatus | None
    comment: str | None


class AttendanceStats(BaseModel):
    student_id: int
    student_name: str
    present: int
    late: int
    absent: int
    excused: int
    upcoming: int
    total_marked: int
    attendance_rate: int  # % (present + late) / marked


class MyLesson(BaseModel):
    id: int
    title: str
    topic: str | None
    starts_at: datetime
    duration_minutes: int
    meeting_url: str | None
    lesson_status: LessonStatus
    status: AttendanceStatus | None
    comment: str | None


class StudentAttendanceSummary(BaseModel):
    stats: AttendanceStats
    lessons: list[MyLesson]


class DateRange(BaseModel):
    date_from: date | None = None
    date_to: date | None = None

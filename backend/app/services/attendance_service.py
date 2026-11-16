from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.models import Attendance, Lesson, StudentProfile
from app.models.enums import AttendanceStatus, LessonStatus
from app.schemas.lesson import AttendanceRecord, AttendanceStats, MyLesson
from app.services import subscription_service as subs

CHARGEABLE = {AttendanceStatus.PRESENT, AttendanceStatus.LATE}


def apply_mark(
    db: Session, row: Attendance, status: AttendanceStatus | None, comment: str | None
) -> None:
    """Set attendance status and keep subscription lesson counters in sync:
    present/late deducts one lesson, switching away refunds it."""
    was_charged = row.charged_subscription_id is not None
    should_charge = status in CHARGEABLE
    if was_charged and not should_charge:
        subs.refund_lesson(db, row.charged_subscription_id)
        row.charged_subscription_id = None
    elif should_charge and not was_charged:
        sub = subs.charge_lesson(db, row.student_id, row.lesson.starts_at.date())
        row.charged_subscription_id = sub.id if sub else None
    row.status = status
    row.comment = comment
    row.marked_at = datetime.now(UTC) if status else None


def records_query(
    teacher_id: int | None = None,
    student_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select[tuple[Attendance]]:
    q = (
        select(Attendance)
        .join(Attendance.lesson)
        .options(
            joinedload(Attendance.lesson),
            joinedload(Attendance.student).joinedload(StudentProfile.user),
        )
        .where(Attendance.removed_at.is_(None))  # taken off the lesson: kept, but not counted
    )
    if teacher_id is not None:
        q = q.where(Lesson.teacher_id == teacher_id)
    if student_id is not None:
        q = q.where(Attendance.student_id == student_id)
    if date_from is not None:
        q = q.where(Lesson.starts_at >= date_from)
    if date_to is not None:
        q = q.where(Lesson.starts_at < date_to)
    return q.order_by(Lesson.starts_at.desc())


def to_record(a: Attendance) -> AttendanceRecord:
    return AttendanceRecord(
        id=a.id,
        lesson_id=a.lesson_id,
        lesson_title=a.lesson.title,
        starts_at=a.lesson.starts_at,
        lesson_status=a.lesson.status,
        student_id=a.student_id,
        student_name=a.student.user.full_name,
        status=a.status,
        comment=a.comment,
    )


def build_stats(student: StudentProfile, rows: list[Attendance]) -> AttendanceStats:
    now = datetime.now(UTC)
    counts = {s: 0 for s in AttendanceStatus}
    upcoming = 0
    for r in rows:
        if r.lesson.status == LessonStatus.CANCELLED:
            continue
        if r.status:
            counts[r.status] += 1
        elif r.lesson.starts_at > now:
            upcoming += 1
    marked = sum(counts.values())
    attended = counts[AttendanceStatus.PRESENT] + counts[AttendanceStatus.LATE]
    return AttendanceStats(
        student_id=student.id,
        student_name=student.user.full_name,
        present=counts[AttendanceStatus.PRESENT],
        late=counts[AttendanceStatus.LATE],
        absent=counts[AttendanceStatus.ABSENT],
        excused=counts[AttendanceStatus.EXCUSED],
        upcoming=upcoming,
        total_marked=marked,
        attendance_rate=round(attended * 100 / marked) if marked else 0,
    )


def student_stats(db: Session, student: StudentProfile) -> AttendanceStats:
    rows = db.scalars(records_query(student_id=student.id)).unique().all()
    return build_stats(student, list(rows))


def to_my_lesson(a: Attendance) -> MyLesson:
    return MyLesson(
        id=a.lesson.id,
        title=a.lesson.title,
        topic=a.lesson.topic,
        starts_at=a.lesson.starts_at,
        duration_minutes=a.lesson.duration_minutes,
        meeting_url=a.lesson.meeting_url,
        lesson_status=a.lesson.status,
        status=a.status,
        comment=a.comment,
    )

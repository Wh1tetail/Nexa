import csv
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import (
    DB,
    CurrentTeacher,
    get_owned_group,
    get_owned_student,
    get_owned_students,
)
from app.core.exceptions import BadRequest, NotFound
from app.core.i18n import M, tr
from app.core.timezones import add_weeks_local, fmt_local, get_zone, shift_wall_clock, to_local, wall_clock_delta
from app.models import Attendance, Lesson, StudentProfile, TeacherProfile, User
from app.models.enums import LessonStatus, NotificationType
from app.repositories import student_repository as repo
from app.schemas.lesson import (
    AttendanceBulk,
    AttendanceRecord,
    AttendanceRow,
    AttendanceStats,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    SeriesExtend,
)
from app.services import attendance_service as att_svc
from app.services.notification_service import notify

router = APIRouter(tags=["lessons & attendance"])


def _day_start(d: date | None) -> datetime | None:
    return datetime.combine(d, time.min, tzinfo=UTC) if d else None


def _day_end(d: date | None) -> datetime | None:
    return datetime.combine(d + timedelta(days=1), time.min, tzinfo=UTC) if d else None


def to_out(lesson: Lesson) -> LessonOut:
    return LessonOut(
        id=lesson.id,
        title=lesson.title,
        topic=lesson.topic,
        starts_at=lesson.starts_at,
        duration_minutes=lesson.duration_minutes,
        meeting_url=lesson.meeting_url,
        status=lesson.status,
        group_id=lesson.group_id,
        group_name=lesson.group.name if lesson.group else None,
        series_id=lesson.series_id,
        attendance=sorted(
            (
                AttendanceRow(
                    id=a.id,
                    student_id=a.student_id,
                    student_name=a.student.user.full_name,
                    status=a.status,
                    comment=a.comment,
                )
                for a in lesson.attendance
            ),
            key=lambda r: r.student_name,
        ),
    )


def _fill_series(db: Session, outs: list[LessonOut]) -> list[LessonOut]:
    """Set series_position / series_total ("3 of 8") with one query."""
    ids = {o.series_id for o in outs if o.series_id}
    if not ids:
        return outs
    rows = db.execute(
        select(Lesson.series_id, Lesson.id).where(Lesson.series_id.in_(ids)).order_by(Lesson.starts_at, Lesson.id)
    ).all()
    order: dict[str, list[int]] = {}
    for sid, lid in rows:
        order.setdefault(sid, []).append(lid)
    for o in outs:
        if o.series_id in order:
            seq = order[o.series_id]
            o.series_total = len(seq)
            o.series_position = seq.index(o.id) + 1 if o.id in seq else None
    return outs


def _one(db: Session, lesson: Lesson) -> LessonOut:
    return _fill_series(db, [to_out(lesson)])[0]


def _get_owned_lesson(db: Session, teacher: TeacherProfile, lesson_id: int) -> Lesson:
    lesson = db.scalar(
        select(Lesson)
        .options(
            selectinload(Lesson.attendance).joinedload(Attendance.student).joinedload(StudentProfile.user),
            joinedload(Lesson.group),
        )
        .where(Lesson.id == lesson_id)
    )
    if lesson is None or lesson.teacher_id != teacher.id:
        raise NotFound("Занятие не найдено")
    return lesson


def _sync_participants(db: Session, lesson: Lesson, students: list[StudentProfile]) -> list[StudentProfile]:
    """Add missing participants; remove unmarked ones that were deselected."""
    wanted = {s.id for s in students}
    current = {a.student_id: a for a in lesson.attendance}
    for sid, row in list(current.items()):
        if sid not in wanted:
            if row.status is not None:
                raise BadRequest("Нельзя убрать ученика с уже отмеченной посещаемостью")
            lesson.attendance.remove(row)
    added = []
    for s in students:
        if s.id not in current:
            lesson.attendance.append(Attendance(student_id=s.id))
            added.append(s)
    return added


@router.get("/lessons", response_model=list[LessonOut])
def list_lessons(
    teacher: CurrentTeacher,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    student_id: int | None = None,
    group_id: int | None = None,
    status_filter: LessonStatus | None = None,
) -> list[LessonOut]:
    q = (
        select(Lesson)
        .options(
            selectinload(Lesson.attendance).joinedload(Attendance.student).joinedload(StudentProfile.user),
            joinedload(Lesson.group),
        )
        .where(Lesson.teacher_id == teacher.id)
        .order_by(Lesson.starts_at)
    )
    if date_from:
        q = q.where(Lesson.starts_at >= _day_start(date_from))
    if date_to:
        q = q.where(Lesson.starts_at < _day_end(date_to))
    if group_id:
        q = q.where(Lesson.group_id == group_id)
    if student_id:
        q = q.where(Lesson.id.in_(select(Attendance.lesson_id).where(Attendance.student_id == student_id)))
    if status_filter:
        q = q.where(Lesson.status == status_filter)
    return _fill_series(db, [to_out(lesson) for lesson in db.scalars(q).unique().all()])


@router.post("/lessons", response_model=LessonOut, status_code=status.HTTP_201_CREATED)
def create_lesson(data: LessonCreate, teacher: CurrentTeacher, db: DB) -> LessonOut:
    """Create a lesson; with repeat_weeks > 0 also creates weekly copies (a series)."""
    students = {s.id: s for s in get_owned_students(db, teacher, data.student_ids)}
    if data.group_id:
        for s in get_owned_group(db, teacher, data.group_id).students:
            students[s.id] = s
    if not students:
        raise BadRequest("Добавьте учеников или группу")
    series_id = uuid.uuid4().hex if data.repeat_weeks else None
    tz = get_zone(teacher.user.timezone)
    first: Lesson | None = None
    for week in range(data.repeat_weeks + 1):
        lesson = Lesson(
            teacher_id=teacher.id,
            group_id=data.group_id,
            title=data.title,
            topic=data.topic,
            starts_at=add_weeks_local(data.starts_at, week, tz),  # same local time every week, DST-safe
            duration_minutes=data.duration_minutes,
            meeting_url=data.meeting_url,
            series_id=series_id,
        )
        db.add(lesson)
        _sync_participants(db, lesson, list(students.values()))
        first = first or lesson
    db.commit()
    return _one(db, _get_owned_lesson(db, teacher, first.id))


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, teacher: CurrentTeacher, db: DB) -> LessonOut:
    return _one(db, _get_owned_lesson(db, teacher, lesson_id))


def _following_in_series(db: Session, teacher: TeacherProfile, lesson: Lesson) -> list[Lesson]:
    """Later, still-scheduled lessons of the same series."""
    if not lesson.series_id:
        return []
    return list(
        db.scalars(
            select(Lesson)
            .options(
                selectinload(Lesson.attendance).joinedload(Attendance.student).joinedload(StudentProfile.user),
            )
            .where(
                Lesson.series_id == lesson.series_id,
                Lesson.teacher_id == teacher.id,
                Lesson.starts_at > lesson.starts_at,
                Lesson.status == LessonStatus.SCHEDULED,
                Lesson.id != lesson.id,
            )
            .order_by(Lesson.starts_at)
        ).all()
    )


def _notify_schedule_change(db: Session, lesson: Lesson, rescheduled: list[Lesson]) -> None:
    """One notification per affected student, with times in that student's time zone."""
    db.flush()
    student_ids = {a.student_id for t in rescheduled for a in t.attendance}
    rows = db.execute(
        select(User.id, User.timezone)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(StudentProfile.id.in_(student_ids))
    ).all()
    by_zone: dict[str, set[int]] = {}
    for user_id, tz_name in rows:
        by_zone.setdefault(get_zone(tz_name).key, set()).add(user_id)
    cancelled = lesson.status == LessonStatus.CANCELLED
    for zone_name, user_ids in by_zone.items():
        tz = get_zone(zone_name)
        if len(rescheduled) == 1:
            title = M("Занятие отменено" if cancelled else "Занятие изменено")
            body = f"«{lesson.title}» — {fmt_local(lesson.starts_at, tz)}"
        else:
            title = M("Занятия отменены" if cancelled else "Занятия изменены")
            first_day = to_local(lesson.starts_at, tz).strftime("%d.%m.%Y")
            body = M("«{title}»: занятий — {n}, начиная с {day}", title=lesson.title, n=len(rescheduled), day=first_day)
        notify(db, user_ids, NotificationType.LESSON_CHANGED, title, body, "/student/attendance")


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(
    lesson_id: int,
    data: LessonUpdate,
    teacher: CurrentTeacher,
    db: DB,
    scope: Literal["one", "following"] = "one",
) -> LessonOut:
    """scope=following applies the change to this lesson and every later
    *scheduled* lesson of its series. A new start time is applied as a shift
    on the teacher's local clock (18:00 -> 19:30 moves every following lesson
    to 19:30 local time, keeping weekdays, also across DST changes);
    completed and cancelled lessons of the series are left untouched."""
    lesson = _get_owned_lesson(db, teacher, lesson_id)
    payload = data.model_dump(exclude_unset=True)
    student_ids = payload.pop("student_ids", None)
    students = get_owned_students(db, teacher, student_ids) if student_ids is not None else None
    tz = get_zone(teacher.user.timezone)
    shift = wall_clock_delta(lesson.starts_at, payload["starts_at"], tz) if payload.get("starts_at") else None

    targets = [lesson] + (_following_in_series(db, teacher, lesson) if scope == "following" else [])
    rescheduled: list[Lesson] = []
    for target in targets:
        changes = {}
        for k, v in payload.items():
            if k == "starts_at":
                if v is not None:
                    changes[k] = v if target is lesson else shift_wall_clock(target.starts_at, shift, tz)
            elif v is not None or k in ("topic", "meeting_url"):
                changes[k] = v
        if any(k in changes and changes[k] != getattr(target, k) for k in ("starts_at", "status", "meeting_url")):
            rescheduled.append(target)
        for k, v in changes.items():
            setattr(target, k, v)
        if students is not None:
            _sync_participants(db, target, students)

    if rescheduled:
        _notify_schedule_change(db, lesson, rescheduled)
    db.commit()
    return _one(db, _get_owned_lesson(db, teacher, lesson_id))


@router.post("/lessons/{lesson_id}/series/extend", response_model=LessonOut)
def extend_series(lesson_id: int, data: SeriesExtend, teacher: CurrentTeacher, db: DB) -> LessonOut:
    """Add N more weekly lessons after the last lesson of the series.
    A single lesson becomes a series."""
    lesson = _get_owned_lesson(db, teacher, lesson_id)
    if lesson.series_id is None:
        lesson.series_id = uuid.uuid4().hex
        last = lesson
    else:
        last = db.scalars(
            select(Lesson)
            .options(selectinload(Lesson.attendance).joinedload(Attendance.student))
            .where(Lesson.series_id == lesson.series_id, Lesson.teacher_id == teacher.id)
            .order_by(Lesson.starts_at.desc())
            .limit(1)
        ).one()
    participants = [a.student for a in last.attendance]
    tz = get_zone(teacher.user.timezone)
    for week in range(1, data.weeks + 1):
        copy = Lesson(
            teacher_id=teacher.id,
            group_id=last.group_id,
            title=last.title,
            topic=last.topic,
            starts_at=add_weeks_local(last.starts_at, week, tz),
            duration_minutes=last.duration_minutes,
            meeting_url=last.meeting_url,
            series_id=lesson.series_id,
        )
        db.add(copy)
        _sync_participants(db, copy, participants)
    db.commit()
    return _one(db, _get_owned_lesson(db, teacher, lesson_id))


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(
    lesson_id: int,
    teacher: CurrentTeacher,
    db: DB,
    scope: Literal["one", "following"] = "one",
) -> Response:
    """scope=following deletes this lesson and all later lessons of the same series
    that have no attendance marks yet."""
    lesson = _get_owned_lesson(db, teacher, lesson_id)
    targets = [lesson]
    if scope == "following" and lesson.series_id:
        later = db.scalars(
            select(Lesson)
            .options(selectinload(Lesson.attendance))
            .where(
                Lesson.series_id == lesson.series_id,
                Lesson.teacher_id == teacher.id,
                Lesson.starts_at > lesson.starts_at,
            )
        ).all()
        targets += [x for x in later if not any(a.status for a in x.attendance)]
    for target in targets:
        for row in target.attendance:
            att_svc.apply_mark(db, row, None, None)  # refund charged lessons
        db.delete(target)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/lessons/{lesson_id}/attendance", response_model=LessonOut)
def mark_attendance(lesson_id: int, data: AttendanceBulk, teacher: CurrentTeacher, db: DB) -> LessonOut:
    lesson = _get_owned_lesson(db, teacher, lesson_id)
    if lesson.status == LessonStatus.CANCELLED:
        raise BadRequest("Занятие отменено")
    rows = {a.student_id: a for a in lesson.attendance}
    for mark in data.marks:
        row = rows.get(mark.student_id)
        if row is None:
            raise BadRequest("Ученик не участвует в этом занятии")
        att_svc.apply_mark(db, row, mark.status, mark.comment)
    if data.complete_lesson and all(r.status for r in lesson.attendance):
        lesson.status = LessonStatus.COMPLETED
    db.commit()
    return _one(db, _get_owned_lesson(db, teacher, lesson_id))


@router.get("/attendance", response_model=list[AttendanceRecord])
def attendance_records(
    teacher: CurrentTeacher,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    student_id: int | None = None,
) -> list[AttendanceRecord]:
    if student_id:
        get_owned_student(db, teacher, student_id)
    q = att_svc.records_query(teacher.id, student_id, _day_start(date_from), _day_end(date_to))
    return [att_svc.to_record(a) for a in db.scalars(q).unique().all()]


@router.get("/attendance/stats", response_model=list[AttendanceStats])
def attendance_stats(
    teacher: CurrentTeacher,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    student_id: int | None = None,
) -> list[AttendanceStats]:
    students = repo.list_for_teacher(db, teacher.id)
    if student_id:
        students = [s for s in students if s.id == student_id]
    q = att_svc.records_query(teacher.id, student_id, _day_start(date_from), _day_end(date_to))
    rows = db.scalars(q).unique().all()
    by_student: dict[int, list[Attendance]] = {}
    for r in rows:
        by_student.setdefault(r.student_id, []).append(r)
    return [att_svc.build_stats(s, by_student.get(s.id, [])) for s in students]


_ATTENDANCE = {"present": "Присутствовал", "absent": "Отсутствовал", "late": "Опоздал", "excused": "Уважительная причина"}
_LESSON_STATUS = {"scheduled": "Запланировано", "completed": "Проведено", "cancelled": "Отменено"}


@router.get("/attendance/export")
def export_attendance(
    teacher: CurrentTeacher,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    student_id: int | None = None,
) -> Response:
    """Attendance records as CSV (UTF-8 with BOM, ';' separator — opens correctly in Excel)."""
    if student_id:
        get_owned_student(db, teacher, student_id)
    q = att_svc.records_query(teacher.id, student_id, _day_start(date_from), _day_end(date_to))
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    tz = get_zone(teacher.user.timezone)
    # texts in the language of the request (the teacher's interface language)
    writer.writerow([tr("Дата ({tz})", tz=tz.key), tr("Время ({tz})", tz=tz.key), tr("Ученик"), tr("Занятие"),
                     tr("Статус занятия"), tr("Посещаемость"), tr("Комментарий")])
    for a in db.scalars(q).unique().all():
        st = to_local(a.lesson.starts_at, tz)
        writer.writerow([
            st.strftime("%d.%m.%Y"),
            st.strftime("%H:%M"),
            a.student.user.full_name,
            a.lesson.title,
            tr(_LESSON_STATUS[a.lesson.status.value]),
            tr(_ATTENDANCE[a.status.value]) if a.status and a.status.value in _ATTENDANCE else tr("Не отмечено"),
            a.comment or "",
        ])
    name = f"attendance_{date_from or 'all'}_{date_to or 'all'}.csv"
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )

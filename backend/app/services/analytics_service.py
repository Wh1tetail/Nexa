"""Progress analytics: per-student history and the teacher's overview.

All percentages are rounded integers. Attendance counts (present + late) over
all marked visits of non-cancelled lessons, exactly like attendance_service.
Months are calendar months in the viewer's time zone.
"""
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timezones import get_zone
from app.models import Attendance, HomeworkSubmission, Lesson, StudentProfile, TestAttempt, User
from app.models.enums import AttemptStatus, AttendanceStatus, LessonStatus, SubmissionStatus, SubscriptionStatus
from app.schemas.analytics import (
    AttendanceMonth,
    ProgressSummary,
    ScorePoint,
    StudentOverviewRow,
    StudentProgress,
    TeacherOverview,
)
from app.services import subscription_service

MONTHS = 6
LOW_ATTENDANCE = 70  # %
LOW_TESTS = 60  # %
OVERDUE_LIMIT = 2
INACTIVE_DAYS = 14
OPEN = (SubmissionStatus.NEW, SubmissionStatus.IN_PROGRESS, SubmissionStatus.NEEDS_REVISION)


def _avg(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def _pct(part: float, whole: float) -> int:
    return round(part * 100 / whole) if whole else 0


def _rate(rows: list[Attendance]) -> int | None:
    marked = [r for r in rows if r.status is not None]
    attended = sum(1 for r in marked if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
    return _pct(attended, len(marked)) if marked else None


# ---------- data loading ----------

def _test_points(db: Session, student_ids: list[int], since: datetime | None = None) -> dict[int, list[ScorePoint]]:
    q = (
        select(TestAttempt)
        .options(selectinload(TestAttempt.test))
        .where(TestAttempt.student_id.in_(student_ids), TestAttempt.status == AttemptStatus.GRADED)
        .order_by(TestAttempt.submitted_at)
    )
    if since:
        q = q.where(TestAttempt.submitted_at >= since)
    # several attempts at one test: only the best counts (the latest of equal ones)
    best: dict[tuple[int, int], TestAttempt] = {}
    for a in db.scalars(q).all():
        if not a.max_score or a.score is None:
            continue
        key = (a.student_id, a.test_id)
        if key not in best or a.score / a.max_score >= best[key].score / best[key].max_score:
            best[key] = a
    out: dict[int, list[ScorePoint]] = defaultdict(list)
    for a in sorted(best.values(), key=lambda a: a.submitted_at):
        pct = _pct(a.score, a.max_score)
        passing = a.test.passing_percent
        out[a.student_id].append(ScorePoint(
            date=a.submitted_at, title=a.test.title, percent=pct,
            passed=(pct >= passing) if passing is not None else None,
        ))
    return out


def _homework_rows(db: Session, student_ids: list[int]) -> list[HomeworkSubmission]:
    return list(db.scalars(
        select(HomeworkSubmission)
        .options(selectinload(HomeworkSubmission.homework))
        .where(HomeworkSubmission.student_id.in_(student_ids))
    ).all())


def _homework_points(rows: list[HomeworkSubmission], since: datetime | None = None) -> dict[int, list[ScorePoint]]:
    out: dict[int, list[ScorePoint]] = defaultdict(list)
    graded = [r for r in rows if r.grade is not None and r.reviewed_at and r.homework.max_grade]
    for r in sorted(graded, key=lambda r: r.reviewed_at):
        if since and r.reviewed_at < since:
            continue
        out[r.student_id].append(ScorePoint(
            date=r.reviewed_at, title=r.homework.title, percent=_pct(r.grade, r.homework.max_grade),
        ))
    return out


def _attendance_rows(db: Session, student_ids: list[int], since: datetime | None = None) -> dict[int, list[Attendance]]:
    q = (
        select(Attendance)
        .join(Lesson, Lesson.id == Attendance.lesson_id)
        .options(selectinload(Attendance.lesson))
        .where(
            Attendance.student_id.in_(student_ids),
            Attendance.removed_at.is_(None),
            Lesson.status != LessonStatus.CANCELLED,
            Lesson.starts_at <= datetime.now(UTC),
        )
    )
    if since:
        q = q.where(Lesson.starts_at >= since)
    out: dict[int, list[Attendance]] = defaultdict(list)
    for a in db.scalars(q).all():
        out[a.student_id].append(a)
    return out


# ---------- one student ----------

def _month_start(d: date) -> date:
    return d.replace(day=1)


def _months_back(today: date, n: int) -> list[date]:
    months, cur = [], _month_start(today)
    for _ in range(n):
        months.append(cur)
        cur = _month_start(cur - timedelta(days=1))
    return list(reversed(months))


def _attendance_by_month(rows: list[Attendance], viewer_tz: str | None) -> list[AttendanceMonth]:
    tz = get_zone(viewer_tz)
    today = datetime.now(UTC).astimezone(tz).date()
    buckets = {m: {s: 0 for s in AttendanceStatus} for m in _months_back(today, MONTHS)}
    for r in rows:
        if r.status is None:
            continue
        m = _month_start(r.lesson.starts_at.astimezone(tz).date())
        if m in buckets:
            buckets[m][r.status] += 1
    out = []
    for m, c in buckets.items():
        marked = sum(c.values())
        attended = c[AttendanceStatus.PRESENT] + c[AttendanceStatus.LATE]
        out.append(AttendanceMonth(
            month=m, present=c[AttendanceStatus.PRESENT], late=c[AttendanceStatus.LATE],
            absent=c[AttendanceStatus.ABSENT], excused=c[AttendanceStatus.EXCUSED],
            rate=_pct(attended, marked) if marked else None,
        ))
    return out


def _on_time_rate(rows: list[HomeworkSubmission]) -> int | None:
    handed = [r for r in rows if r.submitted_at and r.homework.due_at]
    if not handed:
        return None
    return _pct(sum(1 for r in handed if r.submitted_at <= r.homework.due_at), len(handed))


def _trend(points: list[ScorePoint]) -> int | None:
    if len(points) < 4:
        return None
    last = [p.percent for p in points[-3:]]
    before = [p.percent for p in points[-6:-3]]
    return _avg(last) - _avg(before)


def student_progress(db: Session, student: StudentProfile, viewer: User) -> StudentProgress:
    ids = [student.id]
    tests = _test_points(db, ids).get(student.id, [])
    hw_rows = _homework_rows(db, ids)
    homework = _homework_points(hw_rows).get(student.id, [])
    visits = _attendance_rows(db, ids).get(student.id, [])
    return StudentProgress(
        student_id=student.id,
        full_name=student.user.full_name,
        english_level=student.english_level,
        summary=ProgressSummary(
            avg_test=_avg([p.percent for p in tests]),
            avg_homework=_avg([p.percent for p in homework]),
            attendance_rate=_rate(visits),
            tests_count=len(tests),
            homework_count=len(homework),
            on_time_rate=_on_time_rate(hw_rows),
            test_trend=_trend(tests),
        ),
        tests=tests,
        homework=homework,
        attendance=_attendance_by_month(visits, viewer.timezone),
    )


# ---------- the teacher's overview ----------

def teacher_overview(db: Session, teacher_id: int, period_days: int, group_id: int | None = None) -> TeacherOverview:
    now = datetime.now(UTC)
    since = now - timedelta(days=period_days)
    q = (
        select(StudentProfile)
        .options(selectinload(StudentProfile.user), selectinload(StudentProfile.groups))
        .where(StudentProfile.teacher_id == teacher_id)
    )
    students = [s for s in db.scalars(q).all() if s.user.is_active]
    if group_id is not None:
        students = [s for s in students if any(g.id == group_id for g in s.groups)]
    ids = [s.id for s in students]
    if not ids:
        return TeacherOverview(period_days=period_days, students=0, at_risk=0, avg_test=None,
                               avg_homework=None, attendance_rate=None, rows=[])

    tests = _test_points(db, ids, since)
    hw_rows = _homework_rows(db, ids)
    homework = _homework_points(hw_rows, since)
    visits = _attendance_rows(db, ids, since)
    overdue: dict[int, int] = defaultdict(int)
    last_hw: dict[int, datetime] = {}
    for r in hw_rows:
        if r.status in OPEN and r.homework.due_at and r.homework.due_at < now:
            overdue[r.student_id] += 1
        if r.submitted_at and (r.student_id not in last_hw or r.submitted_at > last_hw[r.student_id]):
            last_hw[r.student_id] = r.submitted_at
    last_test = dict(db.execute(
        select(TestAttempt.student_id, TestAttempt.submitted_at)
        .where(TestAttempt.student_id.in_(ids), TestAttempt.submitted_at.is_not(None))
        .order_by(TestAttempt.submitted_at)
    ).all())

    rows = []
    for s in students:
        t = [p.percent for p in tests.get(s.id, [])]
        h = [p.percent for p in homework.get(s.id, [])]
        att = _rate(visits.get(s.id, []))
        marked = sum(1 for v in visits.get(s.id, []) if v.status is not None)
        activity = [d for d in (s.user.last_login_at, last_hw.get(s.id), last_test.get(s.id)) if d]
        last = max(activity) if activity else None
        sub = subscription_service.current_subscription(db, s.id)
        sub_status = subscription_service.compute_status(sub) if sub else None

        risks = []
        if att is not None and marked >= 3 and att < LOW_ATTENDANCE:
            risks.append("low_attendance")
        if t and _avg(t) < LOW_TESTS:
            risks.append("low_tests")
        if overdue[s.id] >= OVERDUE_LIMIT:
            risks.append("overdue_homework")
        if sub_status == SubscriptionStatus.EXPIRED:
            risks.append("subscription_expired")
        if last is None or last < now - timedelta(days=INACTIVE_DAYS):
            risks.append("inactive")
        rows.append(StudentOverviewRow(
            student_id=s.id, full_name=s.user.full_name, english_level=s.english_level,
            groups=sorted(g.name for g in s.groups), avg_test=_avg(t), avg_homework=_avg(h),
            attendance_rate=att, overdue_homework=overdue[s.id], last_activity=last,
            subscription_status=sub_status, risks=risks,
        ))
    # students needing attention first (more reasons first), then by name
    rows.sort(key=lambda r: (-len(r.risks), r.full_name.lower()))
    all_t = [p.percent for pts in tests.values() for p in pts]
    all_h = [p.percent for pts in homework.values() for p in pts]
    all_v = [v for vs in visits.values() for v in vs]
    return TeacherOverview(
        period_days=period_days,
        students=len(rows),
        at_risk=sum(1 for r in rows if r.risks),
        avg_test=_avg(all_t),
        avg_homework=_avg(all_h),
        attendance_rate=_rate(all_v),
        rows=rows,
    )

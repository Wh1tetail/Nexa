"""Who takes part in what: lesson participants, group lessons, test and homework
assignees.

Removal is always soft (`removed_at`): the row keeps attendance marks, answers,
files, grades and attempts, and adding the same student again restores it, so
there are never duplicate assignments and history is never deleted.
"""
from datetime import UTC, datetime

from sqlalchemy import and_, insert, select, update
from sqlalchemy.orm import Session

from app.models import Attendance, Group, Lesson, StudentProfile
from app.models.enums import LessonStatus
from app.services import attendance_service as att_svc
from app.services import subscription_service as subs


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- lesson participants ----------

def _all_rows(db: Session, lesson: Lesson) -> dict[int, Attendance]:
    """Active and removed participant rows of a lesson, by student id."""
    if lesson.id is None:
        return {a.student_id: a for a in lesson.attendance}
    rows = db.scalars(select(Attendance).where(Attendance.lesson_id == lesson.id)).all()
    return {a.student_id: a for a in rows}


def add_to_lesson(db: Session, lesson: Lesson, students: list[StudentProfile]) -> list[StudentProfile]:
    """Add students (restoring removed rows with their marks). Returns the newly active ones."""
    rows = _all_rows(db, lesson)
    added = []
    for s in students:
        row = rows.get(s.id)
        if row is None:
            lesson.attendance.append(Attendance(student_id=s.id))
            added.append(s)
        elif row.removed_at is not None:
            row.removed_at = None
            if row.status is not None:  # a kept mark counts again (charged as before)
                att_svc.apply_mark(db, row, row.status, row.comment)
            added.append(s)
    if added and lesson.id is not None:
        db.flush()
        db.expire(lesson, ["attendance", "removed_attendance"])
    return added


def remove_from_lesson(db: Session, lesson: Lesson, student_ids: set[int]) -> list[int]:
    """Take students off a lesson: the row and its mark stay, a charged lesson goes
    back to the subscription. Group membership and other lessons are untouched."""
    removed = []
    for row in list(lesson.attendance):
        if row.student_id in student_ids:
            if row.charged_subscription_id is not None:
                subs.refund_lesson(db, row.charged_subscription_id)
                row.charged_subscription_id = None
            row.removed_at = _now()
            removed.append(row.student_id)
    if removed:
        db.flush()
        db.expire(lesson, ["attendance", "removed_attendance"])
    return removed


def sync_lesson(db: Session, lesson: Lesson, students: list[StudentProfile]) -> list[StudentProfile]:
    """Make the active participants exactly `students`."""
    wanted = {s.id for s in students}
    remove_from_lesson(db, lesson, {a.student_id for a in lesson.attendance} - wanted)
    return add_to_lesson(db, lesson, students)


# ---------- group membership -> group lessons ----------

def _upcoming_group_lessons(db: Session, group: Group, since: datetime) -> list[Lesson]:
    return list(db.scalars(
        select(Lesson).where(
            Lesson.group_id == group.id,
            Lesson.status == LessonStatus.SCHEDULED,
            Lesson.starts_at >= since,
        ).order_by(Lesson.starts_at)
    ).all())


def assign_group_lessons(
    db: Session, group: Group, students: list[StudentProfile], since: datetime | None = None
) -> int:
    """New group members join the group's scheduled lessons from `since` (default:
    now). Lessons that already took place are never assigned. Returns the number
    of lesson places added."""
    start = max(since or _now(), _now())
    count = 0
    for lesson in _upcoming_group_lessons(db, group, start):
        count += len(add_to_lesson(db, lesson, students))
    return count


def release_group_lessons(db: Session, group: Group, student_ids: set[int]) -> int:
    """Students who left the group are taken off its upcoming lessons; past lessons
    and their attendance stay as they were."""
    count = 0
    for lesson in _upcoming_group_lessons(db, group, _now()):
        count += len(remove_from_lesson(db, lesson, student_ids))
    return count


def change_group_members(
    db: Session,
    group: Group,
    students: list[StudentProfile],
    *,
    assign_lessons: bool = True,
    lessons_from: datetime | None = None,
) -> tuple[list[StudentProfile], set[int]]:
    """Set the group's members and keep its upcoming lessons in step.
    Returns (added students, removed student ids)."""
    before = {s.id for s in group.students}
    after = {s.id for s in students}
    group.students = students
    added = [s for s in students if s.id not in before]
    removed = before - after
    db.flush()
    if assign_lessons and added:
        assign_group_lessons(db, group, added, lessons_from)
    if removed:
        release_group_lessons(db, group, removed)
    return added, removed


# ---------- tests ----------

def test_rows(db: Session, test_id: int) -> dict[int, datetime | None]:
    """student_id -> removed_at for every assignment row of a test."""
    from app.models.test import test_assignments as ta
    return dict(db.execute(select(ta.c.student_id, ta.c.removed_at).where(ta.c.test_id == test_id)).all())


def assign_test(db: Session, test_id: int, students: list[StudentProfile]) -> list[StudentProfile]:
    """Assign (or restore). Returns the students who became active assignees."""
    from app.models.test import test_assignments as ta
    rows = test_rows(db, test_id)
    added = []
    for s in students:
        if s.id not in rows:
            db.execute(insert(ta).values(test_id=test_id, student_id=s.id))
            added.append(s)
        elif rows[s.id] is not None:
            db.execute(update(ta).where(and_(ta.c.test_id == test_id, ta.c.student_id == s.id)).values(removed_at=None))
            added.append(s)
    return added


def unassign_test(db: Session, test_id: int, student_ids: set[int]) -> list[int]:
    """Exclude students from a test; attempts and results stay."""
    from app.models.test import test_assignments as ta
    active = [sid for sid, removed in test_rows(db, test_id).items() if removed is None and sid in student_ids]
    if active:
        db.execute(
            update(ta).where(ta.c.test_id == test_id, ta.c.student_id.in_(active)).values(removed_at=_now())
        )
    return active

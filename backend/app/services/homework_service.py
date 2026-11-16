from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.i18n import M
from app.models import Homework, HomeworkSubmission, StudentProfile
from app.models.enums import NotificationType, SubmissionStatus
from app.schemas.homework import (
    AttachmentOut,
    HomeworkDetail,
    HomeworkListItem,
    StudentHomework,
    SubmissionCounts,
    SubmissionOut,
)
from app.services.notification_service import notify


def assign(db: Session, hw: Homework, students: list[StudentProfile]) -> int:
    """Assign students; an excluded student is restored with their earlier work."""
    existing = {s.student_id: s for s in hw.submissions}
    new_students = []
    for s in students:
        sub = existing.get(s.id)
        if sub is None:
            hw.submissions.append(HomeworkSubmission(student_id=s.id, status=SubmissionStatus.NEW))
            new_students.append(s)
        elif sub.removed_at is not None:
            sub.removed_at = None
            new_students.append(s)
    db.flush()
    by_student = {s.student_id: s.id for s in hw.submissions}
    for s in new_students:
        notify(
            db,
            [s.user_id],
            NotificationType.HOMEWORK_ASSIGNED,
            M("Новое домашнее задание"),
            hw.title,
            f"/student/homework/{by_student[s.id]}",
        )
    return len(new_students)


def unassign(hw: Homework, student_ids: set[int]) -> list[int]:
    """Exclude students: the task disappears for them; files, grade and comments stay."""
    now = datetime.now(UTC)
    removed = []
    for sub in hw.submissions:
        if sub.student_id in student_ids and sub.removed_at is None:
            sub.removed_at = now
            removed.append(sub.student_id)
    return removed


def counts(hw: Homework) -> SubmissionCounts:
    active = [s for s in hw.submissions if s.removed_at is None]
    c = SubmissionCounts(total=len(active), removed=len(hw.submissions) - len(active))
    for s in active:
        setattr(c, s.status.value, getattr(c, s.status.value) + 1)
    return c


def to_list_item(hw: Homework) -> HomeworkListItem:
    return HomeworkListItem(
        id=hw.id,
        title=hw.title,
        due_at=hw.due_at,
        created_at=hw.created_at,
        max_grade=hw.max_grade,
        counts=counts(hw),
    )


def submission_out(s: HomeworkSubmission) -> SubmissionOut:
    return SubmissionOut(
        id=s.id,
        homework_id=s.homework_id,
        student_id=s.student_id,
        student_name=s.student.user.full_name,
        status=s.status,
        student_comment=s.student_comment,
        teacher_comment=s.teacher_comment,
        grade=s.grade,
        submitted_at=s.submitted_at,
        reviewed_at=s.reviewed_at,
        files=[AttachmentOut.model_validate(f) for f in s.files],
        removed_at=s.removed_at,
    )


def to_detail(hw: Homework) -> HomeworkDetail:
    return HomeworkDetail(
        id=hw.id,
        title=hw.title,
        description=hw.description,
        due_at=hw.due_at,
        max_grade=hw.max_grade,
        created_at=hw.created_at,
        attachments=[AttachmentOut.model_validate(a) for a in hw.attachments],
        submissions=sorted(
            (submission_out(s) for s in hw.submissions), key=lambda x: x.student_name
        ),
    )


def to_student_view(s: HomeworkSubmission) -> StudentHomework:
    hw = s.homework
    now = datetime.now(UTC)
    overdue = bool(
        hw.due_at
        and hw.due_at < now
        and s.status in (SubmissionStatus.NEW, SubmissionStatus.IN_PROGRESS, SubmissionStatus.NEEDS_REVISION)
    )
    return StudentHomework(
        submission_id=s.id,
        homework_id=hw.id,
        title=hw.title,
        description=hw.description,
        due_at=hw.due_at,
        max_grade=hw.max_grade,
        teacher_name=hw.teacher.user.full_name,
        status=s.status,
        is_overdue=overdue,
        student_comment=s.student_comment,
        teacher_comment=s.teacher_comment,
        grade=s.grade,
        submitted_at=s.submitted_at,
        reviewed_at=s.reviewed_at,
        created_at=hw.created_at,
        attachments=[AttachmentOut.model_validate(a) for a in hw.attachments],
        files=[AttachmentOut.model_validate(f) for f in s.files],
    )

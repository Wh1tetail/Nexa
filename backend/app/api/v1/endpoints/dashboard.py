from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentStudent, CurrentTeacher
from app.models import (
    Homework,
    HomeworkSubmission,
    Lesson,
    Notification,
    StudentProfile,
    Test,
    TestAttempt,
)
from app.models.enums import AttemptStatus, LessonStatus, SubmissionStatus, SubscriptionStatus
from app.models.test import test_assignments
from app.repositories import student_repository as repo
from app.schemas.dashboard import ActivityItem, StudentDashboard, TeacherDashboard, UpcomingLesson
from app.schemas.notification import NotificationOut
from app.services import attendance_service as att_svc
from app.services import student_service
from app.services import subscription_service as sub_svc
from app.services import test_service as test_svc

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/student", response_model=StudentDashboard)
def student_dashboard(student: CurrentStudent, db: DB) -> StudentDashboard:
    statuses = db.execute(
        select(HomeworkSubmission.status, func.count())
        .where(HomeworkSubmission.student_id == student.id)
        .group_by(HomeworkSubmission.status)
    ).all()
    by_status = {s: n for s, n in statuses}
    done = by_status.get(SubmissionStatus.REVIEWED, 0) + by_status.get(SubmissionStatus.SUBMITTED, 0)
    upcoming = by_status.get(SubmissionStatus.NEW, 0) + by_status.get(SubmissionStatus.IN_PROGRESS, 0)

    tests = db.scalars(
        select(Test)
        .join(test_assignments, test_assignments.c.test_id == Test.id)
        .options(selectinload(Test.questions))
        .where(test_assignments.c.student_id == student.id)
    ).all()
    attempts = {
        a.test_id: a for a in db.scalars(select(TestAttempt).where(TestAttempt.student_id == student.id)).all()
    }
    items = [test_svc.student_item(t, attempts.get(t.id)) for t in tests]
    recent = sorted(
        (i for i in items if i.submitted_at), key=lambda i: i.submitted_at, reverse=True
    )[:5]
    pending = sum(1 for i in items if i.attempt_status in (None, AttemptStatus.IN_PROGRESS) and not i.is_overdue)

    rows = list(db.scalars(att_svc.records_query(student_id=student.id)).unique().all())
    now = datetime.now(UTC)
    next_lessons = sorted(
        (r for r in rows if r.lesson.starts_at >= now and r.lesson.status == LessonStatus.SCHEDULED),
        key=lambda r: r.lesson.starts_at,
    )[:3]

    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == student.user_id)
        .order_by(Notification.created_at.desc())
        .limit(5)
    ).all()
    sub = sub_svc.current_subscription(db, student.id)
    access = sub_svc.has_access(db, student.id)
    if not access:  # no lesson links, tasks or results until the subscription is renewed
        next_lessons, recent, pending, upcoming = [], [], 0, 0
    return StudentDashboard(
        access_active=access,
        full_name=student.user.full_name,
        english_level=student.english_level,
        teacher_name=student.teacher.user.full_name if student.teacher else None,
        homework_done=done,
        homework_upcoming=upcoming,
        homework_needs_revision=by_status.get(SubmissionStatus.NEEDS_REVISION, 0),
        subscription=sub_svc.to_out(sub) if sub else None,
        recent_tests=recent,
        pending_tests=pending,
        attendance=att_svc.build_stats(student, rows),
        next_lessons=[att_svc.to_my_lesson(r) for r in next_lessons],
        notifications=[NotificationOut.model_validate(n) for n in notifications],
    )


@router.get("/teacher", response_model=TeacherDashboard)
def teacher_dashboard(teacher: CurrentTeacher, db: DB) -> TeacherDashboard:
    students = repo.list_for_teacher(db, teacher.id, active=True)
    by_student = repo.subscriptions_by_student(db, [s.id for s in students])
    current = [
        c for c in (student_service.pick_current(by_student.get(s.id, [])) for s in students) if c
    ]
    statuses = [(c, sub_svc.compute_status(c)) for c in current]

    hw_to_review = db.scalar(
        select(func.count())
        .select_from(HomeworkSubmission)
        .join(HomeworkSubmission.homework)
        .where(Homework.teacher_id == teacher.id, HomeworkSubmission.status == SubmissionStatus.SUBMITTED)
    )
    tests_to_review = db.scalar(
        select(func.count())
        .select_from(TestAttempt)
        .join(TestAttempt.test)
        .where(Test.teacher_id == teacher.id, TestAttempt.status == AttemptStatus.PENDING_REVIEW)
    )
    now = datetime.now(UTC)
    lessons = db.scalars(
        select(Lesson)
        .options(selectinload(Lesson.attendance), selectinload(Lesson.group))
        .where(
            Lesson.teacher_id == teacher.id,
            Lesson.starts_at >= now,
            Lesson.status == LessonStatus.SCHEDULED,
        )
        .order_by(Lesson.starts_at)
        .limit(5)
    ).all()

    # recent activity: submissions + completed tests
    subs = db.scalars(
        select(HomeworkSubmission)
        .join(HomeworkSubmission.homework)
        .options(
            selectinload(HomeworkSubmission.homework),
            selectinload(HomeworkSubmission.student).selectinload(StudentProfile.user),
        )
        .where(Homework.teacher_id == teacher.id, HomeworkSubmission.submitted_at.is_not(None))
        .order_by(HomeworkSubmission.submitted_at.desc())
        .limit(8)
    ).all()
    attempts = db.scalars(
        select(TestAttempt)
        .join(TestAttempt.test)
        .options(
            selectinload(TestAttempt.test),
            selectinload(TestAttempt.student).selectinload(StudentProfile.user),
        )
        .where(Test.teacher_id == teacher.id, TestAttempt.submitted_at.is_not(None))
        .order_by(TestAttempt.submitted_at.desc())
        .limit(8)
    ).all()
    activity = [
        ActivityItem(
            kind="homework_submitted",
            student_id=s.student_id,
            student_name=s.student.user.full_name,
            title=s.homework.title,
            at=s.submitted_at,
            link=f"/teacher/homework/{s.homework_id}?submission={s.id}",
        )
        for s in subs
    ] + [
        ActivityItem(
            kind="test_completed",
            student_id=a.student_id,
            student_name=a.student.user.full_name,
            title=a.test.title,
            at=a.submitted_at,
            link=f"/teacher/tests/{a.test_id}/attempts/{a.id}",
        )
        for a in attempts
    ]
    activity.sort(key=lambda x: x.at, reverse=True)

    expiring = sorted(
        (c for c, st in statuses if st in (SubscriptionStatus.EXPIRING_SOON, SubscriptionStatus.EXPIRED)),
        key=lambda c: c.end_date,
    )
    return TeacherDashboard(
        full_name=teacher.user.full_name,
        students_total=len(students),
        subscriptions_active=sum(1 for _, st in statuses if st in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRING_SOON)),
        subscriptions_expiring=sum(1 for _, st in statuses if st == SubscriptionStatus.EXPIRING_SOON),
        subscriptions_expired=sum(1 for _, st in statuses if st == SubscriptionStatus.EXPIRED),
        homework_to_review=hw_to_review or 0,
        tests_to_review=tests_to_review or 0,
        upcoming_lessons=[
            UpcomingLesson(
                id=lesson.id,
                title=lesson.title,
                starts_at=lesson.starts_at,
                duration_minutes=lesson.duration_minutes,
                participants=len(lesson.attendance),
                group_name=lesson.group.name if lesson.group else None,
            )
            for lesson in lessons
        ],
        expiring_subscriptions=[sub_svc.to_out(c) for c in expiring[:6]],
        recent_activity=activity[:8],
    )

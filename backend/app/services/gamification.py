"""XP and achievements.

XP is paid only for confirmed results: a completed course lesson (completion
happens once, under a row lock) and a graded test (automatically or after the
teacher's review). Every award is a row keyed by (student, reason, object) and
inserted with ON CONFLICT DO NOTHING, so repeated or parallel requests can
never pay twice. Achievements work the same way (one row per student and code).
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.i18n import M
from app.core.timezones import get_zone
from app.models import (
    AppSetting,
    CourseLesson,
    CourseLevel,
    CourseModule,
    LessonProgress,
    StudentAchievement,
    StudentActivityDay,
    StudentProfile,
    TestAttempt,
    XPTransaction,
)
from app.models.enums import AchievementCode as A
from app.models.enums import NotificationType, XPReason
from app.schemas.gamification import AchievementOut, Awards, GamificationOut, XPEntry, XPSettings
from app.services.notification_service import notify

SETTINGS_KEY = "xp"
LESSONS_FOR_BADGE = 10
STREAK_FOR_BADGE = 7

# Russian templates (translated through the i18n catalogue) for notifications
TITLES = {
    A.FIRST_LESSON: "Первый урок",
    A.FIRST_TEST: "Первый тест",
    A.PERFECT_SCORE: "Идеальный результат",
    A.STREAK_7: "7 дней подряд",
    A.LESSONS_10: "10 уроков",
    A.LEVEL_COMPLETED: "Уровень пройден",
}


# ---------- settings ----------

def get_settings(db: Session) -> XPSettings:
    row = db.get(AppSetting, SETTINGS_KEY)
    return XPSettings(**(row.value if row else {}))


def save_settings(db: Session, data: XPSettings, user_id: int) -> XPSettings:
    row = db.get(AppSetting, SETTINGS_KEY)
    if row is None:
        row = AppSetting(key=SETTINGS_KEY, value={})
        db.add(row)
    row.value = data.model_dump()
    row.updated_at = datetime.now(UTC)
    row.updated_by_id = user_id
    return data


# ---------- levels ----------

def level_start(level: int) -> int:
    """XP at which a gamification level starts: 0, 100, 300, 600, 1000, …"""
    return 50 * level * (level - 1)


def level_of(xp: int) -> int:
    level = 1
    while xp >= level_start(level + 1):
        level += 1
    return level


# ---------- awarding ----------

def _award(db: Session, student_id: int, reason: XPReason, ref: str, points: int, title: str) -> int:
    """Pay XP once; returns the points paid now (0 when it was paid before)."""
    if points <= 0:
        return 0
    stmt = (
        insert(XPTransaction)
        .values(student_id=student_id, reason=reason, ref_key=ref, points=points, title=title[:200])
        .on_conflict_do_nothing(constraint="uq_xp_transactions_once")
        .returning(XPTransaction.id)
    )
    return points if db.execute(stmt).first() else 0


def _grant(db: Session, student: StudentProfile, code: A) -> bool:
    stmt = (
        insert(StudentAchievement)
        .values(student_id=student.id, code=code)
        .on_conflict_do_nothing(constraint="uq_student_achievements_code")
        .returning(StudentAchievement.id)
    )
    if db.execute(stmt).first() is None:
        return False
    notify(db, [student.user_id], NotificationType.SYSTEM, M("Новое достижение"), M(TITLES[code]), "/student/achievements")
    return True


def _today(student: StudentProfile):
    return datetime.now(get_zone(student.user.timezone)).date()


def streak(db: Session, student: StudentProfile) -> int:
    """Learning days in a row ending today (or yesterday, if today has no activity yet)."""
    days = set(db.scalars(select(StudentActivityDay.day).where(StudentActivityDay.student_id == student.id)).all())
    day = _today(student)
    if day not in days:
        day -= timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= timedelta(days=1)
    return n


def mark_activity(db: Session, student: StudentProfile) -> list[A]:
    """Today is a learning day; returns achievements earned by it (the streak)."""
    db.execute(
        insert(StudentActivityDay).values(student_id=student.id, day=_today(student)).on_conflict_do_nothing()
    )
    if streak(db, student) >= STREAK_FOR_BADGE and _grant(db, student, A.STREAK_7):
        return [A.STREAK_7]
    return []


def _completed_ids(db: Session, student_id: int) -> set[int]:
    return set(db.scalars(select(LessonProgress.lesson_id).where(
        LessonProgress.student_id == student_id, LessonProgress.completed_at.isnot(None),
        LessonProgress.lesson_id.isnot(None),
    )).all())


def _all_done(lessons: list[CourseLesson], done: set[int]) -> bool:
    published = [x.id for x in lessons if x.published]
    return bool(published) and all(i in done for i in published)


def on_lesson_completed(db: Session, student: StudentProfile, lesson: CourseLesson) -> Awards:
    """Called once, when the lesson has just been completed."""
    db.flush()  # the completion must be visible to the queries below (no autoflush)
    s = get_settings(db)
    out = Awards()
    out.xp += _award(db, student.id, XPReason.LESSON, f"lesson:{lesson.id}", s.lesson, lesson.title)
    done = _completed_ids(db, student.id)
    module: CourseModule = lesson.module
    level: CourseLevel = module.level
    if _all_done(list(module.lessons), done):
        out.xp += _award(db, student.id, XPReason.MODULE, f"module:{module.id}", s.module, module.title)
    if _all_done([x for m in level.modules for x in m.lessons], done):
        out.xp += _award(db, student.id, XPReason.LEVEL, f"level:{level.id}", s.level,
                         f"{level.course.title} · {level.title}")
        if _grant(db, student, A.LEVEL_COMPLETED):
            out.achievements.append(A.LEVEL_COMPLETED)
    if _grant(db, student, A.FIRST_LESSON):
        out.achievements.append(A.FIRST_LESSON)
    completed_total = db.scalar(select(func.count()).select_from(LessonProgress).where(
        LessonProgress.student_id == student.id, LessonProgress.completed_at.isnot(None)))
    if completed_total >= LESSONS_FOR_BADGE and _grant(db, student, A.LESSONS_10):
        out.achievements.append(A.LESSONS_10)
    progress = db.scalars(select(LessonProgress).where(
        LessonProgress.student_id == student.id, LessonProgress.lesson_id == lesson.id)).first()
    if progress and progress.score_percent is not None and progress.score_percent >= 100 and _grant(db, student, A.PERFECT_SCORE):
        out.achievements.append(A.PERFECT_SCORE)
    out.achievements += mark_activity(db, student)
    return out


def on_test_graded(db: Session, attempt: TestAttempt) -> Awards:
    """Called whenever an attempt becomes graded (repeat calls pay nothing new)."""
    from app.services.test_service import percent

    student = attempt.student
    s = get_settings(db)
    out = Awards()
    title = attempt.test.title
    out.xp += _award(db, student.id, XPReason.TEST, f"test:{attempt.test_id}", s.test, title)
    pct = percent(attempt)
    if pct is not None and pct >= s.bonus_threshold:
        out.xp += _award(db, student.id, XPReason.TEST_BONUS, f"test:{attempt.test_id}", s.test_bonus, title)
    if _grant(db, student, A.FIRST_TEST):
        out.achievements.append(A.FIRST_TEST)
    if pct == 100 and _grant(db, student, A.PERFECT_SCORE):
        out.achievements.append(A.PERFECT_SCORE)
    return out


# ---------- the student's summary ----------

def summary(db: Session, student: StudentProfile) -> GamificationOut:
    xp = db.scalar(select(func.coalesce(func.sum(XPTransaction.points), 0)).where(XPTransaction.student_id == student.id)) or 0
    level = level_of(xp)
    earned = {a.code: a.earned_at for a in db.scalars(
        select(StudentAchievement).where(StudentAchievement.student_id == student.id)).all()}
    completed = db.scalar(select(func.count()).select_from(LessonProgress).where(
        LessonProgress.student_id == student.id, LessonProgress.completed_at.isnot(None))) or 0
    days = streak(db, student)
    progress = {A.LESSONS_10: (min(completed, LESSONS_FOR_BADGE), LESSONS_FOR_BADGE),
                A.STREAK_7: (min(days, STREAK_FOR_BADGE), STREAK_FOR_BADGE)}
    achievements = [
        AchievementOut(code=code, earned_at=earned.get(code),
                       progress=progress.get(code, (None, None))[0], target=progress.get(code, (None, None))[1])
        for code in A
    ]
    recent = db.scalars(select(XPTransaction).where(XPTransaction.student_id == student.id)
                        .order_by(XPTransaction.created_at.desc(), XPTransaction.id.desc()).limit(20)).all()
    return GamificationOut(
        xp_total=xp, level=level, level_xp=level_start(level), next_level_xp=level_start(level + 1),
        streak_days=days, achievements=achievements,
        recent=[XPEntry(reason=r.reason, points=r.points, title=r.title, created_at=r.created_at) for r in recent],
        settings=get_settings(db),
    )

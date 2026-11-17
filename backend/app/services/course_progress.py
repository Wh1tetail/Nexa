"""Course assignments and students' progress.

An assignment gives a level or a module of a published course to students;
the content stays shared. A student sees the published lessons of their active
assignments once `starts_at` has come. Work on a lesson is kept in
LessonProgress (answers and results per exercise block, listens, completion).
Taking a student off or cancelling an assignment sets removed_at; progress is
never deleted with it.
"""
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, NotFound
from app.core.i18n import M
from app.models import (
    Course,
    CourseAssignment,
    CourseAssignmentStudent,
    CourseLesson,
    CourseLevel,
    CourseModule,
    Group,
    LessonBlock,
    LessonProgress,
    StudentProfile,
    TeacherProfile,
)
from app.models.enums import NotificationType
from app.schemas.course import CheckResult, QuestionResult
from app.schemas.course_assignment import (
    AssignmentDetail,
    AssignmentItem,
    AssignmentStudentRow,
    AssignResult,
    BlockState,
    CourseProgressItem,
    CourseProgressOut,
    StudentCourseDetail,
    StudentCourseItem,
    StudentLessonItem,
    StudentLessonRow,
    StudentLessonView,
    StudentModule,
    StudentProgressRow,
)
from app.services import course_service as cs
from app.services import lesson_blocks as lb
from app.services.notification_service import notify


def now() -> datetime:
    return datetime.now(UTC)


# ---------- the scope of an assignment ----------

def scope_modules(a: CourseAssignment) -> list[CourseModule]:
    return list(a.level.modules) if a.level_id else [a.module]


def scope_lessons(a: CourseAssignment) -> list[CourseLesson]:
    """Published lessons of the assignment, in course order."""
    return [les for m in scope_modules(a) for les in m.lessons if les.published]


def scope_level(a: CourseAssignment) -> CourseLevel:
    return a.level if a.level_id else a.module.level


def scope_title(a: CourseAssignment) -> str:
    return a.level.title if a.level_id else a.module.title


def is_started(a: CourseAssignment) -> bool:
    return a.starts_at <= now()


def exercise_blocks(les: CourseLesson) -> list[LessonBlock]:
    return [b for b in les.blocks if b.type in lb.EXERCISES]


# ---------- what a student has ----------

def student_assignments(db: Session, student_id: int) -> list[CourseAssignment]:
    """Active assignments of the student in published courses (started or not)."""
    q = (
        select(CourseAssignment)
        .join(CourseAssignmentStudent, CourseAssignmentStudent.assignment_id == CourseAssignment.id)
        .join(Course, Course.id == CourseAssignment.course_id)
        .where(
            CourseAssignmentStudent.student_id == student_id,
            CourseAssignmentStudent.removed_at.is_(None),
            CourseAssignment.removed_at.is_(None),
            Course.published.is_(True),
        )
        .order_by(CourseAssignment.starts_at, CourseAssignment.id)
    )
    return list(db.scalars(q).all())


def progress_rows(db: Session, student_id: int, lesson_ids: list[int] | None = None) -> dict[int, LessonProgress]:
    q = select(LessonProgress).where(LessonProgress.student_id == student_id, LessonProgress.lesson_id.isnot(None))
    if lesson_ids is not None:
        if not lesson_ids:
            return {}
        q = q.where(LessonProgress.lesson_id.in_(lesson_ids))
    return {p.lesson_id: p for p in db.scalars(q).all()}  # type: ignore[misc]


def state(p: LessonProgress | None) -> str:
    if p is None:
        return "not_started"
    return "completed" if p.completed_at else "in_progress"


def _pct(done: int, total: int) -> int:
    return round(100 * done / total) if total else 0


def _mean(values: list[float]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def _lesson_item(les: CourseLesson, p: LessonProgress | None) -> StudentLessonItem:
    return StudentLessonItem(
        id=les.id, title=les.title, duration_minutes=les.duration_minutes, status=state(p),  # type: ignore[arg-type]
        score_percent=round(p.score_percent) if p and p.score_percent is not None else None,
        completed_at=p.completed_at if p else None,
    )


def _modules(modules: list[CourseModule], progress: dict[int, LessonProgress]) -> list[StudentModule]:
    out = []
    for m in modules:
        lessons = [_lesson_item(x, progress.get(x.id)) for x in m.lessons if x.published]
        if not lessons:
            continue
        out.append(StudentModule(id=m.id, title=m.title, description=m.description, lessons=lessons,
                                 completed=all(x.status == "completed" for x in lessons)))
    return out


def _course_item(a: CourseAssignment, progress: dict[int, LessonProgress]) -> StudentCourseItem:
    lessons = scope_lessons(a)
    done = [x for x in lessons if state(progress.get(x.id)) == "completed"]
    nxt = next((x.id for x in lessons if state(progress.get(x.id)) != "completed"), None)
    return StudentCourseItem(
        assignment_id=a.id, course_id=a.course_id, course_title=a.course.title,
        course_description=a.course.description, scope="level" if a.level_id else "module",
        scope_title=scope_title(a), level=scope_level(a).level,
        teacher_name=a.teacher.user.full_name if a.teacher else None,
        starts_at=a.starts_at, due_at=a.due_at, started=is_started(a),
        overdue=bool(a.due_at and a.due_at < now() and len(done) < len(lessons)),
        lessons_total=len(lessons), lessons_completed=len(done), percent=_pct(len(done), len(lessons)),
        next_lesson_id=nxt if is_started(a) else None,
    )


def student_courses(db: Session, student: StudentProfile) -> list[StudentCourseItem]:
    assignments = student_assignments(db, student.id)
    ids = [x.id for a in assignments for x in scope_lessons(a)]
    progress = progress_rows(db, student.id, ids)
    return [_course_item(a, progress) for a in assignments]


def get_student_assignment(db: Session, student: StudentProfile, assignment_id: int) -> CourseAssignment:
    a = next((x for x in student_assignments(db, student.id) if x.id == assignment_id), None)
    if a is None:
        raise NotFound("Курс не найден")
    return a


def student_course(db: Session, student: StudentProfile, assignment_id: int) -> StudentCourseDetail:
    a = get_student_assignment(db, student, assignment_id)
    progress = progress_rows(db, student.id, [x.id for x in scope_lessons(a)])
    return StudentCourseDetail(**_course_item(a, progress).model_dump(), modules=_modules(scope_modules(a), progress))


def student_lessons(db: Session, student: StudentProfile) -> list[StudentLessonRow]:
    """Every lesson of the student's started assignments (each lesson once)."""
    rows: list[StudentLessonRow] = []
    seen: set[int] = set()
    assignments = [a for a in student_assignments(db, student.id) if is_started(a)]
    progress = progress_rows(db, student.id, [x.id for a in assignments for x in scope_lessons(a)])
    for a in assignments:
        for m in scope_modules(a):
            for les in m.lessons:
                if not les.published or les.id in seen:
                    continue
                seen.add(les.id)
                item = _lesson_item(les, progress.get(les.id))
                rows.append(StudentLessonRow(**item.model_dump(), assignment_id=a.id, course_title=a.course.title,
                                             module_title=m.title, level=m.level.level))
    return rows


def lesson_access(db: Session, student: StudentProfile, lesson_id: int) -> tuple[CourseLesson, CourseAssignment]:
    """The lesson and the (first) started assignment that gives it; 404 otherwise."""
    les = db.get(CourseLesson, lesson_id)
    if les is not None and les.published:
        for a in student_assignments(db, student.id):
            if is_started(a) and any(x.id == les.id for x in scope_lessons(a)):
                return les, a
    raise NotFound("Урок не найден")


def can_open_lesson_file(db: Session, student: StudentProfile, lesson_id: int) -> bool:
    try:
        lesson_access(db, student, lesson_id)
        return True
    except NotFound:
        return False


# ---------- working on a lesson ----------

def _progress_for_update(db: Session, student: StudentProfile, les: CourseLesson) -> LessonProgress:
    """The student's progress row for the lesson, locked; created on first use."""
    q = select(LessonProgress).where(LessonProgress.student_id == student.id, LessonProgress.lesson_id == les.id)
    p = db.scalars(q.with_for_update()).first()
    if p is not None:
        return p
    try:
        with db.begin_nested():
            db.add(LessonProgress(student_id=student.id, lesson_id=les.id, course_id=les.module.level.course_id,
                                  lesson_title=les.title, blocks={}, plays={}))
    except IntegrityError:  # created by a parallel request
        pass
    return db.scalars(q.with_for_update()).one()


def _valid_check(b: LessonBlock, saved: dict[str, Any] | None) -> bool:
    """A stored check still matches the block (the methodist may have changed it since)."""
    return bool(saved) and len(saved.get("results") or []) == len(b.content.get("questions") or [])


def _score_percent(les: CourseLesson, p: LessonProgress) -> float | None:
    values = []
    for b in exercise_blocks(les):
        saved = p.blocks.get(str(b.id))
        if _valid_check(b, saved) and saved["max"]:
            values.append(100 * saved["best"] / saved["max"])
    return round(sum(values) / len(values), 1) if values else None


def lesson_view(db: Session, student: StudentProfile, lesson_id: int) -> StudentLessonView:
    les, a = lesson_access(db, student, lesson_id)
    p = progress_rows(db, student.id, [les.id]).get(les.id)
    view = cs.lesson_view(db, student.user, les.id)
    order = scope_lessons(a)
    i = next(k for k, x in enumerate(order) if x.id == les.id)
    view.path.prev_id = order[i - 1].id if i > 0 else None
    view.path.next_id = order[i + 1].id if i + 1 < len(order) else None
    blocks = []
    for b in exercise_blocks(les):
        saved = (p.blocks if p else {}).get(str(b.id))
        if not _valid_check(b, saved):
            continue
        results = [QuestionResult(**r) for r in saved["results"]]
        blocks.append(BlockState(
            block_id=b.id,
            answers={int(k): v for k, v in (saved.get("answers") or {}).items()},
            result=CheckResult(results=results, questions=lb.view_questions(b.id, b.content, True),
                               score=saved["score"], max_score=saved["max"]),
            attempts=saved.get("attempts", 1),
            best_percent=round(100 * saved["best"] / saved["max"]) if saved["max"] else None,
        ))
    return StudentLessonView(
        lesson=view, assignment_id=a.id, status=state(p),  # type: ignore[arg-type]
        completed_at=p.completed_at if p else None,
        score_percent=round(p.score_percent) if p and p.score_percent is not None else None,
        exercises_total=len(exercise_blocks(les)), exercises_done=len(blocks), blocks=blocks,
        plays={int(k): v for k, v in (p.plays if p else {}).items()},
    )


def check_block(db: Session, student: StudentProfile, lesson_id: int, block_id: int,
                answers: dict[int, list[str]]) -> CheckResult:
    les, _ = lesson_access(db, student, lesson_id)
    b = next((x for x in les.blocks if x.id == block_id), None)
    if b is None or b.type not in lb.EXERCISES:
        raise NotFound("Задание не найдено")
    raw = lb.check(b.id, b.content, answers)
    score = round(sum(r["points_awarded"] for r in raw), 2)
    max_score = sum(r["max_points"] for r in raw)
    p = _progress_for_update(db, student, les)
    old = p.blocks.get(str(b.id)) if _valid_check(b, p.blocks.get(str(b.id))) else None
    p.blocks = {**p.blocks, str(b.id): {
        "answers": {str(r["question_id"]): r["answer"] for r in raw},
        "results": raw,
        "score": score,
        "max": max_score,
        "best": max(score, old["best"]) if old else score,
        "attempts": (old.get("attempts", 0) if old else 0) + 1,
        "checked_at": now().isoformat(),
    }}
    p.lesson_title = les.title
    p.score_percent = _score_percent(les, p)
    p.updated_at = now()
    from app.services import gamification

    gamification.mark_activity(db, student)
    return CheckResult(results=[QuestionResult(**r) for r in raw], questions=lb.view_questions(b.id, b.content, True),
                       score=score, max_score=max_score)


def count_play(db: Session, student: StudentProfile, lesson_id: int, block_id: int) -> tuple[int, int | None]:
    """Count one listening of an audio/listening block (refused once the limit is used)."""
    les, _ = lesson_access(db, student, lesson_id)
    b = next((x for x in les.blocks if x.id == block_id), None)
    if b is None or b.type not in ("audio", "listening"):
        raise NotFound("Аудио не найдено")
    limit = b.content.get("max_plays")
    p = _progress_for_update(db, student, les)
    used = int(p.plays.get(str(b.id), 0))
    if limit is not None and used >= limit:
        raise BadRequest("Лимит прослушиваний исчерпан")
    p.plays = {**p.plays, str(b.id): used + 1}
    p.updated_at = now()
    return used + 1, limit


def complete_lesson(db: Session, student: StudentProfile, lesson_id: int) -> bool:
    """Mark the lesson completed once every exercise has been checked.
    Idempotent (the row is locked): returns True only the first time."""
    les, _ = lesson_access(db, student, lesson_id)
    p = _progress_for_update(db, student, les)
    if p.completed_at is not None:
        return False
    if any(not _valid_check(b, p.blocks.get(str(b.id))) for b in exercise_blocks(les)):
        raise BadRequest("Сначала выполните все упражнения урока")
    p.completed_at = now()
    p.updated_at = p.completed_at
    p.lesson_title = les.title
    p.score_percent = _score_percent(les, p)
    return True


# ---------- progress summaries ----------

def course_progress(db: Session, student: StudentProfile) -> CourseProgressOut:
    """"My progress": per course level (the assigned lessons of it), plus totals."""
    assignments = [a for a in student_assignments(db, student.id) if is_started(a)]
    all_rows = list(db.scalars(select(LessonProgress).where(LessonProgress.student_id == student.id)).all())
    progress = {p.lesson_id: p for p in all_rows if p.lesson_id is not None}
    # group the assigned modules by (course, level); a module may come from several assignments
    groups: dict[int, dict[int, CourseModule]] = defaultdict(dict)
    levels: dict[int, CourseLevel] = {}
    for a in assignments:
        lv = scope_level(a)
        levels[lv.id] = lv
        for m in scope_modules(a):
            groups[lv.id][m.id] = m
    items = []
    for level_id, mods in groups.items():
        lv = levels[level_id]
        ordered = sorted(mods.values(), key=lambda m: m.position)
        modules = _modules(ordered, progress)
        lessons = [x for m in modules for x in m.lessons]
        done = [x for x in lessons if x.status == "completed"]
        items.append(CourseProgressItem(
            course_id=lv.course_id, course_title=lv.course.title, level=lv.level, level_title=lv.title,
            lessons_total=len(lessons), lessons_completed=len(done), percent=_pct(len(done), len(lessons)),
            modules_total=len(modules), modules_completed=sum(1 for m in modules if m.completed),
            avg_score=_mean([x.score_percent for x in lessons if x.score_percent is not None]),
            modules=modules,
        ))
    items.sort(key=lambda i: (i.course_title, i.level))
    checked = [v for p in all_rows for v in (p.blocks or {}).values() if v.get("max")]
    total = sum(i.lessons_total for i in items)
    completed = sum(i.lessons_completed for i in items)
    return CourseProgressOut(
        english_level=student.english_level,
        lessons_completed=completed,
        lessons_remaining=total - completed,
        modules_completed=sum(i.modules_completed for i in items),
        exercises_done=len(checked),
        avg_score=_mean([100 * v["best"] / v["max"] for v in checked]),
        items=items,
    )


# ---------- teacher: assigning ----------

def _members(a: CourseAssignment, active_only: bool = True) -> list[CourseAssignmentStudent]:
    return [m for m in a.members if not active_only or m.removed_at is None]


def covered_students(db: Session, teacher: TeacherProfile, level: CourseLevel | None, module: CourseModule | None) -> set[int]:
    """Students who already have this level/module (or the level containing the module) from this teacher."""
    q = (
        select(CourseAssignmentStudent.student_id)
        .join(CourseAssignment, CourseAssignment.id == CourseAssignmentStudent.assignment_id)
        .where(CourseAssignment.teacher_id == teacher.id, CourseAssignment.removed_at.is_(None),
               CourseAssignmentStudent.removed_at.is_(None))
    )
    if level is not None:
        q = q.where(CourseAssignment.level_id == level.id)
    else:
        q = q.where((CourseAssignment.module_id == module.id) | (CourseAssignment.level_id == module.level_id))
    return set(db.scalars(q).all())


def assign(
    db: Session,
    teacher: TeacherProfile,
    course: Course,
    level: CourseLevel | None,
    module: CourseModule | None,
    students: list[StudentProfile],
    groups: list[Group],
    starts_at: datetime | None,
    due_at: datetime | None,
) -> AssignResult:
    """One assignment per group (later members get it too) and one for the
    students picked by name. Students who already have it are skipped."""
    lessons = [x for m in ([module] if module else level.modules) for x in m.lessons if x.published]
    if not lessons:
        raise BadRequest("В выбранной части курса пока нет опубликованных уроков")
    starts = starts_at or now()
    if due_at and due_at <= starts:
        raise BadRequest("Срок должен быть позже даты начала")
    taken = covered_students(db, teacher, level, module)
    created: list[CourseAssignment] = []
    got: dict[int, StudentProfile] = {}
    skipped: set[int] = set()

    def make(group: Group | None, members: list[StudentProfile]) -> None:
        fresh = [s for s in members if s.id not in taken]
        skipped.update(s.id for s in members if s.id in taken)
        # nobody new: no assignment (an empty group still gets one: its future members will have it)
        if not fresh and (group is None or members):
            return
        a = CourseAssignment(teacher_id=teacher.id, course_id=course.id, level_id=level.id if level else None,
                             module_id=module.id if module else None, group_id=group.id if group else None,
                             starts_at=starts, due_at=due_at)
        a.members = [CourseAssignmentStudent(student_id=s.id) for s in fresh]
        db.add(a)
        created.append(a)
        for s in fresh:
            taken.add(s.id)
            got[s.id] = s

    for g in groups:
        make(g, list(g.students))
    individual = [s for s in students if s.id not in got]
    if individual:
        make(None, individual)
    db.flush()
    if got:
        part = level.title if level else module.title
        notify(db, [s.user_id for s in got.values()], NotificationType.COURSE_ASSIGNED,
               M("Новый курс: {course}", course=course.title), M("Назначено: {part}", part=part),
               link="/student/courses")
    return AssignResult(assignment_ids=[a.id for a in created], assigned=len(got), skipped=len(skipped - set(got)))


def add_members(db: Session, a: CourseAssignment, students: list[StudentProfile]) -> list[StudentProfile]:
    """Add (or bring back) students; returns those who were not active members."""
    rows = {m.student_id: m for m in a.members}
    added = []
    for s in students:
        m = rows.get(s.id)
        if m is None:
            a.members.append(CourseAssignmentStudent(student_id=s.id))
            added.append(s)
        elif m.removed_at is not None:
            m.removed_at = None
            m.added_at = now()
            added.append(s)
    return added


def remove_members(a: CourseAssignment, student_ids: set[int]) -> int:
    count = 0
    for m in a.members:
        if m.student_id in student_ids and m.removed_at is None:
            m.removed_at = now()
            count += 1
    return count


def sync_group_members(db: Session, group: Group, added: list[StudentProfile], removed: set[int]) -> None:
    """Group membership changed: new members get the group's course assignments,
    those who left are taken off them (their progress stays)."""
    if not added and not removed:
        return
    q = select(CourseAssignment).where(CourseAssignment.group_id == group.id, CourseAssignment.removed_at.is_(None))
    for a in db.scalars(q).all():
        if added:
            add_members(db, a, added)
        if removed:
            remove_members(a, removed)


# ---------- teacher: overviews ----------

def _member_rows(db: Session, a: CourseAssignment) -> list[AssignmentStudentRow]:
    lessons = scope_lessons(a)
    ids = [x.id for x in lessons]
    rows = []
    for m in sorted(a.members, key=lambda m: (m.removed_at is not None, m.student.user.full_name)):
        progress = progress_rows(db, m.student_id, ids)
        done = [p for p in progress.values() if p.completed_at]
        scores = [p.score_percent for p in progress.values() if p.score_percent is not None]
        rows.append(AssignmentStudentRow(
            student_id=m.student_id, full_name=m.student.user.full_name, removed_at=m.removed_at,
            lessons_completed=len(done), lessons_total=len(lessons), percent=_pct(len(done), len(lessons)),
            avg_score=_mean(scores), last_activity=max((p.updated_at for p in progress.values()), default=None),
        ))
    return rows


def assignment_item(db: Session, a: CourseAssignment, rows: list[AssignmentStudentRow] | None = None) -> AssignmentItem:
    rows = rows if rows is not None else _member_rows(db, a)
    active = [r for r in rows if r.removed_at is None]
    return AssignmentItem(
        id=a.id, course_id=a.course_id, course_title=a.course.title, scope="level" if a.level_id else "module",
        scope_title=scope_title(a), level=scope_level(a).level, group_id=a.group_id,
        group_name=a.group.name if a.group else None, students_count=len(active),
        starts_at=a.starts_at, due_at=a.due_at, removed_at=a.removed_at, created_at=a.created_at,
        lessons_total=len(scope_lessons(a)), avg_percent=_mean([r.percent for r in active]),
        completed_count=sum(1 for r in active if r.lessons_total and r.lessons_completed == r.lessons_total),
    )


def assignment_detail(db: Session, a: CourseAssignment) -> AssignmentDetail:
    rows = _member_rows(db, a)
    return AssignmentDetail(**assignment_item(db, a, rows).model_dump(), students=rows)


def teacher_assignments(db: Session, teacher: TeacherProfile, include_removed: bool) -> list[CourseAssignment]:
    q = select(CourseAssignment).where(CourseAssignment.teacher_id == teacher.id)
    if not include_removed:
        q = q.where(CourseAssignment.removed_at.is_(None))
    return list(db.scalars(q.order_by(CourseAssignment.created_at.desc(), CourseAssignment.id.desc())).all())


def get_teacher_assignment(db: Session, teacher: TeacherProfile, assignment_id: int) -> CourseAssignment:
    a = db.get(CourseAssignment, assignment_id)
    if a is None or a.teacher_id != teacher.id:
        raise NotFound("Назначение не найдено")
    return a


def students_overview(db: Session, teacher: TeacherProfile) -> list[StudentProgressRow]:
    """Each of the teacher's students with active course assignments from them."""
    per: dict[int, dict[str, Any]] = {}
    for a in teacher_assignments(db, teacher, include_removed=False):
        lessons = [x.id for x in scope_lessons(a)]
        for m in _members(a):
            if m.student.teacher_id != teacher.id:
                continue  # moved to another teacher
            d = per.setdefault(m.student_id, {"student": m.student, "assignments": 0, "lessons": set()})
            d["assignments"] += 1
            d["lessons"].update(lessons)
    rows = []
    for sid, d in per.items():
        progress = progress_rows(db, sid, list(d["lessons"]))
        done = sum(1 for p in progress.values() if p.completed_at)
        total = len(d["lessons"])
        s = d["student"]
        rows.append(StudentProgressRow(
            student_id=sid, full_name=s.user.full_name, english_level=s.english_level, assignments=d["assignments"],
            lessons_completed=done, lessons_total=total, percent=_pct(done, total),
            avg_score=_mean([p.score_percent for p in progress.values() if p.score_percent is not None]),
            last_activity=max((p.updated_at for p in progress.values()), default=None),
        ))
    return sorted(rows, key=lambda r: r.full_name)


def assert_not_assigned(db: Session, *, course_id: int | None = None, level_id: int | None = None,
                        module_id: int | None = None) -> None:
    """Courses, levels and modules students are working on can't be deleted (lessons can)."""
    q = select(CourseAssignment.id).where(CourseAssignment.removed_at.is_(None))
    if course_id is not None:
        q = q.where(CourseAssignment.course_id == course_id)
    elif level_id is not None:
        module_ids = select(CourseModule.id).where(CourseModule.level_id == level_id)
        q = q.where((CourseAssignment.level_id == level_id) | CourseAssignment.module_id.in_(module_ids))
    else:
        q = q.where(CourseAssignment.module_id == module_id)
    if db.scalars(q.limit(1)).first() is not None:
        raise BadRequest("Эта часть курса назначена ученикам — удалить её нельзя. Можно снять уроки с публикации")

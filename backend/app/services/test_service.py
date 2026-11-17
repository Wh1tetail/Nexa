"""Test grading logic."""
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentProfile, Test, TestAnswer, TestAttempt, TestQuestion
from app.core.exceptions import BadRequest
from app.core.i18n import M
from app.models.enums import CONTENT_TYPES, AttemptStatus, NotificationType, QuestionType
from app.models.test import test_assignments
from app.schemas.test import (
    AnswerOut,
    AttemptDetail,
    AttemptSummary,
    OptionIn,
    QuestionIn,
    QuestionOut,
    StudentTestItem,
)
from app.services import task_types
from app.services.notification_service import notify

TIME_GRACE = timedelta(seconds=60)


def normalize_text(s: str) -> str:
    return " ".join(s.strip().lower().replace("’", "'").split()).rstrip(".!")


def check_attachment_ids(test: Test, questions: list[QuestionIn]) -> None:
    """Questions may only show files of this very test; an audio block needs an
    audio file and a reading picture an image."""
    own = {f.id: f for f in test.files}
    for q in questions:
        if not set(q.attachment_ids) <= set(own):
            raise BadRequest("Файл к вопросу не найден среди материалов теста")
        for fid in task_types.file_ids(q.type, q.config):
            f = own.get(fid)
            if f is None:
                raise BadRequest("Файл к вопросу не найден среди материалов теста")
            kind = "audio/" if q.type == QuestionType.AUDIO else "image/"
            if not f.mime_type.startswith(kind):
                raise BadRequest("Для аудиоблока нужен аудиофайл, для текста — изображение")


def build_questions(test: Test, questions: list[QuestionIn]) -> None:
    check_attachment_ids(test, questions)
    test.questions.clear()
    for i, q in enumerate(questions):
        test.questions.append(
            TestQuestion(
                position=i,
                type=q.type,
                text=q.text,
                options=[o.model_dump() for o in q.options],
                correct_answer=q.correct_answer,
                points=q.points,
                explanation=q.explanation,
                attachment_ids=q.attachment_ids,
                config=q.config,
            )
        )


def apply_settings(test: Test, data) -> None:
    test.available_from = data.available_from
    test.shuffle_questions = data.shuffle_questions
    test.shuffle_options = data.shuffle_options
    test.show_correct_answers = data.show_correct_answers
    test.passing_percent = data.passing_percent
    test.max_attempts = data.max_attempts


def settings_of(test: Test) -> dict:
    return {
        "available_from": test.available_from,
        "shuffle_questions": test.shuffle_questions,
        "shuffle_options": test.shuffle_options,
        "show_correct_answers": test.show_correct_answers,
        "passing_percent": test.passing_percent,
        "max_attempts": test.max_attempts,
    }


def is_available(test: Test, now: datetime | None = None) -> bool:
    return test.available_from is None or test.available_from <= (now or datetime.now(UTC))


def auto_grade(question: Any, answer: list[str]) -> tuple[bool | None, float | None]:
    """Returns (is_correct, points). (None, None) means manual review needed."""
    if question.type in (QuestionType.FILL_GAPS, QuestionType.MATCHING):
        return task_types.grade(question.type, question.config, question.points, answer)
    if question.type == QuestionType.SHORT_ANSWER:
        given = normalize_text(answer[0]) if answer else ""
        accepted = {normalize_text(a) for a in question.correct_answer}
        if given and given in accepted:
            return True, float(question.points)
        if not given:
            return False, 0.0
        return None, None  # teacher decides
    correct = set(question.correct_answer)
    ok = set(answer) == correct
    return ok, float(question.points) if ok else 0.0


def deadline(attempt: TestAttempt) -> datetime | None:
    if attempt.test.time_limit_minutes:
        return attempt.started_at + timedelta(minutes=attempt.test.time_limit_minutes)
    return None


def is_time_over(attempt: TestAttempt) -> bool:
    d = deadline(attempt)
    return bool(d and datetime.now(UTC) > d + TIME_GRACE)


def clean_value(q: Any, value: list[str]) -> list[str]:
    """A student's answer reduced to what the question accepts (q: a test question
    or anything shaped like one, e.g. a lesson exercise)."""
    if q.type in (QuestionType.FILL_GAPS, QuestionType.MATCHING):
        return task_types.clean_answer(q.type, q.config, value)
    if q.type == QuestionType.SHORT_ANSWER:
        return [str(value[0])[:2000]] if value else []
    valid = {o["id"] for o in q.options}
    value = [v for v in dict.fromkeys(value) if v in valid]
    if q.type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE):
        value = value[:1]
    return value


def save_answers(attempt: TestAttempt, answers: dict[int, list[str]]) -> None:
    questions = {q.id: q for q in attempt.test.questions}
    existing = {a.question_id: a for a in attempt.answers}
    for qid, value in answers.items():
        if qid not in questions:
            continue
        q = questions[qid]
        if q.type in CONTENT_TYPES:
            continue  # blocks take no answers
        value = clean_value(q, value)
        if qid in existing:
            existing[qid].answer = value
        else:
            attempt.answers.append(TestAnswer(question_id=qid, answer=value))


def finalize(db: Session, attempt: TestAttempt, answers: dict[int, list[str]]) -> None:
    save_answers(attempt, answers)
    db.flush()
    existing = {a.question_id: a for a in attempt.answers}
    scored = [q for q in attempt.test.questions if q.type not in CONTENT_TYPES]
    for q in scored:
        if q.id not in existing:
            attempt.answers.append(TestAnswer(question_id=q.id, answer=[]))
    db.flush()
    by_q = {a.question_id: a for a in attempt.answers}
    needs_review = False
    for q in scored:
        ans = by_q[q.id]
        ans.is_correct, ans.points_awarded = auto_grade(q, ans.answer)
        if ans.points_awarded is None:
            needs_review = True
    now = datetime.now(UTC)
    attempt.submitted_at = now
    attempt.max_score = float(sum(q.points for q in attempt.test.questions))
    recompute_score(attempt)
    if needs_review:
        attempt.status = AttemptStatus.PENDING_REVIEW
    else:
        attempt.status = AttemptStatus.GRADED
        attempt.graded_at = now
    student: StudentProfile = attempt.student
    notify(
        db,
        [attempt.test.teacher.user_id],
        NotificationType.TEST_COMPLETED,
        M("Тест пройден"),
        M(
            "{name} завершил(а) тест «{title}» — требуется проверка" if needs_review
            else "{name} завершил(а) тест «{title}»",
            name=student.user.full_name, title=attempt.test.title,
        ),
        f"/teacher/tests/{attempt.test_id}/attempts/{attempt.id}",
    )
    if not needs_review:
        notify_graded(db, attempt)
    from app.services import gamification

    gamification.mark_activity(db, student)  # a learning day
    if not needs_review:
        gamification.on_test_graded(db, attempt)


def recompute_score(attempt: TestAttempt) -> None:
    attempt.score = float(sum(a.points_awarded or 0 for a in attempt.answers))


def notify_graded(db: Session, attempt: TestAttempt) -> None:
    pct = percent(attempt)
    notify(
        db,
        [attempt.student.user_id],
        NotificationType.TEST_GRADED,
        M("Результаты теста"),
        f"«{attempt.test.title}»: {pct}%",
        f"/student/tests/attempts/{attempt.id}",
    )


def percent(attempt: TestAttempt) -> int | None:
    if attempt.score is None or not attempt.max_score:
        return None
    return round(attempt.score * 100 / attempt.max_score)


def passed(attempt: TestAttempt) -> bool | None:
    """Pass/fail once graded; None when the test has no passing score."""
    pct = percent(attempt)
    if attempt.status != AttemptStatus.GRADED or attempt.test.passing_percent is None or pct is None:
        return None
    return pct >= attempt.test.passing_percent


def question_out(
    q: TestQuestion, reveal: bool, option_order: random.Random | None = None, seed: str | None = None
) -> QuestionOut:
    options = [OptionIn(**o) for o in q.options]
    if option_order is not None and q.type != QuestionType.TRUE_FALSE:
        option_order.shuffle(options)
    return QuestionOut(
        id=q.id,
        position=q.position,
        type=q.type,
        text=q.text,
        options=options,
        correct_answer=list(q.correct_answer) if reveal else None,
        points=q.points,
        explanation=q.explanation if reveal else None,
        attachment_ids=list(q.attachment_ids or []),
        config=task_types.public_config(q.type, q.config or {}, reveal, seed or f"q-{q.id}"),
    )


def ordered_questions(attempt: TestAttempt) -> list[tuple[TestQuestion, random.Random | None]]:
    """The order a student sees: stable for the attempt (seeded by its id),
    so reloading the page never reshuffles."""
    test = attempt.test
    questions = list(test.questions)
    if test.shuffle_questions:
        # audio / reading blocks stay in place; questions are shuffled only
        # within the part that follows each block (they belong to it)
        rng = random.Random(f"q-{attempt.id}")
        out, part = [], []
        for q in questions:
            if q.type in CONTENT_TYPES:
                rng.shuffle(part)
                out += part + [q]
                part = []
            else:
                part.append(q)
        rng.shuffle(part)
        questions = out + part
    return [
        (q, random.Random(f"o-{attempt.id}-{q.id}") if test.shuffle_options else None)
        for q in questions
    ]


def attempt_summary(a: TestAttempt) -> AttemptSummary:
    graded = a.status == AttemptStatus.GRADED
    return AttemptSummary(
        id=a.id,
        test_id=a.test_id,
        test_title=a.test.title,
        student_id=a.student_id,
        student_name=a.student.user.full_name,
        number=a.number,
        status=a.status,
        started_at=a.started_at,
        submitted_at=a.submitted_at,
        score=a.score if graded else None,
        max_score=a.max_score or float(sum(q.points for q in a.test.questions)),
        percent=percent(a) if graded else None,
        passed=passed(a),
    )


def attempt_detail(a: TestAttempt, for_teacher: bool) -> AttemptDetail:
    from app.schemas.homework import AttachmentOut

    graded = a.status == AttemptStatus.GRADED
    # the score is always shown once graded; correct answers only if the teacher allows it
    show_score = for_teacher or graded
    reveal = for_teacher or (graded and a.test.show_correct_answers)
    summary = attempt_summary(a)
    if for_teacher and a.score is not None:
        summary.score = a.score
        summary.percent = percent(a)
    answers = [
        AnswerOut(
            id=x.id,
            question_id=x.question_id,
            answer=x.answer,
            is_correct=x.is_correct if show_score else None,
            points_awarded=x.points_awarded if show_score else None,
            teacher_comment=x.teacher_comment if show_score else None,
        )
        for x in a.answers
    ]
    if for_teacher:
        questions = [question_out(q, reveal) for q in a.test.questions]
    else:
        questions = [question_out(q, reveal, order, seed=f"{a.id}-{q.id}") for q, order in ordered_questions(a)]
    return AttemptDetail(
        **summary.model_dump(),
        time_limit_minutes=a.test.time_limit_minutes,
        deadline_at=deadline(a),
        passing_percent=a.test.passing_percent,
        show_correct_answers=a.test.show_correct_answers,
        questions=questions,
        answers=answers,
        files=[AttachmentOut.model_validate(f) for f in a.test.files],
        plays={int(k): v for k, v in (a.plays or {}).items()},
    )


# ---------- attempts (several per student; the best result counts) ----------

def attempts_of(db: Session, student_id: int, test_ids: list[int] | None = None) -> dict[int, list[TestAttempt]]:
    """Attempts by test id, oldest first."""
    q = select(TestAttempt).where(TestAttempt.student_id == student_id).order_by(TestAttempt.number)
    if test_ids is not None:
        q = q.where(TestAttempt.test_id.in_(test_ids))
    out: dict[int, list[TestAttempt]] = {}
    for a in db.scalars(q).all():
        out.setdefault(a.test_id, []).append(a)
    return out


def extra_attempts(db: Session, student_id: int) -> dict[int, int]:
    """Extra attempts the teacher allowed, by test id."""
    rows = db.execute(
        select(test_assignments.c.test_id, test_assignments.c.extra_attempts)
        .where(test_assignments.c.student_id == student_id)
    ).all()
    return {test_id: extra for test_id, extra in rows}


def can_start(test: Test, attempts: list[TestAttempt], extra: int, now: datetime | None = None) -> bool:
    """A new attempt may begin: none unfinished, attempts left, the test is open.
    An attempt the teacher added on top of max_attempts ignores the deadline."""
    now = now or datetime.now(UTC)
    if attempts and attempts[-1].status == AttemptStatus.IN_PROGRESS:
        return False
    if len(attempts) >= test.max_attempts + extra or not is_available(test, now):
        return False
    granted_by_teacher = len(attempts) >= test.max_attempts
    return granted_by_teacher or not (test.due_at and test.due_at < now)


def best_attempt(attempts: list[TestAttempt]) -> TestAttempt | None:
    graded = [a for a in attempts if a.status == AttemptStatus.GRADED and percent(a) is not None]
    return max(graded, key=lambda a: (percent(a), a.number)) if graded else None


def student_item(test: Test, attempts: list[TestAttempt], extra: int = 0) -> StudentTestItem:
    now = datetime.now(UTC)
    attempt = attempts[-1] if attempts else None
    graded = attempt is not None and attempt.status == AttemptStatus.GRADED
    done = attempt is not None and attempt.status != AttemptStatus.IN_PROGRESS
    retake = bool(attempts) and can_start(test, attempts, extra, now)
    best = best_attempt(attempts)
    return StudentTestItem(
        test_id=test.id,
        title=test.title,
        description=test.description,
        time_limit_minutes=test.time_limit_minutes,
        due_at=test.due_at,
        available_from=test.available_from,
        is_available=is_available(test, now),
        passing_percent=test.passing_percent,
        passed=passed(attempt) if attempt else None,
        questions_count=sum(1 for q in test.questions if q.type not in CONTENT_TYPES),
        is_overdue=bool(test.due_at and test.due_at < now and not done and not retake),
        attempt_id=attempt.id if attempt else None,
        attempt_status=attempt.status if attempt else None,
        score=attempt.score if graded else None,
        max_score=attempt.max_score if graded else None,
        percent=percent(attempt) if graded else None,
        submitted_at=attempt.submitted_at if attempt else None,
        attempts_used=len(attempts),
        attempts_allowed=test.max_attempts + extra,
        can_retake=retake,
        best_percent=percent(best) if best else None,
    )


def assign_students(db: Session, test: Test, students: list[StudentProfile]) -> int:
    """Assign students (an excluded one is restored with their attempts); notifies the new ones."""
    from app.services import participation

    db.flush()
    new = participation.assign_test(db, test.id, students)
    db.expire(test, ["students"])
    for s in new:
        notify(
            db,
            [s.user_id],
            NotificationType.TEST_ASSIGNED,
            M("Новый тест"),
            test.title,
            "/student/tests",
        )
    return len(new)

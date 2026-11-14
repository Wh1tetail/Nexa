"""Test grading logic."""
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import StudentProfile, Test, TestAnswer, TestAttempt, TestQuestion
from app.core.exceptions import BadRequest
from app.core.i18n import M
from app.models.enums import AttemptStatus, NotificationType, QuestionType
from app.schemas.test import (
    AnswerOut,
    AttemptDetail,
    AttemptSummary,
    OptionIn,
    QuestionIn,
    QuestionOut,
    StudentTestItem,
)
from app.services.notification_service import notify

TIME_GRACE = timedelta(seconds=60)


def normalize_text(s: str) -> str:
    return " ".join(s.strip().lower().replace("’", "'").split()).rstrip(".!")


def check_attachment_ids(test: Test, questions: list[QuestionIn]) -> None:
    """Questions may only show files of this very test."""
    own = {f.id for f in test.files}
    for q in questions:
        if not set(q.attachment_ids) <= own:
            raise BadRequest("Файл к вопросу не найден среди материалов теста")


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
            )
        )


def apply_settings(test: Test, data) -> None:
    test.available_from = data.available_from
    test.shuffle_questions = data.shuffle_questions
    test.shuffle_options = data.shuffle_options
    test.show_correct_answers = data.show_correct_answers
    test.passing_percent = data.passing_percent


def settings_of(test: Test) -> dict:
    return {
        "available_from": test.available_from,
        "shuffle_questions": test.shuffle_questions,
        "shuffle_options": test.shuffle_options,
        "show_correct_answers": test.show_correct_answers,
        "passing_percent": test.passing_percent,
    }


def is_available(test: Test, now: datetime | None = None) -> bool:
    return test.available_from is None or test.available_from <= (now or datetime.now(UTC))


def auto_grade(question: TestQuestion, answer: list[str]) -> tuple[bool | None, float | None]:
    """Returns (is_correct, points). (None, None) means manual review needed."""
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


def save_answers(attempt: TestAttempt, answers: dict[int, list[str]]) -> None:
    questions = {q.id: q for q in attempt.test.questions}
    existing = {a.question_id: a for a in attempt.answers}
    for qid, value in answers.items():
        if qid not in questions:
            continue
        q = questions[qid]
        if q.type != QuestionType.SHORT_ANSWER:
            valid = {o["id"] for o in q.options}
            value = [v for v in dict.fromkeys(value) if v in valid]
            if q.type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE):
                value = value[:1]
        else:
            value = [value[0][:2000]] if value else []
        if qid in existing:
            existing[qid].answer = value
        else:
            attempt.answers.append(TestAnswer(question_id=qid, answer=value))


def finalize(db: Session, attempt: TestAttempt, answers: dict[int, list[str]]) -> None:
    save_answers(attempt, answers)
    db.flush()
    existing = {a.question_id: a for a in attempt.answers}
    for q in attempt.test.questions:
        if q.id not in existing:
            attempt.answers.append(TestAnswer(question_id=q.id, answer=[]))
    db.flush()
    by_q = {a.question_id: a for a in attempt.answers}
    needs_review = False
    for q in attempt.test.questions:
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


def question_out(q: TestQuestion, reveal: bool, option_order: random.Random | None = None) -> QuestionOut:
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
    )


def ordered_questions(attempt: TestAttempt) -> list[tuple[TestQuestion, random.Random | None]]:
    """The order a student sees: stable for the attempt (seeded by its id),
    so reloading the page never reshuffles."""
    test = attempt.test
    questions = list(test.questions)
    if test.shuffle_questions:
        random.Random(f"q-{attempt.id}").shuffle(questions)
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
        questions = [question_out(q, reveal, order) for q, order in ordered_questions(a)]
    return AttemptDetail(
        **summary.model_dump(),
        time_limit_minutes=a.test.time_limit_minutes,
        deadline_at=deadline(a),
        passing_percent=a.test.passing_percent,
        show_correct_answers=a.test.show_correct_answers,
        questions=questions,
        answers=answers,
        files=[AttachmentOut.model_validate(f) for f in a.test.files],
    )


def student_item(test: Test, attempt: TestAttempt | None) -> StudentTestItem:
    now = datetime.now(UTC)
    graded = attempt is not None and attempt.status == AttemptStatus.GRADED
    done = attempt is not None and attempt.status != AttemptStatus.IN_PROGRESS
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
        questions_count=len(test.questions),
        is_overdue=bool(test.due_at and test.due_at < now and not done),
        attempt_id=attempt.id if attempt else None,
        attempt_status=attempt.status if attempt else None,
        score=attempt.score if graded else None,
        max_score=attempt.max_score if graded else None,
        percent=percent(attempt) if graded else None,
        submitted_at=attempt.submitted_at if attempt else None,
    )


def assign_students(db: Session, test: Test, students: list[StudentProfile]) -> int:
    current = {s.id for s in test.students}
    new = [s for s in students if s.id not in current]
    test.students.extend(new)
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

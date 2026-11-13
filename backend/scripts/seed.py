"""Demo seed data. Run:  python -m scripts.seed  [--reset]

Creates an admin, two teachers, students with subscriptions in every state,
groups, past & upcoming lessons with attendance, homework and tests.
All demo accounts use the password from DEMO_PASSWORD below.
"""
import argparse
import random
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    Attendance,
    Group,
    Homework,
    HomeworkSubmission,
    Lesson,
    StudentProfile,
    Subscription,
    TeacherProfile,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import (
    AttendanceStatus,
    EnglishLevel,
    LessonStatus,
    QuestionType,
    SubmissionStatus,
    UserRole,
)
from app.schemas.test import QuestionIn
from app.services import attendance_service, test_service
from app.services.notification_service import notify
from app.models.enums import NotificationType

DEMO_PASSWORD = "Demo12345"

STUDENTS = [
    ("Анна Смирнова", "anna@lingua.school", EnglishLevel.B1, "+7 900 111-22-33"),
    ("Дмитрий Козлов", "dmitry@lingua.school", EnglishLevel.A2, "+7 900 222-33-44"),
    ("Мария Иванова", "maria@lingua.school", EnglishLevel.B2, "+7 900 333-44-55"),
    ("Игорь Петров", "igor@lingua.school", EnglishLevel.A1, "+7 900 444-55-66"),
    ("Елена Волкова", "elena@lingua.school", EnglishLevel.C1, "+7 900 555-66-77"),
    ("Сергей Новиков", "sergey@lingua.school", EnglishLevel.B1, "+7 900 666-77-88"),
    ("Ольга Морозова", "olga@lingua.school", EnglishLevel.A2, "+7 900 777-88-99"),
]


def reset_db() -> None:
    with engine.begin() as conn:
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def main(reset: bool) -> None:
    if reset:
        reset_db()
    random.seed(42)
    db = SessionLocal()
    if db.query(User).count():
        print("Database is not empty - use --reset to recreate demo data.")
        return
    pw = hash_password(DEMO_PASSWORD)
    today = datetime.now(UTC).date()
    now = datetime.now(UTC)

    admin = User(email="admin@lingua.school", password_hash=pw, full_name="Администратор", role=UserRole.ADMIN)
    t_user = User(email="teacher@lingua.school", password_hash=pw, full_name="Екатерина Соколова",
                  phone="+7 900 000-00-01", role=UserRole.TEACHER)
    teacher = TeacherProfile(user=t_user, bio="CELTA, 8 лет преподавания")
    t2_user = User(email="teacher2@lingua.school", password_hash=pw, full_name="Джон Уилсон", role=UserRole.TEACHER)
    teacher2 = TeacherProfile(user=t2_user, bio="Native speaker")
    db.add_all([admin, t_user, teacher, t2_user, teacher2])
    db.flush()

    students: list[StudentProfile] = []
    for i, (name, email, level, phone) in enumerate(STUDENTS):
        u = User(email=email, password_hash=pw, full_name=name, phone=phone, role=UserRole.STUDENT,
                 created_at=now - timedelta(days=120 - i * 9))
        sp = StudentProfile(user=u, teacher=teacher, english_level=level)
        db.add_all([u, sp])
        students.append(sp)
    # a student of the other teacher (to demonstrate isolation)
    other = User(email="peter@lingua.school", password_hash=pw, full_name="Пётр Лебедев", role=UserRole.STUDENT)
    db.add_all([other, StudentProfile(user=other, teacher=teacher2, english_level=EnglishLevel.B1)])
    db.flush()

    g1 = Group(teacher=teacher, name="Intermediate Evening", level=EnglishLevel.B1,
               description="Пн/Ср 19:00", students=[students[0], students[2], students[5]])
    g2 = Group(teacher=teacher, name="Elementary Kids", level=EnglishLevel.A2,
               description="Вт/Чт 17:00", students=[students[1], students[3], students[6]])
    db.add_all([g1, g2])

    # Subscriptions: every status
    sub_plan = [
        (-20, 40, 16, 6, False),   # active
        (-25, 5, 8, 6, False),     # expiring soon
        (-35, 25, 12, 5, False),   # active
        (-40, -3, 8, 8, False),    # expired
        (-10, 50, 24, 3, False),   # active
        (-30, 2, 8, 7, False),     # expiring soon
        (-15, 45, 12, 4, True),    # frozen
    ]
    for sp, (s_off, e_off, total, used, frozen) in zip(students, sub_plan, strict=True):
        db.add(Subscription(
            student=sp, teacher=teacher, title=f"{total} занятий",
            start_date=today + timedelta(days=s_off), end_date=today + timedelta(days=e_off),
            total_lessons=total, used_lessons=0, is_frozen=frozen,
            frozen_at=today - timedelta(days=3) if frozen else None,
        ))
    db.flush()

    # Lessons: past (with attendance) and upcoming
    def at(day: date, hour: int) -> datetime:
        return datetime.combine(day, time(hour, 0), tzinfo=UTC)

    topics = ["Present Perfect", "Phrasal verbs", "Conditionals", "Speaking: travel",
              "Listening practice", "Past Simple vs Past Continuous", "Vocabulary: work"]
    for k in range(6):
        day = today - timedelta(days=3 + k * 4)
        for group, hour in ((g1, 16), (g2, 14)):
            lesson = Lesson(teacher=teacher, group=group, title=group.name, topic=topics[k % len(topics)],
                            starts_at=at(day, hour), duration_minutes=60, status=LessonStatus.COMPLETED)
            db.add(lesson)
            for sp in group.students:
                row = Attendance(student=sp, lesson=lesson)
                lesson.attendance.append(row)
            db.flush()
            for row in lesson.attendance:
                st = random.choices(
                    [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED],
                    weights=[70, 12, 10, 8],
                )[0]
                attendance_service.apply_mark(db, row, st, "Опоздал на 10 минут" if st == AttendanceStatus.LATE else None)
    # individual past lesson for Елена
    ind = Lesson(teacher=teacher, title="Индивидуальное занятие", topic="Business English",
                 starts_at=at(today - timedelta(days=2), 11), status=LessonStatus.COMPLETED)
    db.add(ind)
    ind.attendance.append(Attendance(student=students[4]))
    db.flush()
    attendance_service.apply_mark(db, ind.attendance[0], AttendanceStatus.PRESENT, None)

    for k in range(1, 4):
        for group, hour in ((g1, 16), (g2, 14)):
            lesson = Lesson(teacher=teacher, group=group, title=group.name, topic=topics[(k + 2) % len(topics)],
                            starts_at=at(today + timedelta(days=k * 2 - 1), hour), duration_minutes=60,
                            meeting_url="https://meet.example.com/lingua")
            db.add(lesson)
            for sp in group.students:
                lesson.attendance.append(Attendance(student=sp))
    up = Lesson(teacher=teacher, title="Индивидуальное занятие", topic="Interview preparation",
                starts_at=at(today + timedelta(days=1), 11))
    up.attendance.append(Attendance(student=students[4]))
    db.add(up)
    db.flush()

    # Homework
    hw1 = Homework(teacher=teacher, title="Essay: My last vacation",
                   description="Напишите эссе на 150–200 слов, используя Past Simple и Past Continuous.\n\n"
                               "Прикрепите файл в формате DOCX или PDF.",
                   due_at=now + timedelta(days=3), max_grade=10, group=g1)
    hw2 = Homework(teacher=teacher, title="Workbook p. 34–35",
                   description="Выполните упражнения 1–5 в рабочей тетради. Сфотографируйте страницы.",
                   due_at=now + timedelta(days=1), max_grade=10, group=g2)
    hw3 = Homework(teacher=teacher, title="Vocabulary: 20 phrasal verbs",
                   description="Выучите 20 фразовых глаголов из списка и составьте с каждым предложение.",
                   due_at=now - timedelta(days=2), max_grade=10)
    db.add_all([hw1, hw2, hw3])
    db.flush()
    plan = {
        hw1.id: [(students[0], SubmissionStatus.SUBMITTED), (students[2], SubmissionStatus.REVIEWED),
                 (students[5], SubmissionStatus.NEW)],
        hw2.id: [(students[1], SubmissionStatus.IN_PROGRESS), (students[3], SubmissionStatus.NEW),
                 (students[6], SubmissionStatus.SUBMITTED)],
        hw3.id: [(students[0], SubmissionStatus.REVIEWED), (students[2], SubmissionStatus.NEEDS_REVISION),
                 (students[4], SubmissionStatus.REVIEWED), (students[5], SubmissionStatus.SUBMITTED)],
    }
    for hw in (hw1, hw2, hw3):
        for sp, st in plan[hw.id]:
            sub = HomeworkSubmission(homework=hw, student=sp, status=st)
            if st in (SubmissionStatus.SUBMITTED, SubmissionStatus.REVIEWED, SubmissionStatus.NEEDS_REVISION):
                sub.submitted_at = now - timedelta(hours=random.randint(2, 60))
                sub.student_comment = "Готово, проверьте пожалуйста!"
            if st == SubmissionStatus.REVIEWED:
                sub.grade = random.randint(7, 10)
                sub.teacher_comment = "Отличная работа! Обратите внимание на артикли."
                sub.reviewed_at = now - timedelta(hours=1)
            if st == SubmissionStatus.NEEDS_REVISION:
                sub.teacher_comment = "Добавьте ещё 5 предложений и исправьте ошибки во времени."
                sub.reviewed_at = now - timedelta(hours=3)
            db.add(sub)
    db.flush()

    # Tests
    test1 = Test(teacher=teacher, title="Present Perfect vs Past Simple",
                 description="Проверка темы прошлых уроков. 6 вопросов.", time_limit_minutes=15,
                 due_at=now + timedelta(days=5))
    db.add(test1)
    test_service.build_questions(test1, [
        QuestionIn(type=QuestionType.SINGLE_CHOICE, text="I ___ to London three times.",
                   options=[{"id": "a", "text": "have been"}, {"id": "b", "text": "was"}, {"id": "c", "text": "am"}],
                   correct_answer=["a"]),
        QuestionIn(type=QuestionType.SINGLE_CHOICE, text="She ___ the film yesterday.",
                   options=[{"id": "a", "text": "has watched"}, {"id": "b", "text": "watched"}, {"id": "c", "text": "watches"}],
                   correct_answer=["b"]),
        QuestionIn(type=QuestionType.MULTIPLE_CHOICE, text="Select the time markers used with Present Perfect:",
                   options=[{"id": "a", "text": "already"}, {"id": "b", "text": "yesterday"},
                            {"id": "c", "text": "ever"}, {"id": "d", "text": "last year"}],
                   correct_answer=["a", "c"], points=2),
        QuestionIn(type=QuestionType.TRUE_FALSE, text="«I have seen him last week» is grammatically correct.",
                   correct_answer=["false"]),
        QuestionIn(type=QuestionType.SHORT_ANSWER, text="Write the past participle of «go».",
                   correct_answer=["gone"]),
        QuestionIn(type=QuestionType.SHORT_ANSWER, text="Translate: «Я никогда не был в Париже».",
                   correct_answer=["I have never been to Paris"], points=2),
    ])
    test1.students = [students[0], students[2], students[4], students[5]]
    test2 = Test(teacher=teacher, title="Vocabulary check: Travel",
                 description="Короткий словарный тест.", time_limit_minutes=None, due_at=now + timedelta(days=10))
    db.add(test2)
    test_service.build_questions(test2, [
        QuestionIn(type=QuestionType.SINGLE_CHOICE, text="A place where planes land and take off:",
                   options=[{"id": "a", "text": "airport"}, {"id": "b", "text": "station"}, {"id": "c", "text": "harbour"}],
                   correct_answer=["a"]),
        QuestionIn(type=QuestionType.TRUE_FALSE, text="«Luggage» is a countable noun.", correct_answer=["false"]),
        QuestionIn(type=QuestionType.SHORT_ANSWER, text="The document you need to travel abroad (8 letters):",
                   correct_answer=["passport"]),
    ])
    test2.students = list(students[:4])
    db.flush()

    def take(test: Test, sp: StudentProfile, answers: list[list[str]], minutes_ago: int) -> TestAttempt:
        att = TestAttempt(test=test, student=sp, started_at=now - timedelta(minutes=minutes_ago + 12))
        db.add(att)
        db.flush()
        test_service.finalize(db, att, {q.id: a for q, a in zip(test.questions, answers, strict=True)})
        att.submitted_at = now - timedelta(minutes=minutes_ago)
        return att

    take(test1, students[2], [["a"], ["b"], ["a", "c"], ["false"], ["gone"], ["I have never been to Paris"]], 600)
    take(test1, students[0], [["a"], ["a"], ["a"], ["false"], ["gone"], ["I never was in Paris"]], 90)  # pending review
    take(test2, students[0], [["a"], ["true"], ["passport"]], 2000)
    take(test2, students[1], [["a"], ["false"], ["pasport"]], 300)  # pending review

    # A few extra notifications
    notify(db, [students[0].user_id], NotificationType.SYSTEM, "Добро пожаловать в Lingua!",
           "Здесь вы найдёте домашние задания, тесты и расписание.", "/student")
    for sp, hw in ((students[0], hw1), (students[5], hw1)):
        notify(db, [sp.user_id], NotificationType.HOMEWORK_ASSIGNED, "Новое домашнее задание", hw.title,
               "/student/homework")
    notify(db, [students[0].user_id], NotificationType.TEST_ASSIGNED, "Новый тест", test1.title, "/student/tests")
    notify(db, [t_user.id], NotificationType.HOMEWORK_SUBMITTED, "Сдано домашнее задание",
           f"Анна Смирнова: «{hw1.title}»", f"/teacher/homework/{hw1.id}")

    db.commit()
    from app.services.subscription_service import check_expirations
    check_expirations(db)
    db.close()
    print("Seed complete.")
    print(f"  Teacher: teacher@lingua.school / {DEMO_PASSWORD}")
    print(f"  Student: anna@lingua.school / {DEMO_PASSWORD}")
    print(f"  Admin:   admin@lingua.school / {DEMO_PASSWORD}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="truncate all tables first")
    main(parser.parse_args().reset)

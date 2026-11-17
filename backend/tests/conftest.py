"""Integration tests run against a real PostgreSQL database.

Set TEST_DATABASE_URL (defaults to <DATABASE_URL>_test). The schema is created
with Alembic migrations, so migrations are tested too.
"""
import os
from datetime import UTC, datetime, timedelta
import socket
import tempfile
import threading
import time

from dotenv_shim import load_env

load_env()  # populate os.environ from .env before reading DATABASE_URL

# conftest is imported twice (by pytest and by `from conftest import ...`), so remember
# the real application DB once instead of deriving from an already-rewritten value.
base_url = os.environ.setdefault("APP_DATABASE_URL", os.environ["DATABASE_URL"])
test_url = os.environ.get("TEST_DATABASE_URL") or base_url + "_test"  # e.g. .../Nexa -> .../Nexa_test
# The test DB is wiped (DROP SCHEMA public) on every run: never let it be the main DB.
if test_url.rstrip("/") == base_url.rstrip("/"):
    raise RuntimeError("TEST_DATABASE_URL must point to a separate database, not DATABASE_URL")
os.environ["DATABASE_URL"] = test_url
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"
os.environ["LOCAL_STORAGE_PATH"] = tempfile.mkdtemp(prefix="lms-test-")

import pytest  # noqa: E402
import uvicorn  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import StudentProfile, Subscription, TeacherProfile, User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402

PASSWORD = "Passw0rd!"


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean():
    with engine.begin() as conn:
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        # also clears auth_attempts (login limiter state)
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=15)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_user(role: UserRole, email: str, teacher: TeacherProfile | None = None, name: str = "User"):
    with SessionLocal() as db:
        u = User(email=email, password_hash=hash_password(PASSWORD), full_name=name, role=role)
        db.add(u)
        if role == UserRole.TEACHER:
            p = TeacherProfile(user=u)
        elif role == UserRole.STUDENT:
            p = StudentProfile(user=u, teacher_id=teacher.id if teacher else None)
        else:
            p = None
        if p:
            db.add(p)
        db.commit()
        if p:
            db.refresh(p)
        return u, p


def login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def school(client):
    """teacher A with 2 students, teacher B with 1 student."""
    _, ta = make_user(UserRole.TEACHER, "ta@test.io", name="Teacher A")
    _, tb = make_user(UserRole.TEACHER, "tb@test.io", name="Teacher B")
    _, s1 = make_user(UserRole.STUDENT, "s1@test.io", ta, "Student One")
    _, s2 = make_user(UserRole.STUDENT, "s2@test.io", ta, "Student Two")
    _, s3 = make_user(UserRole.STUDENT, "s3@test.io", tb, "Student Three")
    make_user(UserRole.ADMIN, "school-admin@test.io", name="School Admin")
    # students need an active subscription for lessons, homework and tests
    for s in (s1, s2, s3):
        give_subscription(s)
    adm = login(client, "school-admin@test.io")
    return {
        "ta": ta, "tb": tb, "s1": s1, "s2": s2, "s3": s3,
        "ha": login(client, "ta@test.io"), "hb": login(client, "tb@test.io"),
        "h1": login(client, "s1@test.io"), "h2": login(client, "s2@test.io"), "h3": login(client, "s3@test.io"),
        # the administrator creates students, groups and lessons for a teacher
        "adm": adm,
        "aa": {**adm, "X-Teacher-Id": str(ta.id)},
        "ab": {**adm, "X-Teacher-Id": str(tb.id)},
    }


def give_subscription(student: StudentProfile, days: int = 60, **fields) -> Subscription:
    """An active subscription (started yesterday) unless fields say otherwise."""
    today = datetime.now(UTC).date()
    with SessionLocal() as db:
        sub = Subscription(
            student_id=student.id, teacher_id=student.teacher_id,
            start_date=fields.pop("start_date", today - timedelta(days=1)),
            end_date=fields.pop("end_date", today + timedelta(days=days)),
            total_lessons=fields.pop("total_lessons", 8), **fields,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub


def clear_subscriptions(student: StudentProfile) -> None:
    """For tests that manage a student's subscriptions themselves."""
    with SessionLocal() as db:
        db.query(Subscription).filter_by(student_id=student.id).delete()
        db.commit()


# ---------- courses (stages 18-19) ----------

COURSES_API = "/api/v1"
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x0f" + b"\x00" * 64
CHOICE = {"type": "single_choice", "text": "She ___ to school.", "points": 1, "correct_answer": ["a"],
          "options": [{"id": "a", "text": "goes"}, {"id": "b", "text": "go"}]}
GAPS = {"type": "fill_gaps", "text": "Complete", "config": {"template": "I {am} Anna."}}


@pytest.fixture
def course(client, school):
    """A published course: A1 / Module 1 (Lesson 1 with exercises and a listening, Lesson 2 text only),
    Module 2 (one lesson) and a draft lesson."""
    make_user(UserRole.METHODIST, "method@test.io", name="Mila Methodist")
    hm = login(client, "method@test.io")
    c = client.post(f"{COURSES_API}/courses", headers=hm, json={"title": "General English", "levels": ["A1"], "published": True}).json()
    a1 = c["levels"][0]["id"]
    tree = client.post(f"{COURSES_API}/courses/levels/{a1}/modules", headers=hm, json={"title": "Introduction"}).json()
    tree = client.post(f"{COURSES_API}/courses/levels/{a1}/modules", headers=hm, json={"title": "Daily Life"}).json()
    m1, m2 = (m["id"] for m in tree["levels"][0]["modules"])

    def lesson(module, title, blocks, published=True):
        les = client.post(f"{COURSES_API}/courses/modules/{module}/lessons", headers=hm, json={"title": title}).json()
        r = client.put(f"{COURSES_API}/courses/lessons/{les['id']}", headers=hm,
                       json={"title": title, "published": published, "blocks": blocks(les["id"])})
        assert r.status_code == 200, r.text
        return r.json()

    def first_blocks(lid):
        f = client.post(f"{COURSES_API}/courses/lessons/{lid}/files", headers=hm,
                        files=[("files", ("hello.mp3", MP3, "audio/mpeg"))]).json()[0]["id"]
        return [{"type": "text", "content": {"body": "Hello"}},
                {"type": "quiz", "questions": [CHOICE, GAPS]},
                {"type": "listening", "content": {"attachment_id": f, "max_plays": 2}, "questions": [CHOICE]}]

    l1 = lesson(m1, "Greetings", first_blocks)
    l2 = lesson(m1, "Countries", lambda _: [{"type": "text", "content": {"body": "Spain"}}])
    l3 = lesson(m2, "Routine", lambda _: [{"type": "text", "content": {"body": "Every day"}}])
    draft = lesson(m1, "Draft", lambda _: [{"type": "text", "content": {"body": "x"}}], published=False)
    group = client.post(f"{COURSES_API}/groups", headers=school["aa"], json={"name": "A1 mornings", "student_ids": [school["s1"].id]}).json()
    return {**school, "hm": hm, "course": c["id"], "a1": a1, "m1": m1, "m2": m2,
            "l1": l1, "l2": l2, "l3": l3, "draft": draft, "group": group["id"]}


def _assign(client, h, course, **body):
    return client.post(f"{COURSES_API}/course-assignments", headers=h, json={"course_id": course["course"], **body})

"""Integration tests run against a real PostgreSQL database.

Set TEST_DATABASE_URL (defaults to <DATABASE_URL>_test). The schema is created
with Alembic migrations, so migrations are tested too.
"""
import os
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
from app.models import StudentProfile, TeacherProfile, User  # noqa: E402
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
    return {
        "ta": ta, "tb": tb, "s1": s1, "s2": s2, "s3": s3,
        "ha": login(client, "ta@test.io"), "hb": login(client, "tb@test.io"),
        "h1": login(client, "s1@test.io"), "h2": login(client, "s2@test.io"), "h3": login(client, "s3@test.io"),
    }

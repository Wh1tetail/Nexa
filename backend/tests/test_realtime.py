"""Real-time notifications: PostgreSQL NOTIFY -> listener -> SSE stream.

Runs a real uvicorn server in a thread (TestClient buffers streaming bodies),
opens the SSE stream like the browser does and checks that a notification
created by another user's action arrives live.
"""
import json
import socket
import threading
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import uvicorn
from conftest import login

from app.main import app
from app.services.realtime import broker

API = "/api/v1"


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


_LINES: dict[int, object] = {}


def _read_events(response: httpx.Response, wanted: str, timeout: float = 10) -> dict:
    """Read SSE frames until an event named `wanted` arrives."""
    lines = _LINES.setdefault(id(response), response.iter_lines())
    deadline = time.time() + timeout
    event, data = None, []
    for line in lines:
        if time.time() > deadline:
            break
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif line == "" and event:
            if event == wanted:
                return json.loads("".join(data))
            event, data = None, []
    raise AssertionError(f"event '{wanted}' not received")


def test_notification_is_pushed_live(client, school, live_server):
    student_headers = school["h1"]
    with httpx.Client(base_url=live_server, timeout=httpx.Timeout(15, read=15)) as http:
        with http.stream("GET", f"{API}/notifications/stream", headers=student_headers) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            _read_events(resp, "ready")
            assert broker.subscriber_count() >= 1

            # Teacher assigns homework (through the live server: another request, another thread)
            due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
            r = http.post(f"{API}/homework", headers=school["ha"],
                          json={"title": "Live essay", "due_at": due, "student_ids": [school["s1"].id]})
            assert r.status_code == 201

            note = _read_events(resp, "notification")
            assert note["type"] == "homework_assigned"
            assert note["body"] == "Live essay"
            assert note["link"].startswith("/student/homework/")
            # the event matches the persisted row
            saved = http.get(f"{API}/notifications", headers=student_headers).json()[0]
            assert saved["id"] == note["id"]


def test_stream_isolated_and_requires_auth(client, school, live_server):
    with httpx.Client(base_url=live_server, timeout=httpx.Timeout(10, read=4)) as http:
        assert http.get(f"{API}/notifications/stream").status_code == 401
        # student 2 listens; homework for student 1 must not reach them
        with http.stream("GET", f"{API}/notifications/stream", headers=school["h2"]) as resp:
            _read_events(resp, "ready")
            http.post(f"{API}/homework", headers=school["ha"], json={"title": "Private", "student_ids": [school["s1"].id]})
            with pytest.raises((AssertionError, httpx.ReadTimeout)):
                _read_events(resp, "notification", timeout=3)


def test_rolled_back_notification_is_not_sent(client, school):
    """pg_notify is transactional: nothing is delivered if the transaction rolls back."""
    import psycopg

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models import Notification
    from app.models.enums import NotificationType

    dsn = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("LISTEN lingua_notifications")
        with SessionLocal() as db:
            db.add(Notification(user_id=school["s1"].user_id, type=NotificationType.SYSTEM, title="rollback me"))
            db.flush()
            db.rollback()
            db.add(Notification(user_id=school["s1"].user_id, type=NotificationType.SYSTEM, title="committed"))
            db.commit()
        titles = [json.loads(n.payload)["notification"]["title"] for n in conn.notifies(timeout=2)]
    assert titles == ["committed"]


_ = login


# ---------- session revocation closes open streams immediately ----------

def _stream_ends(resp: httpx.Response) -> bool:
    """True if the server closes the stream after the current position."""
    lines = _LINES.setdefault(id(resp), resp.iter_lines())
    for _ in lines:
        pass
    return True


def test_logout_closes_open_stream(client, school, live_server):
    with httpx.Client(base_url=live_server, timeout=httpx.Timeout(10, read=10)) as http:
        with http.stream("GET", f"{API}/notifications/stream", headers=school["h1"]) as resp:
            _read_events(resp, "ready")
            assert http.post(f"{API}/auth/logout", headers=school["h1"]).status_code == 200
            _read_events(resp, "revoked", timeout=5)
            assert _stream_ends(resp)


def test_password_change_revokes_old_stream_but_not_new(client, school, live_server):
    from conftest import PASSWORD

    with httpx.Client(base_url=live_server, timeout=httpx.Timeout(10, read=10)) as http:
        with http.stream("GET", f"{API}/notifications/stream", headers=school["h1"]) as old:
            _read_events(old, "ready")
            r = http.post(f"{API}/auth/change-password", headers=school["h1"],
                          json={"current_password": PASSWORD, "new_password": "Brand123new"})
            assert r.status_code == 200
            _read_events(old, "revoked", timeout=5)
        new_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        with http.stream("GET", f"{API}/notifications/stream", headers=new_headers) as fresh:
            _read_events(fresh, "ready")
            http.post(f"{API}/homework", headers=school["ha"], json={"title": "Still live", "student_ids": [school["s1"].id]})
            assert _read_events(fresh, "notification")["body"] == "Still live"


def test_deactivation_closes_stream_and_others_unaffected(client, school, live_server):
    from conftest import make_user

    from app.models.enums import UserRole

    make_user(UserRole.ADMIN, "root@test.io")
    admin = login(client, "root@test.io")
    with httpx.Client(base_url=live_server, timeout=httpx.Timeout(10, read=10)) as http:
        with http.stream("GET", f"{API}/notifications/stream", headers=school["h1"]) as s1, \
             http.stream("GET", f"{API}/notifications/stream", headers=school["h2"]) as s2:
            _read_events(s1, "ready")
            _read_events(s2, "ready")
            users = http.get(f"{API}/admin/users?role=student", headers=admin).json()
            s2_user = next(u for u in users if u["email"] == "s2@test.io")
            assert http.patch(f"{API}/admin/users/{s2_user['id']}", headers=admin, json={"is_active": False}).status_code == 200
            _read_events(s2, "revoked", timeout=5)
            # student 1 keeps receiving events
            http.post(f"{API}/homework", headers=school["ha"], json={"title": "For s1", "student_ids": [school["s1"].id]})
            note = _read_events(s1, "notification")
            assert note["body"] == "For s1"

"""Teacher <-> student chat: ownership, unread counters, read receipts, live push."""
import httpx
from conftest import login, make_user
from test_realtime import _read_events

from app.core.database import SessionLocal
from app.models import StudentProfile, User
from app.models.enums import UserRole

API = "/api/v1"


def _send(client, headers, student_id, body):
    return client.post(f"{API}/messages/threads/{student_id}", headers=headers, json={"body": body})


def test_teacher_and_student_exchange_messages(client, school):
    s1 = school["s1"].id
    r = _send(client, school["ha"], s1, "  Hello! How was the homework?  ")
    assert r.status_code == 201
    msg = r.json()
    assert msg["body"] == "Hello! How was the homework?"  # trimmed
    assert msg["read_at"] is None

    # student sees one thread with their teacher, with an unread message
    threads = client.get(f"{API}/messages/threads", headers=school["h1"]).json()
    assert len(threads) == 1
    t = threads[0]
    assert t["student_id"] == s1 and t["partner"]["full_name"] == "Teacher A"
    assert t["unread_count"] == 1 and t["last_message"]["id"] == msg["id"]
    assert client.get(f"{API}/messages/unread-count", headers=school["h1"]).json() == {"count": 1}

    assert _send(client, school["h1"], s1, "Fine, thanks").status_code == 201
    history = client.get(f"{API}/messages/threads/{s1}", headers=school["h1"]).json()
    assert [m["body"] for m in history] == ["Hello! How was the homework?", "Fine, thanks"]

    # reading marks only the partner's messages
    assert client.post(f"{API}/messages/threads/{s1}/read", headers=school["h1"]).json() == {"count": 1}
    assert client.get(f"{API}/messages/unread-count", headers=school["h1"]).json() == {"count": 0}
    assert client.get(f"{API}/messages/unread-count", headers=school["ha"]).json() == {"count": 1}
    history = client.get(f"{API}/messages/threads/{s1}", headers=school["ha"]).json()
    assert history[0]["read_at"] is not None and history[1]["read_at"] is None

    # teacher's list: all own students, the active conversation first
    threads = client.get(f"{API}/messages/threads", headers=school["ha"]).json()
    assert [t["partner"]["full_name"] for t in threads] == ["Student One", "Student Two"]
    assert threads[0]["unread_count"] == 1 and threads[1]["last_message"] is None


def test_foreign_threads_are_404(client, school):
    s1, s3 = school["s1"].id, school["s3"].id
    _send(client, school["ha"], s1, "private")
    # another teacher, another student of the same teacher, a student of another teacher
    assert client.get(f"{API}/messages/threads/{s1}", headers=school["hb"]).status_code == 404
    assert _send(client, school["hb"], s1, "hi").status_code == 404
    assert client.get(f"{API}/messages/threads/{s1}", headers=school["h2"]).status_code == 404
    assert client.post(f"{API}/messages/threads/{s1}/read", headers=school["h3"]).status_code == 404
    assert _send(client, school["ha"], s3, "hi").status_code == 404
    assert client.get(f"{API}/messages/threads/999999", headers=school["ha"]).status_code == 404


def test_message_validation_and_roles(client, school):
    s1 = school["s1"].id
    assert _send(client, school["ha"], s1, "   ").status_code == 422
    assert _send(client, school["ha"], s1, "x" * 4001).status_code == 422
    assert _send(client, school["ha"], s1, "x" * 4000).status_code == 201

    make_user(UserRole.ADMIN, "admin@test.io")
    admin = login(client, "admin@test.io")
    assert client.get(f"{API}/messages/threads", headers=admin).status_code == 403
    assert client.get(f"{API}/messages/unread-count", headers=admin).json() == {"count": 0}


def test_history_paging(client, school):
    s1 = school["s1"].id
    ids = [_send(client, school["ha"], s1, f"m{i}").json()["id"] for i in range(5)]
    page = client.get(f"{API}/messages/threads/{s1}", headers=school["h1"], params={"limit": 2}).json()
    assert [m["id"] for m in page] == ids[3:]
    older = client.get(f"{API}/messages/threads/{s1}", headers=school["h1"],
                       params={"limit": 2, "before_id": ids[3]}).json()
    assert [m["id"] for m in older] == ids[1:3]


def test_student_without_teacher_and_moved_student(client, school):
    _, lone = make_user(UserRole.STUDENT, "lone@test.io")
    h = login(client, "lone@test.io")
    assert client.get(f"{API}/messages/threads", headers=h).json() == []
    assert client.get(f"{API}/messages/unread-count", headers=h).json() == {"count": 0}
    assert _send(client, h, lone.id, "anyone?").status_code == 404

    # student moves to teacher B: the old teacher loses access to the conversation
    s1 = school["s1"].id
    _send(client, school["ha"], s1, "old teacher")
    with SessionLocal() as db:
        db.get(StudentProfile, s1).teacher_id = school["tb"].id
        db.commit()
    assert client.get(f"{API}/messages/threads/{s1}", headers=school["ha"]).status_code == 404
    assert client.get(f"{API}/messages/threads/{s1}", headers=school["hb"]).json() == []


def test_cannot_message_deactivated_user(client, school):
    s1 = school["s1"]
    with SessionLocal() as db:
        db.get(User, s1.user_id).is_active = False
        db.commit()
    r = _send(client, school["ha"], s1.id, "hello?")
    assert r.status_code == 400
    threads = client.get(f"{API}/messages/threads", headers=school["ha"]).json()
    assert next(t for t in threads if t["student_id"] == s1.id)["partner"]["is_active"] is False


def test_chat_events_are_pushed_live(client, school, live_server):
    s1 = school["s1"].id
    with httpx.Client(base_url=live_server, timeout=httpx.Timeout(15, read=15)) as http:
        with http.stream("GET", f"{API}/notifications/stream", headers=school["h1"]) as resp:
            _read_events(resp, "ready")
            r = http.post(f"{API}/messages/threads/{s1}", headers=school["ha"], json={"body": "Live hello"})
            assert r.status_code == 201
            event = _read_events(resp, "chat")
            assert event["type"] == "message" and event["student_id"] == s1
            assert event["message_id"] == r.json()["id"] and event["preview"] == "Live hello"
            assert event["sender_name"] == "Teacher A"

        # the teacher learns that the student has read the message
        with http.stream("GET", f"{API}/notifications/stream", headers=school["ha"]) as resp:
            _read_events(resp, "ready")
            assert http.post(f"{API}/messages/threads/{s1}/read", headers=school["h1"]).json() == {"count": 1}
            event = _read_events(resp, "chat")
            assert event["type"] == "read" and event["up_to_id"] == r.json()["id"]

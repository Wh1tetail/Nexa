"""Stage 9: files in chat, e-mail copies of unread notifications/messages, e-mail settings."""
from datetime import UTC, datetime, timedelta

from conftest import login, make_user
from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Attachment, Message, Notification, StudentProfile
from app.models.enums import NotificationType, UserRole
from app.services import email_service
from app.services.email_outbox import process_email_outbox
from app.services.notification_service import notify

API = "/api/v1"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
PDF = b"%PDF-1.4\n%test\n"


def _send_files(client, headers, student_id, files, body=""):
    return client.post(f"{API}/messages/threads/{student_id}/files", headers=headers,
                       data={"body": body}, files=[("files", f) for f in files])


def _later():
    """A moment after the e-mail delay has passed."""
    return datetime.now(UTC) + timedelta(minutes=settings.EMAIL_NOTIFY_DELAY_MINUTES + 1)


def _run_outbox(now=None) -> int:
    with SessionLocal() as db:
        return process_email_outbox(db, now or _later())


# ---------- files in chat ----------

def test_message_with_files_and_access(client, school):
    s1 = school["s1"].id
    r = _send_files(client, school["ha"], s1, [("sheet.pdf", PDF, "application/pdf"),
                                              ("board.png", PNG, "image/png")], body="  Homework sheet  ")
    assert r.status_code == 201, r.text
    msg = r.json()
    assert msg["body"] == "Homework sheet"
    assert [a["original_name"] for a in msg["attachments"]] == ["sheet.pdf", "board.png"]
    file_id = msg["attachments"][0]["id"]

    # history and the thread list carry the files
    history = client.get(f"{API}/messages/threads/{s1}", headers=school["h1"]).json()
    assert len(history[0]["attachments"]) == 2
    threads = client.get(f"{API}/messages/threads", headers=school["h1"]).json()
    assert len(threads[0]["last_message"]["attachments"]) == 2

    # both participants can download, nobody else (not even an admin)
    assert client.get(f"{API}/files/{file_id}", headers=school["h1"]).content == PDF
    assert client.get(f"{API}/files/{file_id}", headers=school["ha"]).status_code == 200
    for h in ("hb", "h2", "h3"):
        assert client.get(f"{API}/files/{file_id}", headers=school[h]).status_code == 404
    make_user(UserRole.ADMIN, "admin@test.io")
    assert client.get(f"{API}/files/{file_id}", headers=login(client, "admin@test.io")).status_code == 404

    # student moves to another teacher: the old teacher loses access to the files too
    with SessionLocal() as db:
        db.get(StudentProfile, s1).teacher_id = school["tb"].id
        db.commit()
    assert client.get(f"{API}/files/{file_id}", headers=school["ha"]).status_code == 404


def test_file_only_message_and_limits(client, school):
    s1 = school["s1"].id
    r = _send_files(client, school["h1"], s1, [("photo.png", PNG, "image/png")])
    assert r.status_code == 201 and r.json()["body"] == ""
    threads = client.get(f"{API}/messages/threads", headers=school["ha"]).json()
    assert threads[0]["unread_count"] == 1

    too_many = [(f"p{i}.png", PNG, "image/png") for i in range(6)]
    assert _send_files(client, school["h1"], s1, too_many).status_code == 400
    assert _send_files(client, school["h1"], s1, [("x.png", PNG, "image/png")], body="x" * 4001).status_code == 400

    # one bad file rejects the whole message: nothing is stored
    bad = [("ok.png", PNG, "image/png"), ("fake.pdf", PNG, "application/pdf")]
    assert _send_files(client, school["h1"], s1, bad).status_code == 400
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(func.count()).select_from(Attachment)) == 1

    # foreign thread
    assert _send_files(client, school["hb"], s1, [("x.png", PNG, "image/png")]).status_code == 404


# ---------- e-mail outbox ----------

def test_unread_notifications_are_emailed_once(client, school):
    s1_user = school["s1"].user_id
    with SessionLocal() as db:
        notify(db, [s1_user], NotificationType.HOMEWORK_ASSIGNED, "Новое задание: Essay", "Срок: пятница", "/student/homework/1")
        notify(db, [s1_user], NotificationType.SYSTEM, "System note")  # in-app only
        db.commit()
    email_service.outbox.clear()

    assert _run_outbox(datetime.now(UTC)) == 0  # too early: the user may still see it in the app
    assert _run_outbox() == 1
    mail = email_service.outbox[-1]
    assert mail.to == "s1@test.io"
    assert mail.subject == "Новое задание: Essay"
    assert "/student/homework/1" in mail.text and "/student/settings" in mail.text
    assert _run_outbox() == 0  # never twice


def test_read_in_time_or_disabled_means_no_email(client, school):
    s1_user, s2_user = school["s1"].user_id, school["s2"].user_id
    # s2 switches test e-mails off through the API
    r = client.patch(f"{API}/auth/me", headers=school["h2"], json={"email_prefs": {"tests": False}})
    assert r.status_code == 200
    assert r.json()["email_prefs"] == {"messages": True, "homework": True, "tests": False,
                                       "lessons": True, "subscription": True}
    with SessionLocal() as db:
        notify(db, [s1_user, s2_user], NotificationType.TEST_ASSIGNED, "Новый тест")
        db.commit()
        db.execute(update(Notification).where(Notification.user_id == s1_user).values(is_read=True))
        db.commit()
    email_service.outbox.clear()
    assert _run_outbox() == 0
    assert not email_service.outbox


def test_email_prefs_validation(client, school):
    r = client.patch(f"{API}/auth/me", headers=school["h1"], json={"email_prefs": {"spam": True}})
    assert r.status_code == 422
    # partial updates keep the other categories
    client.patch(f"{API}/auth/me", headers=school["h1"], json={"email_prefs": {"lessons": False}})
    client.patch(f"{API}/auth/me", headers=school["h1"], json={"email_prefs": {"tests": False}})
    me = client.get(f"{API}/auth/me", headers=school["h1"]).json()
    assert me["email_prefs"]["lessons"] is False and me["email_prefs"]["tests"] is False
    assert me["email_prefs"]["messages"] is True


def test_unread_chat_messages_are_emailed_as_one_digest(client, school):
    s1, s2 = school["s1"].id, school["s2"].id
    for text in ("Hi!", "Don't forget the essay"):
        client.post(f"{API}/messages/threads/{s1}", headers=school["ha"], json={"body": text})
    _send_files(client, school["h1"], s1, [("answer.png", PNG, "image/png")])  # to the teacher
    client.post(f"{API}/messages/threads/{s2}", headers=school["ha"], json={"body": "Hello s2"})
    client.post(f"{API}/messages/threads/{s2}/read", headers=school["h2"])  # s2 read in time
    email_service.outbox.clear()

    assert _run_outbox() == 2
    by_to = {m.to: m for m in email_service.outbox}
    assert set(by_to) == {"s1@test.io", "ta@test.io"}
    student_mail = by_to["s1@test.io"]
    assert "Teacher A: 2" in student_mail.text and "Don't forget the essay" in student_mail.text
    assert "/student/messages" in student_mail.text
    teacher_mail = by_to["ta@test.io"]
    assert teacher_mail.subject == "Новое сообщение от Student One — NEXA"
    assert "📎 answer.png" in teacher_mail.text and f"/teacher/messages/{s1}" in teacher_mail.text
    assert _run_outbox() == 0


def test_chat_email_respects_prefs(client, school):
    s1 = school["s1"].id
    client.patch(f"{API}/auth/me", headers=school["h1"], json={"email_prefs": {"messages": False}})
    client.post(f"{API}/messages/threads/{s1}", headers=school["ha"], json={"body": "Hi"})
    email_service.outbox.clear()
    assert _run_outbox() == 0
    with SessionLocal() as db:  # handled, not left pending forever
        assert db.scalar(select(func.count()).select_from(Message).where(Message.email_processed_at.is_(None))) == 0

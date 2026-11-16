"""Stage 11: server texts in the user's language, orphan file sweep."""
import ast
import os
import pathlib
import re
import time
from datetime import UTC, datetime, timedelta

from conftest import make_user

from app.core.database import SessionLocal
from app.core.i18n import CATALOG, LANGS, PYDANTIC
from app.models import User
from app.models.enums import UserRole
from app.services import email_service
from app.services.storage_cleanup import sweep_orphans
from app.storage.base import get_storage

API = "/api/v1"
KK = {"Accept-Language": "kk"}
EN = {"Accept-Language": "en-US,en;q=0.9"}


def _h(headers, extra):
    return {**headers, **extra}


# ---------- API errors and validation ----------

def test_errors_follow_the_request_language(client, school):
    ha = school["ha"]
    assert client.get(f"{API}/tests/999999", headers=ha).json()["detail"] == "Тест не найден"
    assert client.get(f"{API}/tests/999999", headers=_h(ha, KK)).json()["detail"] == "Тест табылмады"
    assert client.get(f"{API}/tests/999999", headers=_h(ha, EN)).json()["detail"] == "Test not found"
    # unsupported language -> Russian
    assert client.get(f"{API}/tests/999999", headers=_h(ha, {"Accept-Language": "de"})).json()["detail"] == "Тест не найден"
    # 401 keeps its WWW-Authenticate header
    r = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nope", **EN})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid token" and r.headers["www-authenticate"] == "Bearer"


def test_messages_with_values_are_translated(client, school):
    s1 = school["s1"].id
    long = "x" * 4001
    r = client.post(f"{API}/messages/threads/{s1}/files", headers=_h(school["ha"], EN),
                    data={"body": long}, files=[("files", ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png"))])
    assert r.status_code == 400 and r.json()["detail"] == "The message cannot be longer than 4000 characters"
    r = client.post(f"{API}/messages/threads/{s1}/files", headers=_h(school["ha"], KK),
                    files=[("files", ("run.exe", b"MZ....", "application/octet-stream"))])
    assert r.status_code == 400 and r.json()["detail"].startswith("«run.exe» файлының форматы рұқсат етілмеген")


def test_validation_messages_are_translated(client, school):
    s1 = school["s1"].id
    # built-in Pydantic message (was English even in the Russian interface)
    r = client.post(f"{API}/messages/threads/{s1}", headers=school["ha"], json={"body": ""})
    assert r.json()["detail"] == "Слишком короткое значение (минимум 1)"
    r = client.post(f"{API}/messages/threads/{s1}", headers=_h(school["ha"], KK), json={})
    assert r.json()["detail"] == "Міндетті өріс" and r.json()["field"] == "body"
    # our own ValueError texts
    r = client.patch(f"{API}/auth/me", headers=_h(school["h1"], EN), json={"timezone": "Mars/Olympus"})
    assert r.status_code == 422 and r.json()["detail"] == "Unknown time zone"


def test_plain_http_errors_and_success_messages(client, school):
    make_user(UserRole.STUDENT, "s@test.io")
    for _ in range(10):
        client.post(f"{API}/auth/login", json={"email": "s@test.io", "password": "bad"})
    r = client.post(f"{API}/auth/login", headers=EN, json={"email": "s@test.io", "password": "bad"})
    assert r.status_code == 429 and r.json()["detail"] == "Too many attempts. Please try again in a few minutes"
    r = client.post(f"{API}/notifications/read-all", headers=_h(school["h1"], KK))
    assert r.json()["detail"] == "Барлық хабарландырулар оқылды"


# ---------- notifications, e-mails, CSV ----------

def _set_locale(user_id, lang):
    with SessionLocal() as db:
        db.get(User, user_id).locale = lang
        db.commit()


def test_notifications_use_the_recipients_language(client, school):
    _set_locale(school["s1"].user_id, "kk")
    _set_locale(school["s2"].user_id, "en")
    due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    # the teacher works in Russian; each student gets the text in their own language
    client.post(f"{API}/homework", headers=school["ha"], json={
        "title": "Essay", "due_at": due, "student_ids": [school["s1"].id, school["s2"].id]})
    kk = client.get(f"{API}/notifications", headers=school["h1"]).json()[0]
    en = client.get(f"{API}/notifications", headers=school["h2"]).json()[0]
    assert (kk["title"], kk["body"]) == ("Жаңа үй тапсырмасы", "Essay")  # user content stays as is
    assert en["title"] == "New homework"


def test_emails_use_the_recipients_language(client, school):
    make_user(UserRole.STUDENT, "en@test.io", name="Emma")
    _set_locale(_user_id("en@test.io"), "en")
    email_service.outbox.clear()
    client.post(f"{API}/auth/forgot-password", headers=KK, json={"email": "en@test.io"})
    mail = email_service.outbox[-1]
    assert mail.subject == "Password reset — NEXA" and "Hello, Emma!" in mail.text
    assert 'lang="en"' in mail.html


def test_new_users_start_in_their_creators_language(client, school):
    email_service.outbox.clear()
    r = client.post(f"{API}/students", headers=_h(school["aa"], KK),
                    json={"email": "kid@test.io", "full_name": "Айгерім", "send_invite": True})
    assert r.status_code == 201, r.text
    assert email_service.outbox[-1].subject == "Сіздің NEXA аккаунтыңыз"  # invitation in Kazakh
    with SessionLocal() as db:
        assert db.get(User, _user_id("kid@test.io")).locale == "kk"
    # the response text follows the teacher's language, the e-mail the student's
    again = client.post(f"{API}/students/{r.json()['id']}/invite", headers=_h(school["ha"], EN))
    assert again.json()["detail"] == "An invitation was sent to kid@test.io"
    assert email_service.outbox[-1].subject == "Сіздің NEXA аккаунтыңыз"


def test_attendance_csv_in_request_language(client, school):
    csv = client.get(f"{API}/attendance/export", headers=_h(school["ha"], EN)).content.decode("utf-8-sig")
    assert csv.splitlines()[0].startswith("Date (")
    assert ";Student;Lesson;Lesson status;Attendance;Comment" in csv.splitlines()[0]


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return db.query(User.id).filter(User.email == email).scalar()


# ---------- catalog completeness ----------

def _literal_templates() -> set[str]:
    """First string argument of error/ValueError/M()/tr() calls in the app code."""
    names = {"NotFound", "BadRequest", "Forbidden", "Conflict", "Unauthorized", "ValueError", "TaskError", "M", "tr", "AppError"}
    found: set[str] = set()
    for path in pathlib.Path("app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
                for arg in node.args[:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and re.search("[А-Яа-я]", arg.value):
                        found.add(arg.value)
                    if isinstance(arg, ast.IfExp):  # M("a" if x else "b")
                        for side in (arg.body, arg.orelse):
                            if isinstance(side, ast.Constant) and isinstance(side.value, str):
                                found.add(side.value)
    return found


def test_every_server_text_has_kazakh_and_english():
    missing = sorted(t for t in _literal_templates() if t not in CATALOG and t != "{title} — оценка {grade}/{max}")
    assert not missing, f"not in app/core/i18n.py CATALOG: {missing}"
    placeholder = re.compile(r"\{(\w+)\}")
    for ru, tr_ in CATALOG.items():
        assert set(tr_) == {"kk", "en"}, ru
        for lang in ("kk", "en"):
            assert set(placeholder.findall(tr_[lang])) == set(placeholder.findall(ru)), (ru, lang)
    for kind, texts in PYDANTIC.items():
        assert set(texts) == set(LANGS), kind


# ---------- orphan files ----------

def test_sweep_deletes_only_old_unreferenced_files(client, school):
    storage = get_storage()
    # a referenced file (chat attachment)
    r = client.post(f"{API}/messages/threads/{school['s1'].id}/files", headers=school["ha"],
                    files=[("files", ("a.pdf", b"%PDF-1.4\n%x\n", "application/pdf"))])
    kept_key = _storage_key(r.json()["attachments"][0]["id"])
    storage.save("2020/01/orphan-old.pdf", b"x", "application/pdf")
    storage.save("2020/01/orphan-new.pdf", b"x", "application/pdf")
    old = time.time() - 3 * 86400
    for key in ("2020/01/orphan-old.pdf", kept_key):
        os.utime(storage._path(key), (old, old))

    with SessionLocal() as db:
        dry = sweep_orphans(db, grace=timedelta(hours=24), dry_run=True)
    assert dry.orphans == ["2020/01/orphan-old.pdf"] and dry.deleted == 0

    with SessionLocal() as db:
        res = sweep_orphans(db, grace=timedelta(hours=24))
    assert res.deleted == 1
    keys = {k for k, _ in storage.list_keys()}
    assert "2020/01/orphan-old.pdf" not in keys
    assert "2020/01/orphan-new.pdf" in keys and kept_key in keys  # too new / still referenced


def _storage_key(attachment_id: int) -> str:
    from app.models import Attachment

    with SessionLocal() as db:
        return db.get(Attachment, attachment_id).storage_key

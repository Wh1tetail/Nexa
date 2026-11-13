"""Stage 2: e-mail (reset / invitations), lesson series, CSV export, admin console."""
from datetime import UTC, datetime, timedelta

from conftest import PASSWORD, login, make_user

from app.models.enums import UserRole
from app.services import email_service

API = "/api/v1"


def _token_from(url: str) -> str:
    return url.split("token=")[1]


def test_forgot_password_sends_email(client):
    email_service.outbox.clear()
    make_user(UserRole.STUDENT, "s@test.io", name="Ivan")
    r = client.post(f"{API}/auth/forgot-password", json={"email": "s@test.io"})
    assert r.status_code == 200
    assert len(email_service.outbox) == 1
    mail = email_service.outbox[-1]
    assert mail.to == "s@test.io" and "Ivan" in mail.text
    assert r.json()["dev_reset_url"] in mail.text
    # no mail for unknown addresses
    client.post(f"{API}/auth/forgot-password", json={"email": "nobody@test.io"})
    assert len(email_service.outbox) == 1


def test_invitation_flow(client, school):
    email_service.outbox.clear()
    bad = client.post(f"{API}/students", headers=school["ha"], json={"email": "new@test.io", "full_name": "New Kid"})
    assert bad.status_code == 422  # neither password nor invitation
    r = client.post(f"{API}/students", headers=school["ha"],
                    json={"email": "new@test.io", "full_name": "New Kid", "send_invite": True})
    assert r.status_code == 201, r.text
    url = r.json()["dev_invite_url"]
    mail = email_service.outbox[-1]
    assert mail.to == "new@test.io" and url in mail.text and "Teacher A" in mail.text
    assert client.post(f"{API}/auth/reset-password", json={"token": _token_from(url), "new_password": "Welcome123"}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": "new@test.io", "password": "Welcome123"}).status_code == 200
    # resend invite: only own students
    sid = r.json()["id"]
    assert client.post(f"{API}/students/{sid}/invite", headers=school["ha"]).status_code == 200
    assert client.post(f"{API}/students/{sid}/invite", headers=school["hb"]).status_code == 404


def test_lesson_series_and_delete_following(client, school):
    start = datetime.now(UTC) - timedelta(days=1)
    r = client.post(f"{API}/lessons", headers=school["ha"], json={
        "title": "Weekly", "starts_at": start.isoformat(), "student_ids": [school["s1"].id], "repeat_weeks": 3})
    assert r.status_code == 201, r.text
    series = r.json()["series_id"]
    assert series
    lessons = client.get(f"{API}/lessons", headers=school["ha"]).json()
    assert len([x for x in lessons if x["series_id"] == series]) == 4
    starts = sorted(x["starts_at"] for x in lessons)
    assert (datetime.fromisoformat(starts[1]) - datetime.fromisoformat(starts[0])).days == 7
    ordered = sorted(lessons, key=lambda x: x["starts_at"])
    # mark the 4th lesson, then delete "this and following" from the 2nd
    client.put(f"{API}/lessons/{ordered[3]['id']}/attendance", headers=school["ha"],
               json={"marks": [{"student_id": school["s1"].id, "status": "absent"}]})
    assert client.delete(f"{API}/lessons/{ordered[1]['id']}?scope=following", headers=school["ha"]).status_code == 204
    left = {x["id"] for x in client.get(f"{API}/lessons", headers=school["ha"]).json()}
    assert left == {ordered[0]["id"], ordered[3]["id"]}  # marked lesson kept
    assert client.post(f"{API}/lessons", headers=school["ha"], json={
        "title": "x", "starts_at": start.isoformat(), "student_ids": [school["s1"].id], "repeat_weeks": 60}).status_code == 422


def test_attendance_csv_export(client, school):
    r = client.post(f"{API}/lessons", headers=school["ha"], json={
        "title": "Grammar", "starts_at": datetime.now(UTC).isoformat(), "student_ids": [school["s1"].id]})
    client.put(f"{API}/lessons/{r.json()['id']}/attendance", headers=school["ha"],
               json={"marks": [{"student_id": school["s1"].id, "status": "late", "comment": "10 мин"}]})
    csv = client.get(f"{API}/attendance/export", headers=school["ha"])
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    text = csv.content.decode("utf-8-sig")
    assert "Student One" in text and "Опоздал" in text and "10 мин" in text
    assert client.get(f"{API}/attendance/export?student_id={school['s3'].id}", headers=school["ha"]).status_code == 404
    assert client.get(f"{API}/attendance/export", headers=school["h1"]).status_code == 403


def test_admin_console(client, school):
    admin, _ = make_user(UserRole.ADMIN, "root@test.io", name="Root")
    h = login(client, "root@test.io")
    assert client.get(f"{API}/admin/users", headers=school["ha"]).status_code == 403

    users = client.get(f"{API}/admin/users?role=student", headers=h).json()
    assert {u["email"] for u in users} == {"s1@test.io", "s2@test.io", "s3@test.io"}
    s1 = next(u for u in users if u["email"] == "s1@test.io")
    assert s1["teacher_name"] == "Teacher A"
    teachers = client.get(f"{API}/admin/users?role=teacher", headers=h).json()
    assert next(t for t in teachers if t["email"] == "ta@test.io")["students_count"] == 2
    stats = client.get(f"{API}/admin/stats", headers=h).json()
    assert stats["teachers"] == 2 and stats["students"] == 3

    # deactivate -> sessions revoked and login blocked; cannot deactivate self
    assert client.patch(f"{API}/admin/users/{s1['id']}", headers=h, json={"is_active": False}).json()["is_active"] is False
    assert client.get(f"{API}/auth/me", headers=school["h1"]).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "s1@test.io", "password": PASSWORD}).status_code == 401
    assert client.patch(f"{API}/admin/users/{admin.id}", headers=h, json={"is_active": False}).status_code == 400
    client.patch(f"{API}/admin/users/{s1['id']}", headers=h, json={"is_active": True})

    # set password / send link
    assert client.post(f"{API}/admin/users/{s1['id']}/password", headers=h, json={}).status_code == 422
    assert client.post(f"{API}/admin/users/{s1['id']}/password", headers=h, json={"password": "Changed123"}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": "s1@test.io", "password": "Changed123"}).status_code == 200
    r = client.post(f"{API}/admin/users/{s1['id']}/password", headers=h, json={"send_link": True})
    assert r.json()["dev_invite_url"]

    # reassign to teacher B: teacher A loses access, B gains it
    tb = school["tb"]
    r = client.post(f"{API}/admin/students/{school['s1'].id}/teacher/{tb.id}", headers=h)
    assert r.json()["teacher_name"] == "Teacher B"
    assert client.get(f"{API}/students/{school['s1'].id}", headers=school["ha"]).status_code == 404
    assert client.get(f"{API}/students/{school['s1'].id}", headers=school["hb"]).status_code == 200

    # create teacher via invitation
    r = client.post(f"{API}/admin/teachers", headers=h, json={"email": "t3@test.io", "full_name": "Third T", "send_invite": True})
    assert r.status_code == 201
    assert email_service.outbox[-1].to == "t3@test.io"

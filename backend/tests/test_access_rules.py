"""Subscription gate for students; creating students/groups/lessons and changing subscriptions is admin-only."""
from datetime import UTC, datetime, timedelta

from conftest import give_subscription, make_user

from app.core.database import SessionLocal
from app.models import Subscription
from app.models.enums import UserRole

API = "/api/v1"
CLOSED = ("/me/homework", "/me/tests", "/me/attendance")


def _closed(client, headers) -> bool:
    codes = [client.get(f"{API}{path}", headers=headers) for path in CLOSED]
    return all(r.status_code == 403 and r.json().get("code") == "subscription_required" for r in codes)


def _open(client, headers) -> bool:
    return all(client.get(f"{API}{path}", headers=headers).status_code == 200 for path in CLOSED)


def _only_sub(student_id: int) -> Subscription:
    with SessionLocal() as db:
        return db.query(Subscription).filter_by(student_id=student_id).one()


# ---------- subscription gate ----------

def test_expired_subscription_closes_and_extension_reopens(client, school):
    s1, h1 = school["s1"], school["h1"]
    assert _open(client, h1)
    sub = _only_sub(s1.id)
    today = datetime.now(UTC).date()
    r = client.patch(f"{API}/subscriptions/{sub.id}", headers=school["aa"], json={
        "start_date": str(today - timedelta(days=40)), "end_date": str(today - timedelta(days=1))})
    assert r.status_code == 200 and r.json()["status"] == "expired"

    assert _closed(client, h1)
    me = client.get(f"{API}/auth/me", headers=h1).json()
    assert me["access_active"] is False
    dash = client.get(f"{API}/dashboard/student", headers=h1).json()
    assert dash["access_active"] is False and dash["next_lessons"] == [] and dash["recent_tests"] == []
    # still available: the subscription itself, messages, notifications, settings
    assert client.get(f"{API}/me/subscription", headers=h1).status_code == 200
    assert client.get(f"{API}/messages/threads", headers=h1).status_code == 200
    assert client.get(f"{API}/notifications", headers=h1).status_code == 200

    # the teacher renews it -> everything is back at once
    assert client.post(f"{API}/subscriptions/{sub.id}/extend", headers=school["aa"], json={"add_days": 30}).status_code == 200
    assert _open(client, h1)
    assert client.get(f"{API}/auth/me", headers=h1).json()["access_active"] is True


def test_frozen_closes_and_unfreeze_reopens(client, school):
    sub = _only_sub(school["s1"].id)
    client.post(f"{API}/subscriptions/{sub.id}/freeze", headers=school["aa"])
    assert _closed(client, school["h1"])
    client.post(f"{API}/subscriptions/{sub.id}/unfreeze", headers=school["aa"])
    assert _open(client, school["h1"])


def test_no_subscription_or_not_started_yet_is_closed(client, school):
    from conftest import login

    _, newbie = make_user(UserRole.STUDENT, "newbie@test.io", school["ta"], "Newbie")
    h = login(client, "newbie@test.io")
    assert _closed(client, h)
    today = datetime.now(UTC).date()
    give_subscription(newbie, start_date=today + timedelta(days=3), end_date=today + timedelta(days=33))
    assert _closed(client, h)  # starts in 3 days


def test_homework_files_follow_the_gate(client, school):
    pdf = b"%PDF-1.4\n%x\n"
    hw = client.post(f"{API}/homework", headers=school["ha"], json={
        "title": "Read", "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "student_ids": [school["s1"].id]}).json()
    up = client.post(f"{API}/homework/{hw['id']}/attachments", headers=school["ha"],
                     files=[("files", ("task.pdf", pdf, "application/pdf"))])
    file_id = up.json()[0]["id"]
    assert client.get(f"{API}/files/{file_id}", headers=school["h1"]).status_code == 200
    sub = _only_sub(school["s1"].id)
    client.post(f"{API}/subscriptions/{sub.id}/freeze", headers=school["aa"])
    assert client.get(f"{API}/files/{file_id}", headers=school["h1"]).status_code == 403


# ---------- admin-only creation ----------

def test_teacher_cannot_create_students_groups_or_lessons(client, school):
    ha = school["ha"]
    start = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert client.post(f"{API}/students", headers=ha, json={
        "email": "x@test.io", "full_name": "X Y", "password": "Passw0rd!"}).status_code == 403
    assert client.post(f"{API}/groups", headers=ha, json={"name": "G"}).status_code == 403
    assert client.post(f"{API}/lessons", headers=ha, json={
        "title": "L", "starts_at": start, "student_ids": [school["s1"].id]}).status_code == 403
    # the admin does it for teacher A
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "G", "student_ids": [school["s1"].id]})
    assert g.status_code == 201
    lesson = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "L", "starts_at": start, "student_ids": [school["s1"].id]})
    assert lesson.status_code == 201
    assert any(x["id"] == lesson.json()["id"] for x in client.get(f"{API}/lessons", headers=ha).json())
    assert client.get(f"{API}/lessons/{lesson.json()['id']}", headers=school["hb"]).status_code == 404
    # deleting is admin-only too
    assert client.delete(f"{API}/groups/{g.json()['id']}", headers=ha).status_code == 403
    assert client.delete(f"{API}/lessons/{lesson.json()['id']}", headers=ha).status_code == 403
    assert client.post(f"{API}/lessons/{lesson.json()['id']}/series/extend", headers=ha, json={"weeks": 2}).status_code == 403


def test_what_a_teacher_can_still_change(client, school):
    s1, s2 = school["s1"].id, school["s2"].id
    start = datetime.now(UTC) - timedelta(hours=2)
    lesson = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "L", "starts_at": start.isoformat(), "student_ids": [s1]}).json()
    url = f"{API}/lessons/{lesson['id']}"
    ha = school["ha"]
    # topic and adding students: yes
    r = client.patch(url, headers=ha, json={"topic": "Past Simple", "student_ids": [s1, s2]})
    assert r.status_code == 200 and r.json()["topic"] == "Past Simple" and len(r.json()["attendance"]) == 2
    # removing students, time, title, link, cancelling: no
    assert client.patch(url, headers=ha, json={"student_ids": [s1]}).status_code == 403
    assert client.patch(url, headers=ha, json={"starts_at": (start + timedelta(hours=1)).isoformat()}).status_code == 403
    assert client.patch(url, headers=ha, json={"title": "New"}).status_code == 403
    assert client.patch(url, headers=ha, json={"status": "cancelled"}).status_code == 403
    # marking attendance: yes
    r = client.put(f"{url}/attendance", headers=ha, json={"marks": [{"student_id": s1, "status": "present"}]})
    assert r.status_code == 200
    # the admin can do everything
    assert client.patch(url, headers=school["aa"], json={"student_ids": [s1], "title": "New"}).status_code == 200
    # existing groups and students stay editable for the teacher
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "G", "student_ids": [s1]}).json()
    r = client.patch(f"{API}/groups/{g['id']}", headers=ha, json={"student_ids": [s1, s2], "description": "Evening"})
    assert r.status_code == 200 and len(r.json()["students"]) == 2
    assert client.patch(f"{API}/students/{s1}", headers=ha, json={"english_level": "B1"}).status_code == 200


def test_admin_must_choose_a_teacher(client, school):
    adm = school["adm"]
    start = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    r = client.post(f"{API}/lessons", headers=adm, json={"title": "L", "starts_at": start, "student_ids": []})
    assert r.status_code == 400
    assert client.get(f"{API}/groups", headers=adm, params={"teacher_id": 999999}).status_code == 404
    # ?teacher_id= works like the header; another teacher's students are still refused
    r = client.post(f"{API}/lessons", headers=adm, params={"teacher_id": school["ta"].id}, json={
        "title": "L", "starts_at": start, "student_ids": [school["s3"].id]})
    assert r.status_code == 403
    assert client.get(f"{API}/groups", headers=school["h1"]).status_code == 403


def test_subscriptions_are_view_only_for_teachers(client, school):
    ha, aa, s1 = school["ha"], school["aa"], school["s1"].id
    sub = _only_sub(s1)
    url = f"{API}/subscriptions/{sub.id}"
    # viewing: yes
    assert client.get(f"{API}/subscriptions", headers=ha).status_code == 200
    assert client.get(url, headers=ha).status_code == 200
    assert client.get(f"{API}/students/{s1}/subscriptions", headers=ha).status_code == 200
    # every change: no
    today = datetime.now(UTC).date()
    assert client.post(f"{API}/subscriptions", headers=ha, json={
        "student_id": s1, "start_date": str(today), "end_date": str(today + timedelta(days=30)),
        "total_lessons": 8}).status_code == 403
    assert client.patch(url, headers=ha, json={"title": "X"}).status_code == 403
    assert client.post(f"{url}/extend", headers=ha, json={"add_days": 30}).status_code == 403
    assert client.post(f"{url}/use-lesson", headers=ha, json={"count": 1}).status_code == 403
    assert client.post(f"{url}/freeze", headers=ha).status_code == 403
    assert client.post(f"{url}/unfreeze", headers=ha).status_code == 403
    assert client.delete(url, headers=ha).status_code == 403
    # the admin, acting for the student's teacher, can
    assert client.patch(url, headers=aa, json={"title": "X"}).json()["title"] == "X"
    assert client.post(f"{url}/freeze", headers=aa).json()["status"] == "frozen"
    assert client.post(f"{url}/unfreeze", headers=aa).status_code == 200
    # ...but not through another teacher
    assert client.patch(url, headers=school["ab"], json={"title": "Y"}).status_code == 404
    assert client.delete(url, headers=aa).status_code == 204

from datetime import UTC, date, datetime, timedelta

from conftest import clear_subscriptions

API = "/api/v1"


def test_teacher_sees_only_own_students(client, school):
    r = client.get(f"{API}/students", headers=school["ha"])
    names = [s["full_name"] for s in r.json()]
    assert names == ["Student One", "Student Two"]
    # another teacher's student is hidden (404)
    assert client.get(f"{API}/students/{school['s3'].id}", headers=school["ha"]).status_code == 404
    assert client.get(f"{API}/students?search=two", headers=school["ha"]).json()[0]["full_name"] == "Student Two"


def test_teacher_creates_student_and_student_logs_in(client, school):
    r = client.post(f"{API}/students", headers=school["aa"], json={
        "email": "fresh@test.io", "full_name": "Fresh Student", "password": "Fresh1234", "english_level": "B2"})
    assert r.status_code == 201, r.text
    login = client.post(f"{API}/auth/login", json={"email": "fresh@test.io", "password": "Fresh1234"})
    assert login.status_code == 200
    bad = client.post(f"{API}/students", headers=school["aa"], json={
        "email": "x@test.io", "full_name": "X Y", "password": "nodigits"})
    assert bad.status_code == 422


def test_subscription_status_and_lessons(client, school):
    clear_subscriptions(school["s1"])  # this test creates its own
    today = datetime.now(UTC).date()
    sid = school["s1"].id
    r = client.post(f"{API}/subscriptions", headers=school["ha"], json={
        "student_id": sid, "start_date": str(today - timedelta(days=10)),
        "end_date": str(today + timedelta(days=5)), "total_lessons": 8})
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["status"] == "expiring_soon" and sub["days_left"] == 5 and sub["lessons_left"] == 8
    # other teacher can't touch it
    assert client.post(f"{API}/subscriptions/{sub['id']}/use-lesson", headers=school["hb"],
                       json={"count": 1}).status_code == 404
    # extend by 30 days -> active
    r = client.post(f"{API}/subscriptions/{sub['id']}/extend", headers=school["ha"],
                    json={"add_days": 30, "add_lessons": 4})
    assert r.json()["status"] == "active" and r.json()["total_lessons"] == 12
    r = client.post(f"{API}/subscriptions/{sub['id']}/use-lesson", headers=school["ha"], json={"count": 2})
    assert r.json()["lessons_left"] == 10
    assert client.post(f"{API}/subscriptions/{sub['id']}/freeze", headers=school["ha"]).json()["status"] == "frozen"
    # can't create for another teacher's student
    assert client.post(f"{API}/subscriptions", headers=school["ha"], json={
        "student_id": school["s3"].id, "start_date": str(today), "end_date": str(today),
        "total_lessons": 1}).status_code == 404
    # invalid dates
    assert client.post(f"{API}/subscriptions", headers=school["ha"], json={
        "student_id": sid, "start_date": str(today), "end_date": str(today - timedelta(days=1)),
        "total_lessons": 1}).status_code == 422
    # student sees own subscription
    mine = client.get(f"{API}/me/subscription", headers=school["h1"]).json()
    assert mine["id"] == sub["id"]


def test_expired_subscription_and_notifications(client, school):
    clear_subscriptions(school["s2"])  # this test creates its own
    from app.core.database import SessionLocal
    from app.services.subscription_service import check_expirations

    today = datetime.now(UTC).date()
    client.post(f"{API}/subscriptions", headers=school["ha"], json={
        "student_id": school["s2"].id, "start_date": str(today - timedelta(days=40)),
        "end_date": str(today - timedelta(days=1)), "total_lessons": 8})
    with SessionLocal() as db:
        assert check_expirations(db) == 1
        assert check_expirations(db) == 0  # idempotent
    notes = client.get(f"{API}/notifications", headers=school["ha"]).json()
    assert notes[0]["type"] == "subscription_expired"
    dash = client.get(f"{API}/dashboard/teacher", headers=school["ha"]).json()
    assert dash["subscriptions_expired"] == 1


def test_attendance_charges_subscription(client, school):
    today = datetime.now(UTC).date()
    sub = client.post(f"{API}/subscriptions", headers=school["ha"], json={
        "student_id": school["s1"].id, "start_date": str(today - timedelta(days=5)),
        "end_date": str(today + timedelta(days=30)), "total_lessons": 8}).json()
    lesson = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "Lesson", "starts_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "student_ids": [school["s1"].id, school["s2"].id]})
    assert lesson.status_code == 201, lesson.text
    lid = lesson.json()["id"]
    r = client.put(f"{API}/lessons/{lid}/attendance", headers=school["ha"], json={"marks": [
        {"student_id": school["s1"].id, "status": "present"},
        {"student_id": school["s2"].id, "status": "absent", "comment": "болеет"}]})
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert client.get(f"{API}/subscriptions/{sub['id']}", headers=school["ha"]).json()["used_lessons"] == 1
    # switching present -> excused refunds the lesson
    client.put(f"{API}/lessons/{lid}/attendance", headers=school["ha"], json={"marks": [
        {"student_id": school["s1"].id, "status": "excused"}]})
    assert client.get(f"{API}/subscriptions/{sub['id']}", headers=school["ha"]).json()["used_lessons"] == 0
    stats = client.get(f"{API}/attendance/stats", headers=school["ha"]).json()
    s2 = next(s for s in stats if s["student_id"] == school["s2"].id)
    assert s2["absent"] == 1 and s2["attendance_rate"] == 0
    mine = client.get(f"{API}/me/attendance", headers=school["h2"]).json()
    assert mine["stats"]["absent"] == 1 and mine["lessons"][0]["comment"] == "болеет"
    # teacher B can't mark teacher A lesson; can't add foreign students
    assert client.put(f"{API}/lessons/{lid}/attendance", headers=school["hb"], json={"marks": []}).status_code == 404
    assert client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "x", "starts_at": datetime.now(UTC).isoformat(),
        "student_ids": [school["s3"].id]}).status_code == 403


def test_groups(client, school):
    r = client.post(f"{API}/groups", headers=school["aa"],
                    json={"name": "B1", "student_ids": [school["s1"].id, school["s2"].id]})
    assert r.status_code == 201 and len(r.json()["students"]) == 2
    assert client.post(f"{API}/groups", headers=school["aa"], json={"name": "B1"}).status_code == 409
    assert client.post(f"{API}/groups", headers=school["aa"],
                       json={"name": "X", "student_ids": [school["s3"].id]}).status_code == 403
    gid = r.json()["id"]
    assert len(client.get(f"{API}/students?group_id={gid}", headers=school["ha"]).json()) == 2


_ = date

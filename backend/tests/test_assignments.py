"""Stage 14: lesson participants, group lessons, test/homework exclusion.

Removal is soft everywhere: marks, attempts, files and grades stay, and adding
the student again restores them without duplicates."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import Attendance, Subscription

API = "/api/v1"
PDF = b"%PDF-1.4\n%x\n"


def _lesson(client, school, when, student_ids=(), group_id=None, weeks=0):
    r = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "Grammar", "starts_at": when.isoformat(), "student_ids": list(student_ids),
        "group_id": group_id, "repeat_weeks": weeks})
    assert r.status_code == 201, r.text
    return r.json()


def _participants(client, school, lesson_id):
    d = client.get(f"{API}/lessons/{lesson_id}", headers=school["ha"]).json()
    return sorted(p["student_id"] for p in d["attendance"]), d


def _rows(student_id):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Attendance).where(Attendance.student_id == student_id))


def _used(student_id):
    with SessionLocal() as db:
        return db.scalars(select(Subscription.used_lessons).where(Subscription.student_id == student_id)).one()


# ---------- 2. group membership -> lessons ----------

def test_new_group_member_gets_upcoming_group_lessons_only(client, school):
    s1, s2, s3_other = school["s1"].id, school["s2"].id, school["s3"].id
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "A2", "student_ids": [s1]}).json()
    now = datetime.now(UTC)
    past = _lesson(client, school, now - timedelta(days=3), group_id=g["id"])
    future = _lesson(client, school, now + timedelta(days=1), group_id=g["id"], weeks=3)  # 4 lessons
    assert client.get(f"{API}/groups", headers=school["ha"]).json()[0]["upcoming_lessons"] == 4

    r = client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={"student_ids": [s1, s2]})
    assert r.status_code == 200, r.text
    assert r.json()["lessons_assigned"] == 4
    assert _participants(client, school, future["id"])[0] == [s1, s2]
    assert _participants(client, school, past["id"])[0] == [s1]  # finished lessons are not assigned
    # the student sees them; a foreign student can't be added
    mine = client.get(f"{API}/lessons", headers=school["ha"], params={"student_id": s2}).json()
    assert len(mine) == 4
    assert client.patch(f"{API}/groups/{g['id']}", headers=school["ha"],
                        json={"student_ids": [s1, s2, s3_other]}).status_code == 403

    # adding again does not duplicate anything
    rows = _rows(s2)
    client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={"student_ids": [s1, s2]})
    assert _rows(s2) == rows == 4


def test_lessons_from_a_chosen_date_or_none(client, school):
    s1, s2 = school["s1"].id, school["s2"].id
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "B1", "student_ids": [s1]}).json()
    start = datetime.now(UTC) + timedelta(days=1)
    _lesson(client, school, start, group_id=g["id"], weeks=3)
    r = client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={
        "student_ids": [s1, s2], "lessons_from": (start + timedelta(days=10)).isoformat()})
    assert r.json()["lessons_assigned"] == 2  # weeks 3 and 4 only
    # without lessons: membership only
    client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={"student_ids": [s1]})
    r = client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={
        "student_ids": [s1, s2], "assign_lessons": False})
    assert r.json()["lessons_assigned"] == 0


def test_leaving_the_group_releases_future_lessons_and_keeps_history(client, school):
    s1, s2 = school["s1"].id, school["s2"].id
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "C1", "student_ids": [s1, s2]}).json()
    now = datetime.now(UTC)
    past = _lesson(client, school, now - timedelta(hours=3), group_id=g["id"])
    future = _lesson(client, school, now + timedelta(days=2), group_id=g["id"])
    client.put(f"{API}/lessons/{past['id']}/attendance", headers=school["ha"], json={"marks": [
        {"student_id": s2, "status": "present"}]})

    r = client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={"student_ids": [s1]})
    assert r.json()["lessons_released"] == 1
    assert _participants(client, school, future["id"])[0] == [s1]
    assert s2 in _participants(client, school, past["id"])[0]  # the past lesson and its mark stay
    stats = client.get(f"{API}/me/attendance", headers=school["h2"]).json()["stats"]
    assert stats["present"] == 1
    # coming back restores the same row (no duplicate)
    client.patch(f"{API}/groups/{g['id']}", headers=school["ha"], json={"student_ids": [s1, s2]})
    assert _participants(client, school, future["id"])[0] == [s1, s2]
    assert _rows(s2) == 2


def test_new_student_created_into_a_group_gets_its_lessons(client, school):
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "D1"}).json()
    _lesson(client, school, datetime.now(UTC) + timedelta(days=1), student_ids=[school["s1"].id],
            group_id=g["id"], weeks=1)
    r = client.post(f"{API}/students", headers=school["aa"], json={
        "email": "fresh@test.io", "full_name": "Fresh Student", "password": "Passw0rd1", "group_ids": [g["id"]]})
    assert r.status_code == 201, r.text
    assert _rows(r.json()["id"]) == 2


# ---------- 1. one lesson ----------

def test_remove_from_one_lesson_keeps_group_mark_and_refunds(client, school):
    s1, s2 = school["s1"].id, school["s2"].id
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "E1", "student_ids": [s1, s2]}).json()
    now = datetime.now(UTC)
    done = _lesson(client, school, now - timedelta(hours=3), group_id=g["id"])
    other = _lesson(client, school, now + timedelta(days=1), group_id=g["id"])
    client.put(f"{API}/lessons/{done['id']}/attendance", headers=school["ha"], json={"marks": [
        {"student_id": s1, "status": "present"}, {"student_id": s2, "status": "present"}]})
    assert _used(s2) == 1

    # the teacher removes s2 from the finished lesson
    r = client.post(f"{API}/lessons/{done['id']}/participants/remove", headers=school["ha"], json={"student_ids": [s2]})
    assert r.status_code == 200, r.text
    assert [p["student_id"] for p in r.json()["attendance"]] == [s1]
    removed = r.json()["removed"]
    assert removed[0]["student_id"] == s2 and removed[0]["status"] == "present"  # history kept
    assert _used(s2) == 0  # the charged lesson went back to the subscription
    assert s2 in [m["id"] for m in client.get(f"{API}/groups", headers=school["ha"]).json()[0]["students"]]
    assert _participants(client, school, other["id"])[0] == [s1, s2]
    assert client.get(f"{API}/me/attendance", headers=school["h2"]).json()["stats"]["present"] == 0

    # adding back restores the mark and the charge
    r = client.post(f"{API}/lessons/{done['id']}/participants", headers=school["ha"], json={"student_ids": [s2]})
    row = next(p for p in r.json()["attendance"] if p["student_id"] == s2)
    assert row["status"] == "present" and r.json()["removed"] == []
    assert _used(s2) == 1 and _rows(s2) == 2


def test_lesson_participants_are_owned(client, school):
    lesson = _lesson(client, school, datetime.now(UTC) + timedelta(days=1), student_ids=[school["s1"].id])
    url = f"{API}/lessons/{lesson['id']}/participants"
    assert client.post(url, headers=school["hb"], json={"student_ids": [school["s3"].id]}).status_code == 404
    assert client.post(url, headers=school["ha"], json={"student_ids": [school["s3"].id]}).status_code == 403
    assert client.post(f"{url}/remove", headers=school["h1"], json={"student_ids": [school["s1"].id]}).status_code == 403
    assert client.post(f"{url}/remove", headers=school["ha"], json={"student_ids": []}).status_code == 422


# ---------- 6. tests ----------

def _test(client, school, **fields):
    q = [{"type": "single_choice", "text": "Q", "points": 1, "correct_answer": ["a"],
          "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]}]
    r = client.post(f"{API}/tests", headers=school["ha"], json={
        "title": "Quiz", "questions": q, "student_ids": [school["s1"].id, school["s2"].id], **fields})
    assert r.status_code == 201, r.text
    return r.json()


def test_excluding_from_a_test_keeps_results(client, school):
    t = _test(client, school, max_attempts=2)
    a = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h2"]).json()
    client.post(f"{API}/me/tests/attempts/{a['id']}/submit", headers=school["h2"],
                json={"answers": [{"question_id": t["questions"][0]["id"], "answer": ["a"]}]})

    r = client.post(f"{API}/tests/{t['id']}/unassign", headers=school["ha"], json={"student_ids": [school["s2"].id]})
    assert r.status_code == 200 and r.json()["student_ids"] == [school["s1"].id]
    # the student no longer sees or opens it
    assert client.get(f"{API}/me/tests", headers=school["h2"]).json() == []
    assert client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h2"]).status_code == 404
    assert client.get(f"{API}/me/tests/attempts/{a['id']}", headers=school["h2"]).status_code == 200  # own history
    # the teacher still has the result, with filters
    url = f"{API}/tests/{t['id']}"
    assert len(client.get(f"{url}/attempts", headers=school["ha"]).json()) == 1
    assert client.get(f"{url}/attempts", headers=school["ha"], params={"state": "active"}).json() == []
    removed = client.get(f"{url}/participants", headers=school["ha"], params={"state": "removed"}).json()
    assert removed[0]["student_id"] == school["s2"].id and removed[0]["best_percent"] == 100
    assert removed[0]["removed_at"] is not None
    active = client.get(f"{url}/participants", headers=school["ha"]).json()
    assert [p["student_id"] for p in active] == [school["s1"].id]
    # no extra attempt for an excluded student
    assert client.post(f"{API}/tests/attempts/{a['id']}/retake", headers=school["ha"]).status_code == 400

    # assigning again restores the same row with the attempt history
    client.post(f"{url}/assign", headers=school["ha"], json={"student_ids": [school["s2"].id]})
    item = client.get(f"{API}/me/tests", headers=school["h2"]).json()[0]
    assert item["attempts_used"] == 1 and item["can_retake"] is True
    assert client.post(f"{url}/unassign", headers=school["hb"], json={"student_ids": [school["s2"].id]}).status_code == 404


# ---------- 6. homework ----------

def test_excluding_from_homework_keeps_work(client, school):
    hw = client.post(f"{API}/homework", headers=school["ha"], json={
        "title": "Essay", "due_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "student_ids": [school["s1"].id, school["s2"].id]}).json()
    sub_id = next(s["id"] for s in hw["submissions"] if s["student_id"] == school["s2"].id)
    up = client.post(f"{API}/me/homework/{sub_id}/files", headers=school["h2"],
                     files=[("files", ("essay.pdf", PDF, "application/pdf"))])
    assert up.status_code in (200, 201), up.text
    client.post(f"{API}/me/homework/{sub_id}/submit", headers=school["h2"], json={"student_comment": "done"})
    client.post(f"{API}/homework/submissions/{sub_id}/review", headers=school["ha"],
                json={"grade": 9, "teacher_comment": "Good", "status": "reviewed"})

    r = client.post(f"{API}/homework/{hw['id']}/unassign", headers=school["ha"], json={"student_ids": [school["s2"].id]})
    assert r.status_code == 200, r.text
    sub = next(s for s in r.json()["submissions"] if s["student_id"] == school["s2"].id)
    assert sub["removed_at"] and sub["grade"] == 9 and len(sub["files"]) == 1 and sub["student_comment"] == "done"
    # hidden from the student
    assert client.get(f"{API}/me/homework", headers=school["h2"]).json() == []
    assert client.get(f"{API}/me/homework/{sub_id}", headers=school["h2"]).status_code == 404
    file_id = sub["files"][0]["id"]
    assert client.get(f"{API}/files/{file_id}", headers=school["h2"]).status_code == 403
    assert client.get(f"{API}/files/{file_id}", headers=school["ha"]).status_code == 200
    # counters and lists for the teacher
    item = next(h for h in client.get(f"{API}/homework", headers=school["ha"]).json() if h["id"] == hw["id"])
    assert item["counts"]["total"] == 1 and item["counts"]["removed"] == 1
    subs = f"{API}/homework/submissions"
    assert all(s["student_id"] != school["s2"].id for s in client.get(subs, headers=school["ha"]).json())
    assert len(client.get(subs, headers=school["ha"], params={"state": "removed"}).json()) == 1

    # restoring brings the same work back
    client.patch(f"{API}/homework/{hw['id']}", headers=school["ha"], json={"add_student_ids": [school["s2"].id]})
    mine = client.get(f"{API}/me/homework", headers=school["h2"]).json()
    assert len(mine) == 1 and mine[0]["grade"] == 9

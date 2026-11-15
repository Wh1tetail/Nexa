"""Stage 12: progress analytics for students and the teacher's overview."""
from datetime import UTC, datetime, timedelta

from conftest import make_user

from app.models.enums import UserRole

API = "/api/v1"


def _lesson(client, school, students, days_ago=1):
    r = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "Lesson", "starts_at": (datetime.now(UTC) - timedelta(days=days_ago, hours=1)).isoformat(),
        "student_ids": students})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _mark(client, school, lesson_id, marks):
    r = client.put(f"{API}/lessons/{lesson_id}/attendance", headers=school["ha"],
                   json={"marks": [{"student_id": s, "status": st} for s, st in marks]})
    assert r.status_code == 200, r.text


def _test(client, school, student_id, right: int, of: int = 4, passing=None):
    qs = [{"type": "single_choice", "text": f"Q{i}", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
           "correct_answer": ["a"]} for i in range(of)]
    t = client.post(f"{API}/tests", headers=school["ha"], json={
        "title": f"T{right}", "questions": qs, "student_ids": [student_id], "passing_percent": passing}).json()
    headers = school["h1"] if student_id == school["s1"].id else school["h2"]
    attempt = client.post(f"{API}/me/tests/{t['id']}/start", headers=headers).json()
    answers = [{"question_id": q["id"], "answer": ["a" if i < right else "b"]} for i, q in enumerate(t["questions"])]
    client.post(f"{API}/me/tests/attempts/{attempt['id']}/submit", headers=headers, json={"answers": answers})


def _homework(client, school, student_id, grade=None, due_in_days=2):
    due = (datetime.now(UTC) + timedelta(days=due_in_days)).isoformat()
    hw = client.post(f"{API}/homework", headers=school["ha"], json={
        "title": "Essay", "due_at": due, "max_grade": 10, "student_ids": [student_id]}).json()
    sub_id = client.get(f"{API}/homework/{hw['id']}", headers=school["ha"]).json()["submissions"][0]["id"]
    if grade is not None:
        headers = school["h1"] if student_id == school["s1"].id else school["h2"]
        client.post(f"{API}/me/homework/{sub_id}/submit", headers=headers, json={"student_comment": "done"})
        r = client.post(f"{API}/homework/submissions/{sub_id}/review", headers=school["ha"],
                        json={"status": "reviewed", "grade": grade})
        assert r.status_code == 200, r.text


def test_student_progress(client, school):
    s1 = school["s1"].id
    _test(client, school, s1, right=2, passing=60)  # 50%, not passed
    _test(client, school, s1, right=4)  # 100%
    _homework(client, school, s1, grade=8)  # 80%
    lid = _lesson(client, school, [s1])
    _mark(client, school, lid, [(s1, "present")])
    lid = _lesson(client, school, [s1], days_ago=2)
    _mark(client, school, lid, [(s1, "absent")])

    me = client.get(f"{API}/analytics/me", headers=school["h1"]).json()
    teacher_view = client.get(f"{API}/analytics/students/{s1}", headers=school["ha"]).json()
    assert me["summary"] == teacher_view["summary"]
    assert me["summary"]["avg_test"] == 75 and me["summary"]["tests_count"] == 2
    assert me["summary"]["avg_homework"] == 80 and me["summary"]["on_time_rate"] == 100
    assert me["summary"]["attendance_rate"] == 50 and me["summary"]["test_trend"] is None
    assert [p["percent"] for p in me["tests"]] == [50, 100]
    assert me["tests"][0]["passed"] is False and me["tests"][1]["passed"] is None
    assert len(me["attendance"]) == 6 and me["attendance"][-1]["rate"] in (50, 100, 0)
    assert sum(m["present"] + m["absent"] for m in me["attendance"]) == 2


def test_progress_access(client, school):
    s1 = school["s1"].id
    assert client.get(f"{API}/analytics/students/{s1}", headers=school["hb"]).status_code == 404
    assert client.get(f"{API}/analytics/students/{s1}", headers=school["h1"]).status_code == 403
    assert client.get(f"{API}/analytics/overview", headers=school["h1"]).status_code == 403
    assert client.get(f"{API}/analytics/me", headers=school["ha"]).status_code == 403


def test_overview_flags_students_needing_attention(client, school):
    s1, s2 = school["s1"].id, school["s2"].id
    # s2: low attendance (1 of 3), low tests, two overdue homeworks
    for status in ("present", "absent", "absent"):
        _mark(client, school, _lesson(client, school, [s2]), [(s2, status)])
    _test(client, school, s2, right=1)  # 25%
    _homework(client, school, s2, due_in_days=-1)
    _homework(client, school, s2, due_in_days=-3)
    # s1: fine
    _mark(client, school, _lesson(client, school, [s1]), [(s1, "present")])
    _test(client, school, s1, right=4)

    ov = client.get(f"{API}/analytics/overview", headers=school["ha"]).json()
    assert ov["students"] == 2 and ov["at_risk"] == 1 and ov["period_days"] == 90
    first, second = ov["rows"]
    assert first["student_id"] == s2  # needing attention first
    assert set(first["risks"]) == {"low_attendance", "low_tests", "overdue_homework"}
    assert first["attendance_rate"] == 33 and first["overdue_homework"] == 2 and first["avg_test"] == 25
    assert second["risks"] == [] and second["avg_test"] == 100
    assert ov["avg_test"] == 62  # (25 + 100) / 2, rounded half to even
    assert ov["attendance_rate"] == 50  # 2 of 4 visits across students


def test_overview_filters(client, school):
    g = client.post(f"{API}/groups", headers=school["aa"], json={"name": "A1", "student_ids": [school["s1"].id]}).json()
    ov = client.get(f"{API}/analytics/overview", headers=school["ha"], params={"group_id": g["id"], "period": 30}).json()
    assert [r["student_id"] for r in ov["rows"]] == [school["s1"].id] and ov["period_days"] == 30
    assert client.get(f"{API}/analytics/overview", headers=school["hb"], params={"group_id": g["id"]}).status_code == 404
    assert client.get(f"{API}/analytics/overview", headers=school["ha"], params={"period": 400}).status_code == 422
    # a student who never signed in or did anything is flagged as inactive; one who signed in is not
    make_user(UserRole.STUDENT, "quiet@test.io", school["tb"], "Quiet One")
    rows = {r["full_name"]: r for r in client.get(f"{API}/analytics/overview", headers=school["hb"]).json()["rows"]}
    assert rows["Quiet One"]["risks"] == ["inactive"] and rows["Quiet One"]["last_activity"] is None
    assert rows["Student Three"]["risks"] == [] and rows["Student Three"]["last_activity"] is not None

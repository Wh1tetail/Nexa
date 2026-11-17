"""Stage 19: XP, achievements, streaks and the admin's XP settings."""
from datetime import timedelta

from sqlalchemy import select
from conftest import _assign
from test_attempt_history import _create, _start, _submit

from app.core.database import SessionLocal
from app.models import CourseLesson, StudentActivityDay, StudentProfile, XPTransaction
from app.services import gamification as gm

API = "/api/v1"


def _do_lesson(client, h, lesson, right=True):
    """Check every exercise of a lesson (right or wrong answers) and finish it."""
    v = client.get(f"{API}/me/course-lessons/{lesson['id']}", headers=h).json()
    for b in v["lesson"]["blocks"]:
        if b["questions"]:
            answers = {}
            for i, q in enumerate(b["questions"]):
                if q["type"] == "fill_gaps":
                    answers[str(i)] = ["am" if right else "is"]
                else:
                    answers[str(i)] = ["a" if right else "b"]
            client.post(f"{API}/me/course-lessons/{lesson['id']}/blocks/{b['id']}/check", headers=h, json={"answers": answers})
    return client.post(f"{API}/me/course-lessons/{lesson['id']}/complete", headers=h).json()


def _me(client, h):
    return client.get(f"{API}/me/gamification", headers=h).json()


def test_lesson_module_level_xp_paid_once(client, course):
    h1, s1 = course["h1"], course["s1"]
    _assign(client, course["ha"], course, module_id=course["m1"], student_ids=[s1.id])

    r = _do_lesson(client, h1, course["l2"])  # no exercises
    assert r["awards"] == {"xp": 10, "achievements": ["first_lesson"]}
    again = client.post(f"{API}/me/course-lessons/{course['l2']['id']}/complete", headers=h1).json()
    assert again["awards"] == {"xp": 0, "achievements": []}  # completing again pays nothing

    # the last lesson of the module: lesson + module; all answers right: perfect score
    r = _do_lesson(client, h1, course["l1"])
    assert r["awards"]["xp"] == 10 + 30 and r["awards"]["achievements"] == ["perfect_score"]

    # the other module completes the level
    _assign(client, course["ha"], course, module_id=course["m2"], student_ids=[s1.id])
    r = _do_lesson(client, h1, course["l3"])
    assert r["awards"]["xp"] == 10 + 30 + 100 and r["awards"]["achievements"] == ["level_completed"]

    me = _me(client, h1)
    assert me["xp_total"] == 190 and me["level"] == 2 and me["level_xp"] == 100 and me["next_level_xp"] == 300
    assert [e["reason"] for e in me["recent"]][:3] == ["level", "module", "lesson"]
    assert me["recent"][0]["title"] == "General English · A1 Beginner"
    earned = {a["code"] for a in me["achievements"] if a["earned_at"]}
    assert earned == {"first_lesson", "perfect_score", "level_completed"}
    ten = next(a for a in me["achievements"] if a["code"] == "lessons_10")
    assert (ten["progress"], ten["target"]) == (3, 10)

    # even a direct repeat (e.g. two requests racing) can't pay twice
    with SessionLocal() as db:
        student = db.get(StudentProfile, s1.id)
        lesson = db.get(CourseLesson, course["l3"]["id"])
        assert gm.on_lesson_completed(db, student, lesson).xp == 0
        db.commit()
        assert db.scalar(select(XPTransaction.points).where(XPTransaction.ref_key == f"lesson:{lesson.id}")) == 10
    assert _me(client, h1)["xp_total"] == 190

    # the teacher sees it; another teacher doesn't
    assert client.get(f"{API}/students/{s1.id}/gamification", headers=course["ha"]).json()["xp_total"] == 190
    assert client.get(f"{API}/students/{s1.id}/gamification", headers=course["hb"]).status_code == 404


def test_test_xp_bonus_and_review(client, school):
    h1 = school["h1"]
    t = _create(client, school, max_attempts=3)
    a = _start(client, school, t["id"]).json()
    _submit(client, school, t, a["id"], right=3)  # 75%: XP, no bonus
    me = _me(client, h1)
    assert me["xp_total"] == 5 and {x["code"] for x in me["achievements"] if x["earned_at"]} == {"first_test"}
    # a better retake adds only the bonus; the test itself is paid once
    a = _start(client, school, t["id"], retake=True).json()
    _submit(client, school, t, a["id"], right=4)
    me = _me(client, h1)
    assert me["xp_total"] == 10 and [e["reason"] for e in me["recent"]] == ["test_bonus", "test"]
    assert "perfect_score" in {x["code"] for x in me["achievements"] if x["earned_at"]}
    a = _start(client, school, t["id"], retake=True).json()
    _submit(client, school, t, a["id"], right=4)
    assert _me(client, h1)["xp_total"] == 10

    # a test that needs the teacher's review pays only once it is graded
    q = [{"type": "short_answer", "text": "Your name?", "points": 2, "correct_answer": []}]
    t2 = client.post(f"{API}/tests", headers=school["ha"], json={"title": "Essay", "questions": q, "student_ids": [school["s1"].id]}).json()
    a = _start(client, school, t2["id"]).json()
    r = client.post(f"{API}/me/tests/attempts/{a['id']}/submit", headers=h1,
                    json={"answers": [{"question_id": t2["questions"][0]["id"], "answer": ["Anna"]}]}).json()
    assert r["status"] == "pending_review" and _me(client, h1)["xp_total"] == 10
    detail = client.get(f"{API}/tests/attempts/{a['id']}", headers=school["ha"]).json()
    client.post(f"{API}/tests/attempts/{a['id']}/grade", headers=school["ha"],
                json={"answers": [{"answer_id": detail["answers"][0]["id"], "points_awarded": 2}]})
    assert _me(client, h1)["xp_total"] == 20  # 5 + bonus 5 (100%)


def test_admin_settings_and_rights(client, course):
    h1, s1 = course["h1"], course["s1"]
    adm = course["adm"]
    assert client.get(f"{API}/admin/gamification", headers=adm).json() == {
        "lesson": 10, "test": 5, "test_bonus": 5, "bonus_threshold": 90, "module": 30, "level": 100}
    new = {"lesson": 25, "test": 5, "test_bonus": 5, "bonus_threshold": 80, "module": 0, "level": 100}
    assert client.put(f"{API}/admin/gamification", headers=adm, json=new).json() == new
    assert client.put(f"{API}/admin/gamification", headers=adm, json={**new, "bonus_threshold": 40}).status_code == 422
    assert client.put(f"{API}/admin/gamification", headers=course["ha"], json=new).status_code == 403
    assert client.get(f"{API}/admin/gamification", headers=h1).status_code == 403

    _assign(client, course["ha"], course, module_id=course["m1"], student_ids=[s1.id])
    _do_lesson(client, h1, course["l2"])
    r = _do_lesson(client, h1, course["l1"])
    assert r["awards"]["xp"] == 25  # new value; a module worth 0 pays nothing
    me = _me(client, h1)
    assert me["settings"]["lesson"] == 25 and me["xp_total"] == 50


def test_seven_day_streak(client, course):
    h1, s1 = course["h1"], course["s1"]
    _assign(client, course["ha"], course, module_id=course["m1"], student_ids=[s1.id])
    with SessionLocal() as db:
        student = db.get(StudentProfile, s1.id)
        today = gm._today(student)
        db.add_all([StudentActivityDay(student_id=s1.id, day=today - timedelta(days=d)) for d in range(1, 7)])
        db.add(StudentActivityDay(student_id=s1.id, day=today - timedelta(days=9)))  # an older, separate run
        db.commit()
    assert _me(client, h1)["streak_days"] == 6  # up to yesterday
    r = _do_lesson(client, h1, course["l2"])  # today's activity makes 7
    assert "streak_7" in r["awards"]["achievements"]
    me = _me(client, h1)
    assert me["streak_days"] == 7
    streak = next(a for a in me["achievements"] if a["code"] == "streak_7")
    assert streak["earned_at"] and (streak["progress"], streak["target"]) == (7, 7)

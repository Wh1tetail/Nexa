"""Several attempts per test: history is kept, the best result counts."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models import Test
from app.models.test import test_assignments

API = "/api/v1"


def _questions(n=4):
    return [{
        "type": "single_choice", "text": f"Q{i}", "points": 1,
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "correct_answer": ["a"],
    } for i in range(n)]


def _create(client, school, **fields):
    body = {"title": "Grammar", "questions": _questions(), "student_ids": [school["s1"].id], **fields}
    r = client.post(f"{API}/tests", headers=school["ha"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _start(client, school, test_id, retake=False):
    return client.post(f"{API}/me/tests/{test_id}/start", headers=school["h1"], params={"retake": retake})


def _submit(client, school, test, attempt_id, right):
    answers = [{"question_id": q["id"], "answer": ["a" if i < right else "b"]}
               for i, q in enumerate(test["questions"])]
    r = client.post(f"{API}/me/tests/attempts/{attempt_id}/submit", headers=school["h1"], json={"answers": answers})
    assert r.status_code == 200, r.text
    return r.json()


def _item(client, school):
    return client.get(f"{API}/me/tests", headers=school["h1"]).json()[0]


def test_three_attempts_keep_history_and_best_counts(client, school):
    t = _create(client, school, max_attempts=3)
    assert t["max_attempts"] == 3
    first = _start(client, school, t["id"]).json()
    assert first["number"] == 1
    _submit(client, school, t, first["id"], right=3)  # 75%

    item = _item(client, school)
    assert (item["attempts_used"], item["attempts_allowed"], item["can_retake"]) == (1, 3, True)
    # opening without retake shows the finished attempt, it does not start a new one
    assert _start(client, school, t["id"]).json()["id"] == first["id"]

    second = _start(client, school, t["id"], retake=True).json()
    assert second["number"] == 2 and second["id"] != first["id"]
    # an unfinished attempt is continued, never doubled
    assert _start(client, school, t["id"], retake=True).json()["id"] == second["id"]
    _submit(client, school, t, second["id"], right=1)  # 25%

    third = _start(client, school, t["id"], retake=True).json()
    _submit(client, school, t, third["id"], right=2)  # 50%
    item = _item(client, school)
    assert item["attempts_used"] == 3 and item["can_retake"] is False
    assert item["percent"] == 50 and item["best_percent"] == 75  # latest vs best
    r = _start(client, school, t["id"], retake=True)
    assert r.status_code == 400 and r.json()["detail"] == "Попытки закончились"

    history = client.get(f"{API}/me/tests/{t['id']}/attempts", headers=school["h1"]).json()
    assert [(a["number"], a["percent"]) for a in history] == [(3, 50), (2, 25), (1, 75)]
    teacher = client.get(f"{API}/tests/{t['id']}/attempts", headers=school["ha"]).json()
    assert sorted(a["number"] for a in teacher) == [1, 2, 3]
    # another student's history is not visible
    assert client.get(f"{API}/me/tests/{t['id']}/attempts", headers=school["h2"]).status_code == 404

    # analytics use the best attempt only
    progress = client.get(f"{API}/analytics/students/{school['s1'].id}", headers=school["ha"]).json()
    assert [p["percent"] for p in progress["tests"]] == [75]


def test_one_attempt_by_default_and_teacher_grant_ignores_deadline(client, school):
    t = _create(client, school)  # max_attempts = 1, as before
    first = _start(client, school, t["id"]).json()
    _submit(client, school, t, first["id"], right=1)
    assert _item(client, school)["can_retake"] is False
    assert _start(client, school, t["id"], retake=True).status_code == 400

    # the deadline passes, then the teacher allows one more attempt
    with SessionLocal() as db:
        db.get(Test, t["id"]).due_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    assert client.post(f"{API}/tests/attempts/{first['id']}/retake", headers=school["ha"]).status_code == 204
    item = _item(client, school)
    assert item["can_retake"] is True and item["attempts_allowed"] == 2 and item["is_overdue"] is False
    second = _start(client, school, t["id"], retake=True).json()
    assert _submit(client, school, t, second["id"], right=4)["percent"] == 100
    assert _item(client, school)["best_percent"] == 100


def test_regular_attempts_respect_the_deadline(client, school):
    t = _create(client, school, max_attempts=2)
    first = _start(client, school, t["id"]).json()
    _submit(client, school, t, first["id"], right=1)
    with SessionLocal() as db:
        db.get(Test, t["id"]).due_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert _item(client, school)["can_retake"] is False
    r = _start(client, school, t["id"], retake=True)
    assert r.status_code == 400 and r.json()["detail"] == "Срок сдачи теста истёк"


def test_retake_needs_the_test_still_assigned(client, school):
    t = _create(client, school)
    first = _start(client, school, t["id"]).json()
    _submit(client, school, t, first["id"], right=1)
    with SessionLocal() as db:  # the student is no longer assigned
        db.execute(delete(test_assignments).where(test_assignments.c.test_id == t["id"]))
        db.commit()
    r = client.post(f"{API}/tests/attempts/{first['id']}/retake", headers=school["ha"])
    assert r.status_code == 400


def test_max_attempts_is_validated(client, school):
    for bad in (0, 11):
        r = client.post(f"{API}/tests", headers=school["ha"], json={
            "title": "X", "questions": _questions(), "max_attempts": bad})
        assert r.status_code == 422

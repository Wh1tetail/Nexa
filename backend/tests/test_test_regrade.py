"""The teacher may change the points of any answer of a finished attempt, auto-graded ones included."""
from test_attempt_history import _create, _start, _submit

from app.core.database import SessionLocal
from app.models import Notification
from app.models.enums import NotificationType

API = "/api/v1"


def _grade(client, school, attempt_id, grades, headers=None):
    return client.post(f"{API}/tests/attempts/{attempt_id}/grade", headers=headers or school["ha"],
                       json={"answers": grades})


def test_teacher_changes_auto_graded_points(client, school):
    t = _create(client, school)
    a = _start(client, school, t["id"]).json()
    r = _submit(client, school, t, a["id"], right=2)  # auto-graded: 2 of 4
    assert r["status"] == "graded" and r["score"] == 2

    detail = client.get(f"{API}/tests/attempts/{a['id']}", headers=school["ha"]).json()
    by_q = {x["question_id"]: x for x in detail["answers"]}
    wrong = by_q[t["questions"][3]["id"]]
    right = by_q[t["questions"][0]["id"]]
    assert wrong["points_awarded"] == 0 and right["points_awarded"] == 1

    # a wrong answer counted as right, a right one docked half a point
    r = _grade(client, school, a["id"], [
        {"answer_id": wrong["id"], "points_awarded": 1, "teacher_comment": "Accepted"},
        {"answer_id": right["id"], "points_awarded": 0.5},
    ])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["score"] == 2.5 and d["percent"] == 62 and d["status"] == "graded"
    by_q = {x["question_id"]: x for x in d["answers"]}
    assert by_q[wrong["question_id"]]["is_correct"] is True
    assert by_q[wrong["question_id"]]["teacher_comment"] == "Accepted"
    assert by_q[right["question_id"]]["is_correct"] is False

    # the student sees the new result and is told about the change
    mine = client.get(f"{API}/me/tests/attempts/{a['id']}", headers=school["h1"]).json()
    assert mine["score"] == 2.5
    with SessionLocal() as db:
        titles = [n.title for n in db.query(Notification).filter_by(
            user_id=school["s1"].user_id, type=NotificationType.TEST_GRADED).order_by(Notification.id)]
    assert titles[-1] == "Оценка за тест изменена"

    # saving the same points again sends nothing new
    _grade(client, school, a["id"], [{"answer_id": wrong["id"], "points_awarded": 1}])
    with SessionLocal() as db:
        n = db.query(Notification).filter_by(user_id=school["s1"].user_id, type=NotificationType.TEST_GRADED).count()
    assert n == len(titles)

    # limits and ownership
    r = _grade(client, school, a["id"], [{"answer_id": wrong["id"], "points_awarded": 2}])
    assert r.status_code == 400 and r.json()["detail"] == "Максимум за вопрос — 1 балл(ов)"
    assert _grade(client, school, a["id"], [{"answer_id": wrong["id"], "points_awarded": -1}]).status_code == 422
    assert _grade(client, school, a["id"], [], headers=school["hb"]).status_code == 404

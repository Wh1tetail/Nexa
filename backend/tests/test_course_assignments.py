"""Stage 18: assigning courses to students and groups, students' lessons and progress."""
from datetime import UTC, datetime, timedelta

import pytest
from conftest import clear_subscriptions, login, make_user

from app.core.database import SessionLocal
from app.models import LessonProgress, Notification
from app.models.enums import NotificationType, UserRole

API = "/api/v1"
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x0f" + b"\x00" * 64
CHOICE = {"type": "single_choice", "text": "She ___ to school.", "points": 1, "correct_answer": ["a"],
          "options": [{"id": "a", "text": "goes"}, {"id": "b", "text": "go"}]}
GAPS = {"type": "fill_gaps", "text": "Complete", "config": {"template": "I {am} Anna."}}


@pytest.fixture
def course(client, school):
    """A published course: A1 / Module 1 (Lesson 1 with exercises and a listening, Lesson 2 text only),
    Module 2 (one lesson) and a draft lesson."""
    make_user(UserRole.METHODIST, "method@test.io", name="Mila Methodist")
    hm = login(client, "method@test.io")
    c = client.post(f"{API}/courses", headers=hm, json={"title": "General English", "levels": ["A1"], "published": True}).json()
    a1 = c["levels"][0]["id"]
    tree = client.post(f"{API}/courses/levels/{a1}/modules", headers=hm, json={"title": "Introduction"}).json()
    tree = client.post(f"{API}/courses/levels/{a1}/modules", headers=hm, json={"title": "Daily Life"}).json()
    m1, m2 = (m["id"] for m in tree["levels"][0]["modules"])

    def lesson(module, title, blocks, published=True):
        les = client.post(f"{API}/courses/modules/{module}/lessons", headers=hm, json={"title": title}).json()
        r = client.put(f"{API}/courses/lessons/{les['id']}", headers=hm,
                       json={"title": title, "published": published, "blocks": blocks(les["id"])})
        assert r.status_code == 200, r.text
        return r.json()

    def first_blocks(lid):
        f = client.post(f"{API}/courses/lessons/{lid}/files", headers=hm,
                        files=[("files", ("hello.mp3", MP3, "audio/mpeg"))]).json()[0]["id"]
        return [{"type": "text", "content": {"body": "Hello"}},
                {"type": "quiz", "questions": [CHOICE, GAPS]},
                {"type": "listening", "content": {"attachment_id": f, "max_plays": 2}, "questions": [CHOICE]}]

    l1 = lesson(m1, "Greetings", first_blocks)
    l2 = lesson(m1, "Countries", lambda _: [{"type": "text", "content": {"body": "Spain"}}])
    l3 = lesson(m2, "Routine", lambda _: [{"type": "text", "content": {"body": "Every day"}}])
    draft = lesson(m1, "Draft", lambda _: [{"type": "text", "content": {"body": "x"}}], published=False)
    group = client.post(f"{API}/groups", headers=school["aa"], json={"name": "A1 mornings", "student_ids": [school["s1"].id]}).json()
    return {**school, "hm": hm, "course": c["id"], "a1": a1, "m1": m1, "m2": m2,
            "l1": l1, "l2": l2, "l3": l3, "draft": draft, "group": group["id"]}


def _assign(client, h, course, **body):
    return client.post(f"{API}/course-assignments", headers=h, json={"course_id": course["course"], **body})


def test_assign_to_group_and_students_without_duplicates(client, course):
    ha = course["ha"]
    s1, s2, s3 = course["s1"], course["s2"], course["s3"]
    r = _assign(client, ha, course, module_id=course["m1"], group_ids=[course["group"]], student_ids=[s2.id])
    assert r.status_code == 201, r.text
    assert r.json()["assigned"] == 2 and r.json()["skipped"] == 0 and len(r.json()["assignment_ids"]) == 2
    # the same again: nobody new, no new assignments
    r = _assign(client, ha, course, module_id=course["m1"], group_ids=[course["group"]], student_ids=[s1.id, s2.id])
    assert r.json() == {"assignment_ids": [], "assigned": 0, "skipped": 2}
    # the whole level is a different (bigger) part: allowed; then the module inside it counts as covered
    assert _assign(client, ha, course, level_id=course["a1"], student_ids=[s2.id]).json()["assigned"] == 1
    assert _assign(client, ha, course, module_id=course["m2"], student_ids=[s2.id]).json()["skipped"] == 1

    with SessionLocal() as db:
        n = db.query(Notification).filter_by(user_id=s1.user_id, type=NotificationType.COURSE_ASSIGNED).one()
        assert n.title == "Новый курс: General English" and n.body == "Назначено: Introduction"

    mine = client.get(f"{API}/me/courses", headers=course["h1"]).json()
    assert len(mine) == 1 and mine[0]["scope_title"] == "Introduction" and mine[0]["lessons_total"] == 2
    assert mine[0]["teacher_name"] == "Teacher A" and mine[0]["next_lesson_id"] == course["l1"]["id"]
    assert client.get(f"{API}/me/courses", headers=course["h3"]).json() == []
    lessons = client.get(f"{API}/me/course-lessons", headers=course["h2"]).json()
    assert [x["title"] for x in lessons] == ["Greetings", "Countries", "Routine"]  # no draft, each once

    # only own students and groups; validation
    assert _assign(client, course["hb"], course, module_id=course["m1"], student_ids=[s1.id]).status_code == 403
    assert _assign(client, course["hb"], course, module_id=course["m1"], group_ids=[course["group"]]).status_code == 404
    assert _assign(client, ha, course, module_id=course["m1"]).status_code == 422
    assert _assign(client, ha, course, student_ids=[s1.id]).status_code == 422
    assert _assign(client, course["h1"], course, module_id=course["m1"], student_ids=[s1.id]).status_code == 403
    assert s3  # (teacher B's student is never visible to teacher A)

    # a course that is not published can't be assigned (teachers don't see it)
    client.put(f"{API}/courses/{course['course']}", headers=course["hm"], json={"title": "General English", "published": False})
    assert _assign(client, ha, course, module_id=course["m2"], student_ids=[s1.id]).status_code == 404
    assert client.get(f"{API}/me/courses", headers=course["h1"]).json() == []


def test_lesson_work_is_saved_and_completed_once(client, course):
    h1, s1 = course["h1"], course["s1"]
    later = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    a = _assign(client, course["ha"], course, module_id=course["m1"], student_ids=[s1.id], starts_at=later).json()
    lid = course["l1"]["id"]
    # not started yet: listed, but closed
    item = client.get(f"{API}/me/courses", headers=h1).json()[0]
    assert item["started"] is False and item["next_lesson_id"] is None
    assert client.get(f"{API}/me/course-lessons/{lid}", headers=h1).status_code == 404
    aid = a["assignment_ids"][0]
    client.patch(f"{API}/course-assignments/{aid}", headers=course["ha"],
                 json={"starts_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()})

    v = client.get(f"{API}/me/course-lessons/{lid}", headers=h1).json()
    assert v["status"] == "not_started" and v["exercises_total"] == 2 and v["exercises_done"] == 0
    quiz = next(b for b in v["lesson"]["blocks"] if b["type"] == "quiz")
    listening = next(b for b in v["lesson"]["blocks"] if b["type"] == "listening")
    assert quiz["questions"][0]["correct_answer"] is None
    assert v["lesson"]["path"]["next_id"] == course["l2"]["id"] and v["lesson"]["path"]["prev_id"] is None
    assert client.get(f"{API}/me/course-lessons/{course['draft']['id']}", headers=h1).status_code == 404
    assert client.get(f"{API}/me/course-lessons/{course['l3']['id']}", headers=h1).status_code == 404  # other module

    # finishing needs every exercise checked
    r = client.post(f"{API}/me/course-lessons/{lid}/complete", headers=h1)
    assert r.status_code == 400 and r.json()["detail"] == "Сначала выполните все упражнения урока"
    check = f"{API}/me/course-lessons/{lid}/blocks/{quiz['id']}/check"
    r = client.post(check, headers=h1, json={"answers": {"0": ["b"], "1": ["is"]}}).json()
    assert r["score"] == 0 and r["questions"][0]["correct_answer"] == ["a"]
    r = client.post(check, headers=h1, json={"answers": {"0": ["a"], "1": ["am"]}}).json()
    assert r["score"] == 2
    client.post(check, headers=h1, json={"answers": {"0": ["b"], "1": ["am"]}})  # worse later: the best counts

    # listening limit is counted on the server
    play = f"{API}/me/course-lessons/{lid}/plays/{listening['id']}"
    assert client.post(play, headers=h1).json() == {"plays": 1, "max_plays": 2}
    assert client.post(play, headers=h1).json()["plays"] == 2
    r = client.post(play, headers=h1)
    assert r.status_code == 400 and r.json()["detail"] == "Лимит прослушиваний исчерпан"
    client.post(f"{API}/me/course-lessons/{lid}/blocks/{listening['id']}/check", headers=h1, json={"answers": {"0": ["a"]}})

    # everything is still there in a new session
    v = client.get(f"{API}/me/course-lessons/{lid}", headers=login(client, "s1@test.io")).json()
    saved = next(b for b in v["blocks"] if b["block_id"] == quiz["id"])
    assert saved["answers"] == {"0": ["b"], "1": ["am"]} and saved["attempts"] == 3 and saved["best_percent"] == 100
    assert saved["result"]["score"] == 1 and v["plays"] == {str(listening["id"]): 2}
    assert v["status"] == "in_progress" and v["exercises_done"] == 2

    done = client.post(f"{API}/me/course-lessons/{lid}/complete", headers=h1).json()
    assert done["status"] == "completed" and done["score_percent"] == 100
    again = client.post(f"{API}/me/course-lessons/{lid}/complete", headers=h1).json()
    assert again["completed_at"] == done["completed_at"]  # never twice

    # a lesson without exercises can be finished right away
    assert client.post(f"{API}/me/course-lessons/{course['l2']['id']}/complete", headers=h1).json()["status"] == "completed"

    # course page, "my progress" and the teacher's view agree
    detail = client.get(f"{API}/me/courses/{aid}", headers=h1).json()
    assert detail["percent"] == 100 and detail["modules"][0]["completed"] is True
    p = client.get(f"{API}/me/course-progress", headers=h1).json()
    assert p["english_level"] == "A1" and p["lessons_completed"] == 2 and p["lessons_remaining"] == 0
    assert p["modules_completed"] == 1 and p["exercises_done"] == 2 and p["avg_score"] == 100
    assert p["items"][0]["level_title"] == "A1 Beginner" and p["items"][0]["percent"] == 100
    t = client.get(f"{API}/course-assignments/{aid}", headers=course["ha"]).json()
    assert t["students"][0]["percent"] == 100 and t["completed_count"] == 1 and t["avg_percent"] == 100
    overview = client.get(f"{API}/course-assignments/students", headers=course["ha"]).json()
    assert overview[0]["lessons_completed"] == 2 and overview[0]["assignments"] == 1
    assert client.get(f"{API}/course-assignments/students/{s1.id}/progress", headers=course["ha"]).json()["lessons_completed"] == 2
    assert client.get(f"{API}/course-assignments/students/{s1.id}/progress", headers=course["hb"]).status_code == 404

    # lesson files: the student while assigned; nobody else
    file_id = next(b for b in v["lesson"]["blocks"] if b["type"] == "listening")["content"]["attachment_id"]
    assert client.get(f"{API}/files/{file_id}", headers=h1).status_code == 200
    assert client.get(f"{API}/files/{file_id}", headers=course["h2"]).status_code == 404

    # no subscription: no courses
    clear_subscriptions(s1)
    r = client.get(f"{API}/me/courses", headers=h1)
    assert r.status_code == 403 and r.json()["code"] == "subscription_required"


def test_groups_cancelling_and_history(client, course):
    ha, s1, s2 = course["ha"], course["s1"], course["s2"]
    aid = _assign(client, ha, course, module_id=course["m1"], group_ids=[course["group"]]).json()["assignment_ids"][0]
    lid = course["l2"]["id"]
    client.post(f"{API}/me/course-lessons/{lid}/complete", headers=course["h1"])

    # s2 joins the group: gets its course; s1 leaves: loses it, progress stays
    client.patch(f"{API}/groups/{course['group']}", headers=ha, json={"student_ids": [s2.id]})
    assert len(client.get(f"{API}/me/courses", headers=course["h2"]).json()) == 1
    assert client.get(f"{API}/me/courses", headers=course["h1"]).json() == []
    d = client.get(f"{API}/course-assignments/{aid}", headers=ha).json()
    assert {(r["student_id"], r["removed_at"] is None) for r in d["students"]} == {(s1.id, False), (s2.id, True)}
    assert next(r for r in d["students"] if r["student_id"] == s1.id)["lessons_completed"] == 1

    # coming back to the group brings the assignment and the earlier progress back
    client.patch(f"{API}/groups/{course['group']}", headers=ha, json={"student_ids": [s1.id, s2.id]})
    assert client.get(f"{API}/me/courses", headers=course["h1"]).json()[0]["lessons_completed"] == 1

    # the teacher takes one student off, then cancels the assignment
    client.delete(f"{API}/course-assignments/{aid}/students/{s2.id}", headers=ha)
    assert client.get(f"{API}/me/courses", headers=course["h2"]).json() == []
    assert client.delete(f"{API}/course-assignments/{aid}", headers=ha).status_code == 204
    assert client.get(f"{API}/me/courses", headers=course["h1"]).json() == []
    assert client.get(f"{API}/course-assignments", headers=ha).json() == []
    assert len(client.get(f"{API}/course-assignments?include_removed=true", headers=ha).json()) == 1
    assert client.get(f"{API}/course-assignments/{aid}", headers=course["hb"]).status_code == 404


def test_assigned_content_is_protected_and_history_kept(client, course):
    hm, s1 = course["hm"], course["s1"]
    _assign(client, course["ha"], course, module_id=course["m1"], student_ids=[s1.id])
    msg = "Эта часть курса назначена ученикам — удалить её нельзя. Можно снять уроки с публикации"
    for url in (f"/courses/modules/{course['m1']}", f"/courses/levels/{course['a1']}", f"/courses/{course['course']}"):
        r = client.delete(f"{API}{url}", headers=hm)
        assert r.status_code == 400 and r.json()["detail"] == msg, url
    assert client.delete(f"{API}/courses/modules/{course['m2']}", headers=hm).status_code == 200  # not assigned

    lid = course["l2"]["id"]
    client.post(f"{API}/me/course-lessons/{lid}/complete", headers=course["h1"])
    # a lesson can be deleted; the student's record of it stays
    assert client.delete(f"{API}/courses/lessons/{lid}", headers=hm).status_code == 200
    with SessionLocal() as db:
        p = db.query(LessonProgress).filter_by(student_id=s1.id).one()
        assert p.lesson_id is None and p.lesson_title == "Countries" and p.completed_at is not None
    item = client.get(f"{API}/me/courses", headers=course["h1"]).json()[0]
    assert item["lessons_total"] == 1 and item["lessons_completed"] == 0

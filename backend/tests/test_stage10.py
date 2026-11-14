"""Stage 10: menu counters per section, test materials and test settings."""
from datetime import UTC, datetime, timedelta

from conftest import login, make_user

from app.models.enums import UserRole

API = "/api/v1"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
PDF = b"%PDF-1.4\n%reading\n"


def _questions(n=3, **extra):
    qs = []
    for i in range(n):
        qs.append({
            "type": "single_choice", "text": f"Q{i}", "points": 1,
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"},
                        {"id": "d", "text": "D"}],
            "correct_answer": ["a"], "explanation": f"Because {i}", **extra,
        })
    return qs


def _create(client, school, **fields):
    body = {"title": "Listening", "questions": _questions(), "student_ids": [school["s1"].id], **fields}
    r = client.post(f"{API}/tests", headers=school["ha"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- counters in the side menu ----------

def test_unread_counters_per_section(client, school):
    _create(client, school)  # -> "test_assigned" for s1
    client.post(f"{API}/homework", headers=school["ha"], json={
        "title": "Essay", "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "student_ids": [school["s1"].id]})
    h = school["h1"]
    counts = client.get(f"{API}/notifications/unread-by-section", headers=h).json()
    assert counts == {"homework": 1, "tests": 1, "lessons": 0, "subscription": 0}

    # opening the section marks only its notifications as seen
    assert client.post(f"{API}/notifications/read-section", headers=h, json={"section": "tests"}).json() == {"count": 1}
    counts = client.get(f"{API}/notifications/unread-by-section", headers=h).json()
    assert counts["tests"] == 0 and counts["homework"] == 1
    assert client.get(f"{API}/notifications/unread-count", headers=h).json() == {"count": 1}
    assert client.post(f"{API}/notifications/read-section", headers=h, json={"section": "spam"}).status_code == 422


# ---------- materials ----------

def test_test_materials_and_question_files(client, school):
    t = _create(client, school)
    tid = t["id"]
    r = client.post(f"{API}/tests/{tid}/files", headers=school["ha"],
                    files=[("files", ("text.pdf", PDF, "application/pdf")), ("files", ("pic.png", PNG, "image/png"))])
    assert r.status_code == 201, r.text
    pdf_id, png_id = [f["id"] for f in r.json()]

    # another teacher cannot touch them
    assert client.post(f"{API}/tests/{tid}/files", headers=school["hb"],
                       files=[("files", ("x.png", PNG, "image/png"))]).status_code == 404

    # attach the picture to question 1; foreign ids are rejected
    qs = _questions()
    qs[1]["attachment_ids"] = [png_id]
    body = {"title": "Listening", "questions": qs, "student_ids": [school["s1"].id]}
    detail = client.put(f"{API}/tests/{tid}", headers=school["ha"], json=body).json()
    assert detail["questions"][1]["attachment_ids"] == [png_id]
    assert [f["original_name"] for f in detail["files"]] == ["text.pdf", "pic.png"]
    qs[0]["attachment_ids"] = [999999]
    assert client.put(f"{API}/tests/{tid}", headers=school["ha"],
                      json={**body, "questions": qs}).status_code == 400

    # the student sees the files only after starting the test
    assert client.get(f"{API}/files/{pdf_id}", headers=school["h1"]).status_code == 404
    attempt = client.post(f"{API}/me/tests/{tid}/start", headers=school["h1"]).json()
    assert {f["id"] for f in attempt["files"]} == {pdf_id, png_id}
    assert client.get(f"{API}/files/{pdf_id}", headers=school["h1"]).content == PDF
    assert client.get(f"{API}/files/{pdf_id}", headers=school["h2"]).status_code == 404  # not assigned

    # once started, materials are locked
    assert client.delete(f"{API}/tests/{tid}/files/{pdf_id}", headers=school["ha"]).status_code == 400


def test_deleting_a_file_detaches_it_from_questions(client, school):
    t = _create(client, school)
    tid = t["id"]
    fid = client.post(f"{API}/tests/{tid}/files", headers=school["ha"],
                      files=[("files", ("pic.png", PNG, "image/png"))]).json()[0]["id"]
    qs = _questions()
    qs[0]["attachment_ids"] = [fid]
    client.put(f"{API}/tests/{tid}", headers=school["ha"], json={"title": "T", "questions": qs})
    assert client.delete(f"{API}/tests/{tid}/files/{fid}", headers=school["ha"]).status_code == 204
    detail = client.get(f"{API}/tests/{tid}", headers=school["ha"]).json()
    assert detail["files"] == [] and detail["questions"][0]["attachment_ids"] == []


# ---------- settings ----------

def test_available_from_blocks_start(client, school):
    later = datetime.now(UTC) + timedelta(days=1)
    t = _create(client, school, available_from=later.isoformat())
    item = client.get(f"{API}/me/tests", headers=school["h1"]).json()[0]
    assert item["is_available"] is False
    assert client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).status_code == 400
    # opening date must be before the deadline
    r = client.post(f"{API}/tests", headers=school["ha"], json={
        "title": "x", "questions": _questions(1), "available_from": later.isoformat(),
        "due_at": (later - timedelta(hours=1)).isoformat()})
    assert r.status_code == 422


def test_shuffle_is_stable_per_attempt(client, school):
    t = _create(client, school, questions=_questions(8), shuffle_questions=True, shuffle_options=True)
    first = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()
    again = client.get(f"{API}/me/tests/attempts/{first['id']}", headers=school["h1"]).json()
    order = [q["id"] for q in first["questions"]]
    assert order == [q["id"] for q in again["questions"]]  # reloading never reshuffles
    assert sorted(order) == sorted(q["id"] for q in t["questions"])
    assert order != [q["id"] for q in t["questions"]]  # 8 questions: 1/40320 chance to stay in place
    assert all(sorted(o["id"] for o in q["options"]) == ["a", "b", "c", "d"] for q in first["questions"])
    # the teacher always sees the original order
    teacher_view = client.get(f"{API}/tests/attempts/{first['id']}", headers=school["ha"]).json()
    assert [q["id"] for q in teacher_view["questions"]] == [q["id"] for q in t["questions"]]


def _take(client, school, test, right: int):
    attempt = client.post(f"{API}/me/tests/{test['id']}/start", headers=school["h1"]).json()
    answers = [{"question_id": q["id"], "answer": ["a" if i < right else "b"]}
               for i, q in enumerate(test["questions"])]
    return client.post(f"{API}/me/tests/attempts/{attempt['id']}/submit", headers=school["h1"],
                       json={"answers": answers}).json()


def test_passing_score_and_hidden_answers(client, school):
    t = _create(client, school, passing_percent=70, show_correct_answers=False)
    result = _take(client, school, t, right=2)  # 67%
    assert result["percent"] == 67 and result["passed"] is False
    # score is visible, correct answers and explanations are not
    assert all(q["correct_answer"] is None and q["explanation"] is None for q in result["questions"])
    assert all(a["is_correct"] is not None for a in result["answers"])
    item = client.get(f"{API}/me/tests", headers=school["h1"]).json()[0]
    assert item["passed"] is False and item["passing_percent"] == 70

    # the teacher still sees everything
    teacher_view = client.get(f"{API}/tests/attempts/{result['id']}", headers=school["ha"]).json()
    assert teacher_view["questions"][0]["explanation"] == "Because 0"


def test_explanations_shown_when_allowed(client, school):
    t = _create(client, school, passing_percent=60)
    result = _take(client, school, t, right=3)
    assert result["passed"] is True
    assert [q["explanation"] for q in result["questions"]] == ["Because 0", "Because 1", "Because 2"]


def test_teacher_can_allow_a_retake(client, school):
    t = _create(client, school)
    result = _take(client, school, t, right=1)
    # another teacher cannot
    assert client.post(f"{API}/tests/attempts/{result['id']}/reset", headers=school["hb"]).status_code == 404
    assert client.post(f"{API}/tests/attempts/{result['id']}/reset", headers=school["ha"]).status_code == 204
    item = client.get(f"{API}/me/tests", headers=school["h1"]).json()[0]
    assert item["attempt_id"] is None
    notes = client.get(f"{API}/notifications", headers=school["h1"]).json()
    assert notes[0]["title"] == "Тест можно пройти ещё раз"
    assert _take(client, school, t, right=3)["percent"] == 100


def test_settings_can_change_after_start_but_questions_cannot(client, school):
    t = _create(client, school)
    client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"])
    body = {"title": "Listening", "questions": _questions(), "passing_percent": 50, "show_correct_answers": False}
    r = client.put(f"{API}/tests/{t['id']}", headers=school["ha"], json=body)
    assert r.status_code == 200 and r.json()["passing_percent"] == 50
    changed = _questions()
    changed[0]["explanation"] = "Different"
    assert client.put(f"{API}/tests/{t['id']}", headers=school["ha"],
                      json={**body, "questions": changed}).status_code == 400


def test_kazakh_locale_is_accepted(client, school):
    r = client.patch(f"{API}/auth/me", headers=school["h1"], json={"locale": "kk"})
    assert r.status_code == 200 and r.json()["locale"] == "kk"
    make_user(UserRole.ADMIN, "admin@test.io")
    assert client.patch(f"{API}/auth/me", headers=login(client, "admin@test.io"),
                        json={"locale": "de"}).status_code == 422

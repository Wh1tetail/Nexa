import io
from datetime import UTC, datetime, timedelta

API = "/api/v1"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")


def test_homework_full_cycle(client, school):
    r = client.post(f"{API}/homework", headers=school["ha"], json={
        "title": "Essay", "description": "Write", "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "student_ids": [school["s1"].id]})
    assert r.status_code == 201, r.text
    hw = r.json()
    up = client.post(f"{API}/homework/{hw['id']}/attachments", headers=school["ha"],
                     files=[("files", ("task.pdf", PDF, "application/pdf"))])
    assert up.status_code == 201, up.text
    material_id = up.json()[0]["id"]

    mine = client.get(f"{API}/me/homework", headers=school["h1"]).json()
    assert len(mine) == 1 and mine[0]["status"] == "new"
    sub_id = mine[0]["submission_id"]
    # student 2 isn't assigned: no access to the submission or the material
    assert client.get(f"{API}/me/homework/{sub_id}", headers=school["h2"]).status_code == 404
    assert client.get(f"{API}/files/{material_id}", headers=school["h2"]).status_code == 403
    assert client.get(f"{API}/files/{material_id}", headers=school["h1"]).content == PDF

    # disguised file rejected (extension says pdf, bytes are png)
    bad = client.post(f"{API}/me/homework/{sub_id}/files", headers=school["h1"],
                      files=[("files", ("evil.pdf", PNG, "application/pdf"))])
    assert bad.status_code == 400
    exe = client.post(f"{API}/me/homework/{sub_id}/files", headers=school["h1"],
                      files=[("files", ("run.exe", b"MZ....", "application/octet-stream"))])
    assert exe.status_code == 400
    ok = client.post(f"{API}/me/homework/{sub_id}/files", headers=school["h1"], files=[
        ("files", ("photo.png", PNG, "image/png")),
        ("files", ("answer.txt", "Привет".encode(), "text/plain")),
    ])
    assert ok.status_code == 201, ok.text
    file_id = ok.json()[0]["id"]
    r = client.post(f"{API}/me/homework/{sub_id}/submit", headers=school["h1"], json={"student_comment": "Done"})
    assert r.json()["status"] == "submitted"
    # can't change after submit
    assert client.post(f"{API}/me/homework/{sub_id}/submit", headers=school["h1"], json={}).status_code == 400

    # teacher notified and can download, other teacher can't
    notes = client.get(f"{API}/notifications", headers=school["ha"]).json()
    assert any(n["type"] == "homework_submitted" for n in notes)
    assert client.get(f"{API}/files/{file_id}", headers=school["ha"]).status_code == 200
    assert client.get(f"{API}/files/{file_id}", headers=school["hb"]).status_code == 403

    assert client.post(f"{API}/homework/submissions/{sub_id}/review", headers=school["ha"],
                       json={"status": "reviewed", "grade": 11}).status_code == 400
    r = client.post(f"{API}/homework/submissions/{sub_id}/review", headers=school["ha"],
                    json={"status": "reviewed", "grade": 9, "teacher_comment": "Good"})
    assert r.json()["grade"] == 9
    assert client.get(f"{API}/me/homework/{sub_id}", headers=school["h1"]).json()["status"] == "reviewed"
    dash = client.get(f"{API}/dashboard/student", headers=school["h1"]).json()
    assert dash["homework_done"] == 1


def test_upload_size_limit(client, school, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    hw = client.post(f"{API}/homework", headers=school["ha"],
                     json={"title": "x", "student_ids": [school["s1"].id]}).json()
    big = PDF + b"0" * (1024 * 1024 + 10)
    r = client.post(f"{API}/homework/{hw['id']}/attachments", headers=school["ha"],
                    files=[("files", ("big.pdf", io.BytesIO(big), "application/pdf"))])
    assert r.status_code == 400


QUESTIONS = [
    {"type": "single_choice", "text": "Q1", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
     "correct_answer": ["a"]},
    {"type": "multiple_choice", "text": "Q2",
     "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}],
     "correct_answer": ["a", "c"], "points": 2},
    {"type": "true_false", "text": "Q3", "correct_answer": ["true"]},
    {"type": "short_answer", "text": "Q4", "correct_answer": ["gone"]},
    {"type": "short_answer", "text": "Q5", "correct_answer": [], "points": 3},
]


def test_test_flow_with_manual_review(client, school):
    r = client.post(f"{API}/tests", headers=school["ha"], json={
        "title": "Grammar", "time_limit_minutes": 10, "questions": QUESTIONS, "student_ids": [school["s1"].id]})
    assert r.status_code == 201, r.text
    test = r.json()
    q = {x["text"]: x["id"] for x in test["questions"]}

    items = client.get(f"{API}/me/tests", headers=school["h1"]).json()
    assert items[0]["test_id"] == test["id"]
    assert client.get(f"{API}/me/tests", headers=school["h2"]).json() == []
    assert client.post(f"{API}/me/tests/{test['id']}/start", headers=school["h2"]).status_code == 404

    att = client.post(f"{API}/me/tests/{test['id']}/start", headers=school["h1"]).json()
    # correct answers are hidden from the student
    assert all(x["correct_answer"] is None for x in att["questions"])
    r = client.post(f"{API}/me/tests/attempts/{att['id']}/submit", headers=school["h1"], json={"answers": [
        {"question_id": q["Q1"], "answer": ["a"]},
        {"question_id": q["Q2"], "answer": ["a"]},
        {"question_id": q["Q3"], "answer": ["true"]},
        {"question_id": q["Q4"], "answer": [" Gone "]},
        {"question_id": q["Q5"], "answer": ["My free text"]},
    ]})
    res = r.json()
    assert res["status"] == "pending_review" and res["score"] is None

    detail = client.get(f"{API}/tests/attempts/{att['id']}", headers=school["ha"]).json()
    by_q = {a["question_id"]: a for a in detail["answers"]}
    assert by_q[q["Q1"]]["is_correct"] is True
    assert by_q[q["Q2"]]["points_awarded"] == 0
    assert by_q[q["Q4"]]["is_correct"] is True
    assert by_q[q["Q5"]]["points_awarded"] is None
    assert client.post(f"{API}/tests/attempts/{att['id']}/grade", headers=school["ha"], json={"answers": [
        {"answer_id": by_q[q["Q5"]]["id"], "points_awarded": 5}]}).status_code == 400
    r = client.post(f"{API}/tests/attempts/{att['id']}/grade", headers=school["ha"], json={"answers": [
        {"answer_id": by_q[q["Q5"]]["id"], "points_awarded": 2, "teacher_comment": "ok"}]})
    assert r.json()["status"] == "graded" and r.json()["score"] == 5.0  # 1 + 0 + 1 + 1 + 2
    mine = client.get(f"{API}/me/tests/attempts/{att['id']}", headers=school["h1"]).json()
    assert mine["percent"] == round(5 * 100 / 8)
    assert mine["questions"][0]["correct_answer"] == ["a"]
    notes = client.get(f"{API}/notifications", headers=school["h1"]).json()
    assert any(n["type"] == "test_graded" for n in notes)
    # questions locked after attempts
    changed = dict(QUESTIONS[0], text="changed")
    r = client.put(f"{API}/tests/{test['id']}", headers=school["ha"], json={
        "title": "Grammar", "questions": [changed] + QUESTIONS[1:]})
    assert r.status_code == 400


def test_invalid_questions_rejected(client, school):
    bad = {"type": "single_choice", "text": "Q", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
           "correct_answer": ["a", "b"]}
    r = client.post(f"{API}/tests", headers=school["ha"], json={"title": "x", "questions": [bad]})
    assert r.status_code == 422


def test_notifications_read(client, school):
    client.post(f"{API}/homework", headers=school["ha"], json={"title": "x", "student_ids": [school["s1"].id]})
    assert client.get(f"{API}/notifications/unread-count", headers=school["h1"]).json()["count"] == 1
    n = client.get(f"{API}/notifications", headers=school["h1"]).json()[0]
    assert client.post(f"{API}/notifications/{n['id']}/read", headers=school["h2"]).status_code == 404
    client.post(f"{API}/notifications/read-all", headers=school["h1"])
    assert client.get(f"{API}/notifications/unread-count", headers=school["h1"]).json()["count"] == 0

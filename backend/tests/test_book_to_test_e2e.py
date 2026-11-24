"""Book-to-Test, stage 9: the whole way from a PDF to a student's attempt and lesson.

book -> questions (AI faked) -> review -> library -> publish -> teacher's copy ->
assignment -> attempt -> analytics / XP -> a lesson exercise. At every student
step the book, its title and the quotes stay out of the responses.
"""
import json

from conftest import _assign
from test_book_review import fake_ai, q  # noqa: F401  (fixture)
from test_pdf_extract import process, text_pdf

from app.worker import run_once

API = "/api/v1"
__all__ = ["fake_ai"]

PAGES = ["Unit 1\nMy mother is a teacher.\nMy father works in a bank.", "Unit 2\nWe went to Turkestan by train."]
QUOTES = ("My mother is a teacher.", "My father works in a bank.", "We went to Turkestan by train.")


def private(resp, title):
    """Nothing about the book in a student's response."""
    text = json.dumps(resp.json(), ensure_ascii=False)
    assert title not in text and not any(x in text for x in QUOTES), text[:500]
    for item in resp.json().get("questions", []) if isinstance(resp.json(), dict) else []:
        assert item.get("source") is None


def test_from_a_book_to_a_students_attempt_and_lesson(client, course, fake_ai):
    hm, ha, h1, s1 = course["hm"], course["ha"], course["h1"], course["s1"]

    # 1. the methodist uploads a book; the worker reads its pages
    book = process(client, hm, text_pdf(PAGES))
    title = book["title"]
    assert book["status"] == "ready" and book["page_count"] == 2

    # 2. questions are generated (the model is faked); one quote is not on its page
    fake_ai([q(1, "What is the mother's job?"),
             q(1, "Where does the father work?", correct_answer=["b"], excerpt=QUOTES[1],
               options=[{"id": "a", "text": "In a shop"}, {"id": "b", "text": "In a bank"}]),
             q(2, "How did they travel?", excerpt="They flew.",
               options=[{"id": "a", "text": "By train"}, {"id": "b", "text": "By plane"}])])
    r = client.post(f"{API}/books/{book['id']}/generate", headers=hm,
                    json={"page_start": 1, "page_end": 2, "question_count": 3, "types": ["single_choice"]})
    assert r.status_code == 202, r.text
    run_once()
    drafts = client.get(f"{API}/books/{book['id']}/drafts", headers=hm).json()
    ids = [d["id"] for d in drafts]
    assert [d["status"] for d in drafts] == ["draft"] * 3 and drafts[2]["warnings"] == ["source_not_found"]

    # 3. review: the server refuses the bad quote until it is fixed
    review = client.post(f"{API}/books/{book['id']}/drafts/review", headers=hm, json={"ids": ids, "action": "approve"}).json()
    assert [x["ok"] for x in review] == [True, True, False]
    client.put(f"{API}/books/drafts/{ids[2]}", headers=hm,
               json={"question": drafts[2]["question"], "difficulty": "medium", "excerpt": QUOTES[2]})
    assert client.post(f"{API}/books/{book['id']}/drafts/review", headers=hm,
                       json={"ids": [ids[2]], "action": "approve"}).json()[0]["ok"] is True

    # 4. into the library: an unpublished test, hidden from teachers until the methodist publishes it
    lib = client.post(f"{API}/books/{book['id']}/export", headers=hm, json={"draft_ids": ids, "title": "Family", "level": "A1"})
    assert lib.status_code == 201, lib.text
    lib = lib.json()
    assert lib["published"] is False and all(x["source"]["book_title"] == title for x in lib["questions"])
    assert client.get(f"{API}/library/tests/{lib['id']}", headers=ha).status_code == 404
    body = {"title": "Family", "level": "A1", "published": True,
            "questions": [{k: v for k, v in x.items() if k not in ("id", "position")} for x in lib["questions"]]}
    assert client.put(f"{API}/library/tests/{lib['id']}", headers=hm, json=body).status_code == 200

    # 5. a teacher copies it (the source comes along for the teacher) and assigns it
    mine = client.post(f"{API}/library/tests/{lib['id']}/copy", headers=ha)
    assert mine.status_code == 201, mine.text
    mine = mine.json()
    assert [x["source"]["page_start"] for x in mine["questions"]] == [1, 1, 2]
    put = {"title": mine["title"], "student_ids": [s1.id],
           "questions": [{k: v for k, v in x.items() if k not in ("id", "position")} for x in mine["questions"]]}
    assert client.put(f"{API}/tests/{mine['id']}", headers=ha, json=put).status_code == 200

    # 6. the student takes it: nothing about the book reaches them
    listed = client.get(f"{API}/me/tests", headers=h1)
    private(listed, title)
    attempt = client.post(f"{API}/me/tests/{mine['id']}/start", headers=h1)
    assert attempt.status_code == 200, attempt.text
    private(attempt, title)
    answers = [{"question_id": x["id"], "answer": ["b" if i == 1 else "a"]} for i, x in enumerate(attempt.json()["questions"])]
    done = client.post(f"{API}/me/tests/attempts/{attempt.json()['id']}/submit", headers=h1, json={"answers": answers})
    assert done.status_code == 200, done.text
    assert done.json()["score"] == done.json()["max_score"] == 3
    private(done, title)

    # 7. it counts like any test: analytics for both sides, XP for the student
    me = client.get(f"{API}/analytics/me", headers=h1).json()
    assert me["summary"]["tests_count"] == 1 and me["summary"]["avg_test"] == 100
    assert client.get(f"{API}/analytics/students/{s1.id}", headers=ha).json()["summary"] == me["summary"]
    xp = client.get(f"{API}/me/gamification", headers=h1).json()
    assert xp["xp_total"] > 0 and "first_test" in {a["code"] for a in xp["achievements"] if a["earned_at"]}

    # 8. a library question goes into a course lesson with its source; the student gets neither
    lid = course["l1"]["id"]
    blocks = []
    for b in course["l1"]["blocks"]:
        qs = b["questions"]
        if b["type"] == "quiz":
            qs = [*qs, {**{k: v for k, v in lib["questions"][0].items() if k not in ("id", "position")}}]
        blocks.append({"id": b["id"], "type": b["type"], "title": b["title"], "content": b["content"], "questions": qs})
    r = client.put(f"{API}/courses/lessons/{lid}", headers=hm, json={"title": course["l1"]["title"], "published": True, "blocks": blocks})
    assert r.status_code == 200, r.text
    assert next(b for b in r.json()["blocks"] if b["type"] == "quiz")["questions"][2]["source"]["book_title"] == title
    _assign(client, ha, course, module_id=course["m1"], student_ids=[s1.id])
    view = client.get(f"{API}/me/course-lessons/{lid}", headers=h1)
    assert view.status_code == 200, view.text
    private(view, title)
    quiz = next(b for b in view.json()["lesson"]["blocks"] if b["type"] == "quiz")
    checked = client.post(f"{API}/me/course-lessons/{lid}/blocks/{quiz['id']}/check", headers=h1,
                          json={"answers": {"0": ["a"], "1": ["am"], "2": ["a"]}})
    assert checked.status_code == 200 and checked.json()["score"] == 3
    private(checked, title)

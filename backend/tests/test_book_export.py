"""Book-to-Test, stage 7: approved drafts go to the library; the source is for editors only."""
import json

from test_book_review import drafts, fake_ai, review  # noqa: F401  (fixtures)

from app.core.database import SessionLocal
from app.models import QuestionDraft, Test

API = "/api/v1"
__all__ = ["drafts", "fake_ai"]


def export(client, ctx, **body):
    return client.post(f"{API}/books/{ctx['book']['id']}/export", headers=ctx["h"], json=body)


def approve_all(client, ctx):
    a, b, c = ctx["ids"]
    d = ctx["drafts"][2]  # its quote is not on the page: fix it first
    client.put(f"{API}/books/drafts/{c}", headers=ctx["h"], json={
        "question": d["question"], "difficulty": "hard", "excerpt": "We went to Turkestan by train."})
    assert [ok for _, ok, _ in review(client, ctx, [a, b, c], "approve")] == [True, True, True]


def test_export_to_a_new_library_test(client, school, drafts):
    h, (a, b, c) = drafts["h"], drafts["ids"]
    # only approved questions of this book: the whole request is refused otherwise
    review(client, drafts, [a], "approve")
    r = export(client, drafts, draft_ids=[a, b], title="Family")
    assert r.status_code == 400 and r.json()["detail"] == "В библиотеку можно отправить только утверждённые вопросы этой книги"
    assert export(client, drafts, draft_ids=[a]).status_code == 422  # no title, no test
    approve_all(client, drafts)

    r = export(client, drafts, draft_ids=[c, a], title=" Family ", level="A2", tags=["Book", "book "])
    assert r.status_code == 201, r.text
    t = r.json()
    assert (t["title"], t["published"], t["level"], t["tags"]) == ("Family", False, "A2", ["book"])
    # the order of the request, each with where it came from
    qs = t["questions"]
    assert [q["text"] for q in qs] == ["How did they travel?", "What is the mother's job?"]
    assert qs[0]["source"] == {"book_id": drafts["book"]["id"], "book_title": drafts["book"]["title"],
                               "page_start": 2, "page_end": 2, "excerpt": "We went to Turkestan by train.",
                               "difficulty": "hard"}
    assert qs[1]["correct_answer"] == ["a"] and qs[1]["source"]["page_start"] == 1

    with SessionLocal() as db:
        rows = {d.id: d for d in db.query(QuestionDraft).filter(QuestionDraft.id.in_([a, b, c]))}
        assert (rows[a].status.value, rows[a].exported_test_id) == ("exported", t["id"])
        assert rows[b].status.value == "approved"
    # exported questions can't go twice, nor be edited or reviewed
    assert export(client, drafts, draft_ids=[a], title="Again").status_code == 400
    assert review(client, drafts, [a], "reject") == [(a, False, "exported")]
    ds = {d["id"]: d for d in client.get(f"{API}/books/{drafts['book']['id']}/drafts", headers=h).json()}
    assert ds[a]["exported_test_id"] == t["id"]

    # nothing is published: teachers don't see it
    assert client.get(f"{API}/library/tests/{t['id']}", headers=school["ha"]).status_code == 404
    for hh in (school["ha"], school["h1"]):
        assert client.post(f"{API}/books/{drafts['book']['id']}/export", headers=hh,
                           json={"draft_ids": [b], "title": "X"}).status_code == 403


def test_export_adds_to_an_unpublished_test_only(client, school, drafts):
    h, (a, b, c) = drafts["h"], drafts["ids"]
    approve_all(client, drafts)
    t = export(client, drafts, draft_ids=[a], title="Family").json()
    r = export(client, drafts, draft_ids=[b], test_id=t["id"])
    assert r.status_code == 201, r.text
    assert [q["position"] for q in r.json()["questions"]] == [0, 1]
    assert r.json()["questions"][1]["text"] == "Where does the father work?"

    # a published test is not touched; a teacher's own test is not a library test
    body = {"title": "Family", "published": True,
            "questions": [{k: v for k, v in q.items() if k not in ("id", "position")} for q in r.json()["questions"]]}
    assert client.put(f"{API}/library/tests/{t['id']}", headers=h, json=body).status_code == 200
    r = export(client, drafts, draft_ids=[c], test_id=t["id"])
    assert r.status_code == 409 and r.json()["detail"] == "Дополнить можно только неопубликованный тест библиотеки"
    with SessionLocal() as db:
        own = db.query(Test).filter(Test.is_library.is_(False)).first()
        own_id = own.id if own else 999999
    assert export(client, drafts, draft_ids=[c], test_id=own_id).status_code == 404
    assert export(client, drafts, draft_ids=[c], test_id=999999).status_code == 404


def test_source_stays_with_editors_and_never_reaches_students(client, school, drafts):
    h = drafts["h"]
    approve_all(client, drafts)
    t = export(client, drafts, draft_ids=drafts["ids"], title="Family").json()
    quote = "My mother is a teacher."

    # the editor saves the test back with the sources: they are kept
    questions = [{k: v for k, v in q.items() if k not in ("id", "position")} for q in t["questions"]]
    body = {"title": "Family", "published": True, "questions": questions}
    r = client.put(f"{API}/library/tests/{t['id']}", headers=h, json=body)
    assert r.status_code == 200 and r.json()["questions"][1]["source"]["excerpt"] == quote

    # a teacher's copy keeps them in the teacher's editor
    mine = client.post(f"{API}/library/tests/{t['id']}/copy", headers=school["ha"]).json()
    assert mine["questions"][1]["source"]["excerpt"] == quote
    assert client.get(f"{API}/tests/{mine['id']}", headers=school["ha"]).json()["questions"][1]["source"]["page_start"] == 1

    # the student never gets the source or the quote: not in the attempt, not in the results
    put = {"title": mine["title"], "questions": [{k: v for k, v in q.items() if k not in ("id", "position")}
                                                 for q in mine["questions"]], "student_ids": [school["s1"].id]}
    assert client.put(f"{API}/tests/{mine['id']}", headers=school["ha"], json=put).status_code == 200
    attempt = client.post(f"{API}/me/tests/{mine['id']}/start", headers=school["h1"])
    assert attempt.status_code == 200, attempt.text
    done = client.post(f"{API}/me/tests/attempts/{attempt.json()['id']}/submit", headers=school["h1"],
                       json={"answers": []})
    assert done.status_code == 200, done.text
    for resp in (attempt, done, client.get(f"{API}/me/tests/attempts/{attempt.json()['id']}", headers=school["h1"])):
        text = json.dumps(resp.json(), ensure_ascii=False)
        assert quote not in text and "Turkestan by train" not in text and drafts["book"]["title"] not in text
        assert all(q.get("source") is None for q in resp.json().get("questions", []))


def test_lesson_exercises_keep_the_source_for_editors_only(client, course):
    """Stage 8: a library question copied into a lesson keeps its source; students never get it."""
    from conftest import _assign

    hm, lid = course["hm"], course["l1"]["id"]
    quote = "My mother is a teacher at a primary school."
    source = {"book_id": None, "book_title": "Aisha's family", "page_start": 3, "page_end": 3,
              "excerpt": quote, "difficulty": "easy"}
    blocks = course["l1"]["blocks"]
    body_blocks = []
    for b in blocks:
        qs = b["questions"]
        if b["type"] == "quiz":
            qs = [{**qs[0], "source": source}, *qs[1:]]
        body_blocks.append({"id": b["id"], "type": b["type"], "title": b["title"], "content": b["content"], "questions": qs})
    r = client.put(f"{API}/courses/lessons/{lid}", headers=hm,
                   json={"title": course["l1"]["title"], "published": True, "blocks": body_blocks})
    assert r.status_code == 200, r.text
    quiz = next(b for b in r.json()["blocks"] if b["type"] == "quiz")
    assert quiz["questions"][0]["source"] == source and quiz["questions"][1].get("source") is None
    # saved again as the editor sends it back: still there
    again = client.get(f"{API}/courses/lessons/{lid}", headers=hm).json()
    assert next(b for b in again["blocks"] if b["type"] == "quiz")["questions"][0]["source"]["excerpt"] == quote

    # the student: neither in the lesson nor in the checked answers; grading is unchanged
    _assign(client, course["ha"], course, module_id=course["m1"], student_ids=[course["s1"].id])
    v = client.get(f"{API}/me/course-lessons/{lid}", headers=course["h1"])
    assert v.status_code == 200, v.text
    sq = next(b for b in v.json()["lesson"]["blocks"] if b["type"] == "quiz")
    check = client.post(f"{API}/me/course-lessons/{lid}/blocks/{sq['id']}/check", headers=course["h1"],
                        json={"answers": {"0": ["a"], "1": ["am"]}})
    assert check.status_code == 200 and check.json()["score"] == 2
    for resp in (v, check):
        text = json.dumps(resp.json(), ensure_ascii=False)
        assert quote not in text and "Aisha's family" not in text

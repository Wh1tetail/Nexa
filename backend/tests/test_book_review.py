"""Book-to-Test, stage 6: reviewing drafts - edit, approve / reject (server-checked), regenerate."""
import pytest
from pydantic import SecretStr
from test_ai_generation import cfg
from test_pdf_extract import process, text_pdf

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import QuestionDraft
from app.models.enums import DraftStatus
from app.services import ai_client as ai
from app.services.question_generator import GeneratedBatch
from app.worker import run_once

API = "/api/v1"


def q(page, text, **over):
    base = {"type": "single_choice", "text": text,
            "options": [{"id": "a", "text": "A teacher"}, {"id": "b", "text": "A doctor"}, {"id": "c", "text": "A pilot"}],
            "correct_answer": ["a"], "gap_template": None, "pairs": [], "explanation": None,
            "difficulty": "easy", "page": page, "excerpt": "My mother is a teacher."}
    return {**base, **over}


class Recorder:
    """A fake AI transport that answers from a list and keeps the prompts."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def call(self, *, model, system, prompt, schema, max_output_tokens, usage):
        self.prompts.append(prompt)
        usage.record(model, ai.TokenCounts(input_tokens=500, output_tokens=100))
        return GeneratedBatch.model_validate({"questions": self.answers.pop(0)})


@pytest.fixture
def fake_ai(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", SecretStr("sk-test-not-real"))

    def play(*answers):
        rec = Recorder(answers)
        monkeypatch.setattr(ai, "get_ai_client", lambda: ai.AIClient(cfg(), transport=rec, sleep=lambda s: None))
        return rec

    return play


@pytest.fixture
def drafts(client, school, fake_ai):
    """A processed book with three drafts; the third one's quote is not on the page."""
    h = school["adm"]
    pages = ["Unit 1\nMy mother is a teacher.\nMy father works in a bank.", "Unit 2\nWe went to Turkestan by train."]
    b = process(client, h, text_pdf(pages))
    fake_ai([q(1, "What is the mother's job?"), q(1, "Where does the father work?"),
             q(2, "How did they travel?", excerpt="We flew there.")])
    client.post(f"{API}/books/{b['id']}/generate", headers=h,
                json={"page_start": 1, "page_end": 2, "question_count": 3, "types": ["single_choice"]})
    run_once()
    ds = client.get(f"{API}/books/{b['id']}/drafts", headers=h).json()
    assert [d["warnings"] for d in ds] == [[], [], ["source_not_found"]]
    return {"h": h, "book": b, "ids": [d["id"] for d in ds], "drafts": ds}


def review(client, ctx, ids, action):
    r = client.post(f"{API}/books/{ctx['book']['id']}/drafts/review", headers=ctx["h"], json={"ids": ids, "action": action})
    assert r.status_code == 200, r.text
    return [(x["id"], x["ok"], x["reason"]) for x in r.json()]


def statuses(ids):
    with SessionLocal() as db:
        return [db.get(QuestionDraft, i).status.value for i in ids]


def test_bulk_approve_is_checked_per_question(client, school, drafts):
    a, b, c = drafts["ids"]
    # the quote of c is not on its page: it can't be approved before an edit
    assert review(client, drafts, [a, b, c, 999999], "approve") == [
        (a, True, None), (b, True, None), (c, False, "needs_edit"), (999999, False, "not_found")]
    assert statuses([a, b, c]) == ["approved", "approved", "draft"]

    # an edit runs the checks again and sends the question back to review
    d = drafts["drafts"][2]
    body = {"question": {**d["question"], "text": "How did the family travel to Turkestan?"},
            "difficulty": "medium", "excerpt": "We went to Turkestan by train."}
    r = client.put(f"{API}/books/drafts/{c}", headers=drafts["h"], json=body)
    assert r.status_code == 200, r.text
    assert (r.json()["warnings"], r.json()["status"], r.json()["difficulty"]) == ([], "draft", "medium")
    assert review(client, drafts, [c], "approve") == [(c, True, None)]

    # editing an approved question returns it to review
    r = client.put(f"{API}/books/drafts/{a}", headers=drafts["h"],
                   json={"question": drafts["drafts"][0]["question"], "difficulty": "easy"})
    assert r.json()["status"] == "draft"
    # an invalid question is refused by the same rules as the test editor
    bad = {**drafts["drafts"][0]["question"], "correct_answer": ["a", "b"]}
    assert client.put(f"{API}/books/drafts/{a}", headers=drafts["h"], json={"question": bad, "difficulty": "easy"}).status_code == 422

    assert review(client, drafts, [a], "reject") == [(a, True, None)]
    assert review(client, drafts, [a], "reset") == [(a, True, None)]
    assert statuses([a]) == ["draft"]

    # a stored draft that no longer passes the rules is not approved (the server re-checks it)
    with SessionLocal() as db:
        row = db.get(QuestionDraft, a)
        row.question = {**row.question, "options": []}
        db.commit()
    assert review(client, drafts, [a], "approve") == [(a, False, "invalid")]

    # exported questions are out of review's reach
    with SessionLocal() as db:
        db.get(QuestionDraft, b).status = DraftStatus.EXPORTED
        db.commit()
    assert review(client, drafts, [b], "reject") == [(b, False, "exported")]
    r = client.put(f"{API}/books/drafts/{b}", headers=drafts["h"], json={"question": drafts["drafts"][1]["question"], "difficulty": "easy"})
    assert r.status_code == 409 and r.json()["detail"] == "Вопрос уже в библиотеке"

    for h in (school["ha"], school["h1"]):
        assert client.post(f"{API}/books/{drafts['book']['id']}/drafts/review", headers=h, json={"ids": [a], "action": "approve"}).status_code == 403
        assert client.put(f"{API}/books/drafts/{a}", headers=h, json={"question": drafts["drafts"][0]["question"], "difficulty": "easy"}).status_code == 403
    assert client.put(f"{API}/books/drafts/999999", headers=drafts["h"],
                      json={"question": drafts["drafts"][0]["question"], "difficulty": "easy"}).status_code == 404


def test_regenerate_replaces_one_question(client, school, drafts, fake_ai):
    h, (a, b, c) = drafts["h"], drafts["ids"]
    rec = fake_ai([q(1, "What does the father do?", excerpt="My father works in a bank.", difficulty="medium")])
    r = client.post(f"{API}/books/drafts/{a}/regenerate", headers=h)
    assert r.status_code == 202, r.text
    st = r.json()["settings"]
    assert (st["page_start"], st["page_end"], st["question_count"], st["replace_draft_id"]) == (1, 2, 1, a)
    run_once()
    # the prompt asked not to repeat the questions that exist on those pages
    assert "do not repeat" in rec.prompts[0] and "What is the mother's job?" in rec.prompts[0]
    ds = {d["id"]: d for d in client.get(f"{API}/books/{drafts['book']['id']}/drafts", headers=h).json()}
    assert ds[a]["status"] == "rejected"
    new = [d for i, d in ds.items() if i not in (a, b, c)]
    assert len(new) == 1 and new[0]["question"]["text"] == "What does the father do?" and new[0]["status"] == "draft"

    # the model repeats an existing question: it is dropped and the draft stays as it was
    fake_ai([q(1, "Where does the father work?")])
    client.post(f"{API}/books/drafts/{b}/regenerate", headers=h)
    run_once()
    assert statuses([b]) == ["draft"]
    job = client.get(f"{API}/books/{drafts['book']['id']}/jobs", headers=h).json()[0]
    assert job["kind"] == "regenerate" and job["settings"]["result"]["drafts"] == 0

    # an approved question must go back to review first; no key: no generation
    review(client, drafts, [b], "approve")
    r = client.post(f"{API}/books/drafts/{b}/regenerate", headers=h)
    assert r.status_code == 409
    for hh in (school["ha"], school["h1"]):
        assert client.post(f"{API}/books/drafts/{c}/regenerate", headers=hh).status_code == 403


def test_new_generation_skips_questions_that_exist(client, school, drafts, fake_ai):
    h = drafts["h"]
    fake_ai([q(1, "What is the mother's job?"), q(1, "Is the father a pilot?", type="true_false", options=[],
                                                  correct_answer=["false"], excerpt="My father works in a bank.")])
    client.post(f"{API}/books/{drafts['book']['id']}/generate", headers=h,
                json={"page_start": 1, "page_end": 1, "question_count": 2, "types": ["single_choice", "true_false"]})
    run_once()
    job = client.get(f"{API}/books/{drafts['book']['id']}/jobs", headers=h).json()[0]
    assert job["settings"]["result"]["drafts"] == 1 and job["settings"]["result"]["rejected"] == 1

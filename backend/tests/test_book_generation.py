"""Book-to-Test, stage 5: AI question generation as a worker job (the AI is faked)."""
import pytest
from pydantic import SecretStr
from test_ai_generation import FakeTransport, cfg
from test_pdf_extract import process, text_pdf

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Notification, QuestionDraft
from app.models.enums import DraftStatus, NotificationType
from app.services import ai_client as ai
from app.services.question_generator import GeneratedBatch
from app.worker import run_once

API = "/api/v1"


def q(page, text, **over):
    base = {"type": "single_choice", "text": text,
            "options": [{"id": "a", "text": "By bus"}, {"id": "b", "text": "On foot"}, {"id": "c", "text": "By car"}],
            "correct_answer": ["a"], "gap_template": None, "pairs": [], "explanation": "It says so.",
            "difficulty": "easy", "page": page, "excerpt": f"Page {page} line."}
    return {**base, **over}


@pytest.fixture
def ai_script(monkeypatch):
    """Configure a key and hand the worker an AI client that plays a script."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", SecretStr("sk-test-not-real"))
    holder = {}

    def play(script):
        transport = FakeTransport(script)
        holder["transport"] = transport
        monkeypatch.setattr(ai, "get_ai_client", lambda: ai.AIClient(cfg(), transport=transport, sleep=lambda s: None))
        return transport

    return play


def book_with_text(client, h, n=6):
    return process(client, h, text_pdf([f"Unit {i}\nPage {i} line.\nAnna goes to school by bus." for i in range(1, n + 1)]))


def generate(client, h, book_id, **body):
    payload = {"page_start": 1, "page_end": 2, "question_count": 2, "types": ["single_choice"], **body}
    return client.post(f"{API}/books/{book_id}/generate", headers=h, json=payload)


def test_generation_job_makes_drafts_with_sources_and_cost(client, school, ai_script):
    h = school["adm"]
    b = book_with_text(client, h)
    transport = ai_script([GeneratedBatch.model_validate({"questions": [
        q(1, "How does Anna go to school?"),
        q(2, "What is on page 2?", difficulty="hard", excerpt="not on the page"),
        q(9, "Out of range?"),
    ]})])
    r = generate(client, h, b["id"], difficulty="easy", question_language="en")
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["kind"] == "generate" and job["status"] == "queued" and job["settings"]["level"] == "B1"  # the book's level

    assert run_once() == job["id"]
    j = client.get(f"{API}/books/jobs/{job['id']}", headers=h).json()
    result = j["settings"]["result"]
    assert j["status"] == "done" and len(result.pop("draft_ids")) == 2
    assert result == {"drafts": 2, "rejected": 1, "shortfall": 0, "model": "model-a"}
    assert j["usage"]["requests"] == 1 and j["usage"]["input_tokens"] == 1000
    assert j["usage"]["estimated_cost_usd"] == pytest.approx(0.004)

    drafts = client.get(f"{API}/books/{b['id']}/drafts", headers=h).json()
    assert [(d["status"], d["page_start"], d["difficulty"]) for d in drafts] == [("draft", 1, "easy"), ("draft", 2, "hard")]
    assert drafts[0]["question"]["text"] == "How does Anna go to school?" and drafts[0]["question"]["correct_answer"] == ["a"]
    assert drafts[0]["excerpt"] == "Page 1 line." and drafts[0]["warnings"] == []
    assert drafts[1]["warnings"] == ["source_not_found", "difficulty_mismatch"]
    assert client.get(f"{API}/books/{b['id']}", headers=h).json()["drafts"] == {"draft": 2}
    with SessionLocal() as db:  # nothing is approved by the system
        assert {d.status for d in db.query(QuestionDraft)} == {DraftStatus.DRAFT}
        me = client.get(f"{API}/auth/me", headers=h).json()["id"]
        n = db.query(Notification).filter_by(user_id=me, type=NotificationType.QUESTIONS_READY).one()
        assert n.title == "Вопросы готовы: 2" and n.body == b["title"]
    # the prompt carried the chosen pages as data, with the rules
    assert transport.calls == ["model-a"]


def test_long_ranges_go_in_portions(client, school, ai_script, monkeypatch):
    monkeypatch.setattr(settings, "AI_PAGES_PER_REQUEST", 10)
    h = school["adm"]
    b = book_with_text(client, h, n=25)
    batches = [GeneratedBatch.model_validate({"questions": [q(p, f"Question about page {p}?") for p in pages]})
               for pages in ([1, 2, 3, 4], [11, 12, 13, 14], [21, 22])]
    transport = ai_script(batches)
    r = generate(client, h, b["id"], page_start=1, page_end=25, question_count=10)
    assert r.status_code == 202, r.text
    run_once()
    drafts = client.get(f"{API}/books/{b['id']}/drafts", headers=h).json()
    # 10 questions shared 4 / 4 / 2 by the amount of text (10, 10 and 5 pages)
    assert [d["page_start"] for d in drafts] == [1, 2, 3, 4, 11, 12, 13, 14, 21, 22]
    assert len(transport.calls) == 3


def test_fewer_questions_when_material_is_short(client, school, ai_script):
    h = school["adm"]
    b = book_with_text(client, h)
    ai_script([GeneratedBatch.model_validate({"questions": [q(1, "Only one good question?")]})])
    generate(client, h, b["id"], question_count=5)
    run_once()
    j = client.get(f"{API}/books/{b['id']}/jobs", headers=h).json()[0]
    assert j["status"] == "done" and j["settings"]["result"]["drafts"] == 1 and j["settings"]["result"]["shortfall"] == 4


def test_ai_failures(client, school, ai_script):
    h = school["adm"]
    b = book_with_text(client, h)
    # a refusal on the only model: failed, no retry, the spent tokens are kept
    ai_script([ai._Refused("cyber")])
    generate(client, h, b["id"])
    run_once()
    j = client.get(f"{API}/books/{b['id']}/jobs", headers=h).json()[0]
    assert j["status"] == "failed" and j["error_code"] == "ai_refused" and j["attempts"] == 1
    assert j["usage"]["requests"] == 1 and j["usage"]["input_tokens"] == 1000

    # the provider is down: the job goes back to the queue, usage adds up over attempts
    ai_script([ai._Transient("http_529")] * 4)
    generate(client, h, b["id"])
    run_once()
    j = client.get(f"{API}/books/{b['id']}/jobs", headers=h).json()[0]
    assert j["status"] == "queued" and j["error_code"] == "ai_unavailable" and j["usage"]["requests"] == 4
    with SessionLocal() as db:
        assert db.query(QuestionDraft).count() == 0


def test_generation_checks(client, school, ai_script, monkeypatch):
    h = school["adm"]
    b = book_with_text(client, h)
    ai_script([])

    def bad(r, text, code=400):
        assert r.status_code == code and r.json()["detail"] == text, r.text

    bad(generate(client, h, b["id"], question_count=settings.AI_MAX_QUESTIONS_PER_JOB + 1),
        f"Количество вопросов — от 1 до {settings.AI_MAX_QUESTIONS_PER_JOB}")
    bad(generate(client, h, b["id"], page_start=1, page_end=settings.AI_MAX_PAGES_PER_JOB + 1),
        f"Не более {settings.AI_MAX_PAGES_PER_JOB} страниц за один раз")
    bad(generate(client, h, b["id"], types=["short_answer"]), "Выберите типы вопросов")  # not enabled yet
    assert generate(client, h, b["id"], page_start=None, page_end=None).status_code == 422
    assert generate(client, h, b["id"], chapter_id=999999).status_code == 404

    # a chapter is a page range
    ch = client.get(f"{API}/books/{b['id']}/chapters", headers=h).json()[0]
    r = generate(client, h, b["id"], chapter_id=ch["id"], page_start=None, page_end=None)
    assert r.status_code == 202 and (r.json()["settings"]["page_start"], r.json()["settings"]["chapter_title"]) == (
        ch["start_page"], ch["title"])
    bad(generate(client, h, b["id"]), "Эта книга уже обрабатывается", 409)  # one generation at a time

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    bad(generate(client, h, b["id"]), "Генерация вопросов не настроена: нет ключа AI")
    for hh in (school["ha"], school["h1"]):
        assert generate(client, hh, b["id"]).status_code == 403
        assert client.get(f"{API}/books/{b['id']}/drafts", headers=hh).status_code == 403

"""Book-to-Test AI layer: the retry and model-switching policy, the Anthropic error
mapping, usage and cost, and question validation. No real API calls are made."""
import logging
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.exceptions import BadRequest
from app.models.enums import QuestionType
from app.services import ai_client as ai
from app.services.question_generator import (
    GeneratedBatch,
    GenerationSettings,
    PageText,
    build_prompt,
    generate_questions,
)


def cfg(**over):
    base = {"ANTHROPIC_API_KEY": SecretStr("sk-test-not-real"), "AI_MODEL": "model-a",
            "AI_FALLBACK_MODELS": [], "AI_MAX_RETRIES": 3,
            "AI_PRICES": {"model-a": {"input": 2.0, "output": 10.0, "cache_read": 0.1, "cache_write": 2.5},
                          "model-b": {"input": 4.0, "output": 20.0}}}
    return settings.model_copy(update={**base, **over})


class FakeTransport:
    """Plays a script: each item is an exception to raise or a value to return,
    and records (model, tokens) as a real transport would."""

    def __init__(self, script, tokens=ai.TokenCounts(input_tokens=1000, output_tokens=200)):
        self.script = list(script)
        self.calls: list[str] = []
        self.tokens = tokens

    def call(self, *, model, system, prompt, schema, max_output_tokens, usage):
        self.calls.append(model)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            if isinstance(step, (ai._Refused, ai._Malformed, ai.AIOutputTruncated)):
                usage.record(model, self.tokens)
            elif isinstance(step, ai._Transient):
                usage.record(model, None)
            raise step
        usage.record(model, self.tokens)
        return step


def client(script, sleeps=None, **over):
    sleeps = sleeps if sleeps is not None else []
    return ai.AIClient(cfg(**over), transport=FakeTransport(script), sleep=sleeps.append)


def gen(c):
    return c.generate_structured(system="s", prompt="p", schema=GeneratedBatch, usage=c.new_usage())


# ---------- policy ----------

def test_transient_errors_are_retried_with_backoff_then_succeed():
    ok = GeneratedBatch(questions=[])
    sleeps = []
    c = client([ai._Transient("rate_limited", retry_after=7), ai._Transient("timeout"), ok], sleeps)
    usage = c.new_usage()
    r = c.generate_structured(system="s", prompt="p", schema=GeneratedBatch, usage=usage)
    assert r.output is ok and r.model == "model-a" and c.transport.calls == ["model-a"] * 3
    assert sleeps[0] == 7  # Retry-After is honoured
    assert 2 * 0.8 * 2 <= sleeps[1] <= 2 * 1.2 * 2  # exponential backoff for the 2nd retry
    assert usage.requests == 3 and usage.totals.input_tokens == 1000  # only the answer had tokens


def test_retries_are_limited_then_the_next_model_is_tried():
    ok = GeneratedBatch(questions=[])
    script = [ai._Transient("http_529")] * 3 + [ok]
    c = client(script, AI_MAX_RETRIES=2, AI_FALLBACK_MODELS=["model-b"])
    r = gen(c)
    assert c.transport.calls == ["model-a"] * 3 + ["model-b"] and r.model == "model-b"


def test_everything_unavailable_raises_ai_unavailable():
    c = client([ai._Transient("network")] * 2, AI_MAX_RETRIES=1)
    with pytest.raises(ai.AIUnavailable):
        gen(c)


def test_refusal_switches_model_without_retrying():
    ok = GeneratedBatch(questions=[])
    c = client([ai._Refused("cyber"), ok], AI_FALLBACK_MODELS=["model-b"])
    assert gen(c).model == "model-b" and c.transport.calls == ["model-a", "model-b"]
    c = client([ai._Refused("cyber")])
    with pytest.raises(ai.AIRefused):
        gen(c)


def test_malformed_answers_are_retried_then_reported():
    ok = GeneratedBatch(questions=[])
    assert gen(client([ai._Malformed("x"), ok])).output is ok
    c = client([ai._Malformed("x")] * 4)
    with pytest.raises(ai.AIMalformedResponse):
        gen(c)
    assert len(c.transport.calls) == 4  # first try + AI_MAX_RETRIES


def test_final_errors_stop_at_once():
    for err in (ai.AIOutputTruncated("limit"), ai.AIRequestRejected("http_400"), ai.AINotConfigured("key")):
        c = client([err], AI_FALLBACK_MODELS=["model-b"])
        with pytest.raises(type(err)):
            gen(c)
        assert c.transport.calls == ["model-a"]


def test_unknown_model_is_skipped():
    ok = GeneratedBatch(questions=[])
    c = client([ai._ModelUnavailable("model-a"), ok], AI_FALLBACK_MODELS=["model-b"])
    assert gen(c).model == "model-b"


def test_usage_and_estimated_cost():
    usage = ai.AIUsage(prices={**ai.DEFAULT_PRICES, "model-b": {"input": 4.0, "output": 20.0}})
    usage.record("claude-sonnet-5-5", ai.TokenCounts(input_tokens=100_000, output_tokens=10_000,
                                                     cache_read_tokens=50_000, cache_write_tokens=20_000))
    usage.record("model-b", ai.TokenCounts(input_tokens=1_000_000, output_tokens=0))
    usage.record("model-b", None)  # a failed request: counted, no tokens
    d = usage.to_dict()
    # 0.1*2 + 0.01*10 + 0.05*0.1 + 0.02*2.5 = 0.355; + 1*4 = 4.355
    assert d["estimated_cost_usd"] == pytest.approx(4.355)
    assert d["requests"] == 3 and d["input_tokens"] == 1_100_000 and d["by_model"]["model-b"]["input_tokens"] == 1_000_000
    usage.record("unpriced-model", ai.TokenCounts(input_tokens=1))
    assert usage.to_dict()["estimated_cost_usd"] is None  # never a made-up price


def test_model_comes_from_settings_and_key_is_required():
    assert settings.AI_MODEL  # configured, not hard-coded in the services
    with pytest.raises(ai.AINotConfigured):
        ai.AIClient(cfg(ANTHROPIC_API_KEY=None))
    with pytest.raises(ai.AINotConfigured):
        ai.AIClient(cfg(ANTHROPIC_API_KEY=SecretStr("  ")))


# ---------- Anthropic transport: SDK errors -> policy ----------

REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, code, headers=None):
    return cls("err", response=httpx2.Response(code, request=REQ, headers=headers or {}), body=None)


class FakeStream:
    def __init__(self, outcome):
        self.outcome = outcome
        self.current_message_snapshot = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0))

    def __enter__(self):
        if isinstance(self.outcome, Exception) and not isinstance(self.outcome, ValueError):
            raise self.outcome
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def transport_with(outcome):
    t = ai.AnthropicTransport(cfg())
    t._client = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: FakeStream(outcome)))
    return t


def tcall(t, usage):
    return t.call(model="model-a", system="s", prompt="p", schema=GeneratedBatch, max_output_tokens=100, usage=usage)


def message(stop_reason="end_turn", parsed=None):
    return SimpleNamespace(
        stop_reason=stop_reason, parsed_output=parsed, stop_details=None,
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300, cache_read_input_tokens=100,
                              cache_creation_input_tokens=0),
    )


def test_anthropic_errors_are_mapped():
    usage = ai.AIUsage()
    cases = [
        (status_error(anthropic.RateLimitError, 429, {"retry-after": "12"}), ai._Transient),
        (status_error(anthropic.InternalServerError, 500), ai._Transient),
        (status_error(anthropic.APIStatusError, 529), ai._Transient),
        (anthropic.APITimeoutError(request=REQ), ai._Transient),
        (anthropic.APIConnectionError(request=REQ), ai._Transient),
        (status_error(anthropic.AuthenticationError, 401), ai.AINotConfigured),
        (status_error(anthropic.NotFoundError, 404), ai._ModelUnavailable),
        (status_error(anthropic.BadRequestError, 400), ai.AIRequestRejected),
        (ValueError("bad json"), ai._Malformed),
    ]
    for err, expected in cases:
        with pytest.raises(expected) as info:
            tcall(transport_with(err), usage)
        if isinstance(err, anthropic.RateLimitError):
            assert info.value.retry_after == 12


def test_anthropic_answers_are_checked():
    usage = ai.AIUsage()
    ok = GeneratedBatch(questions=[])
    assert tcall(transport_with(message(parsed=ok)), usage) is ok
    assert usage.by_model["model-a"].cache_read_tokens == 100
    with pytest.raises(ai._Refused):
        tcall(transport_with(message("refusal")), usage)
    with pytest.raises(ai.AIOutputTruncated):
        tcall(transport_with(message("max_tokens")), usage)
    with pytest.raises(ai._Malformed):
        tcall(transport_with(message(parsed=None)), usage)
    assert usage.requests == 4 and usage.totals.output_tokens == 1200


def test_api_key_is_not_in_the_transport_repr_or_logs(caplog):
    t = ai.AnthropicTransport(cfg())
    assert "sk-test-not-real" not in repr(vars(t))
    assert "sk-test-not-real" not in repr(cfg())  # SecretStr hides it


# ---------- question generation ----------

PAGES = [
    PageText(12, "Anna goes to school by bus every morning. Her brother walks."),
    PageText(13, "On Sundays the family visits the museum in the old town."),
]


def q(**over):
    base = {"type": "single_choice", "text": "How does Anna go to school?",
            "options": [{"id": "a", "text": "By bus"}, {"id": "b", "text": "On foot"}, {"id": "c", "text": "By car"}],
            "correct_answer": ["a"], "gap_template": None, "pairs": [], "explanation": "Page 12 says so.",
            "page": 12, "excerpt": "Anna goes to school by bus every morning."}
    return {**base, **over}


def run(questions, **settings_over):
    batch = GeneratedBatch.model_validate({"questions": questions})
    c = ai.AIClient(cfg(), transport=FakeTransport([batch]), sleep=lambda s: None)
    s = GenerationSettings(page_start=12, page_end=13, question_count=settings_over.pop("count", 10),
                           types=settings_over.pop("types", tuple(QuestionType)[:6]), **settings_over)
    return generate_questions(PAGES, s, client=c)


def test_generated_questions_go_through_lms_validation():
    r = run([
        q(),
        q(text="Where does the family go on Sundays?", type="short_answer", options=[],
          correct_answer=["the museum"], page=13, excerpt="the family visits the museum"),
        q(type="fill_gaps", text="Complete the sentence.", options=[], correct_answer=[],
          gap_template="Anna goes to school by {bus}.", excerpt="by bus every morning"),
        q(type="matching", text="Match.", options=[], correct_answer=[],
          pairs=[{"left": "Anna", "right": "bus"}, {"left": "brother", "right": "walks"}], excerpt="Her brother walks."),
        q(text="True or false: Anna walks.", type="true_false", options=[], correct_answer=["false"]),
        q(correct_answer=["a", "b"], text="Two right answers in single choice"),  # QuestionIn rejects
        q(type="fill_gaps", text="No gaps", options=[], correct_answer=[], gap_template="no braces here"),  # task_types rejects
        q(page=40),  # outside the chosen pages
        q(),  # duplicate
        q(text="Where is the museum?", page=13, excerpt="a sentence that is not in the book"),
    ])
    assert [d.question.type for d in r.drafts] == [
        QuestionType.SINGLE_CHOICE, QuestionType.SHORT_ANSWER, QuestionType.FILL_GAPS,
        QuestionType.MATCHING, QuestionType.TRUE_FALSE, QuestionType.SINGLE_CHOICE]
    assert all(d.status == "draft" for d in r.drafts)  # never approved here
    assert r.drafts[2].question.config["gaps"][0]["answers"] == ["bus"]  # normalized by task_types
    assert r.drafts[4].question.options[0].id == "true"
    assert r.drafts[0].warnings == [] and r.drafts[0].page == 12
    assert r.drafts[-1].warnings == ["source_not_found"]
    assert [x.reason for x in r.rejected] == ["invalid", "invalid", "page_out_of_range", "duplicate"]
    assert r.model == "model-a" and r.usage.to_dict()["estimated_cost_usd"] == pytest.approx(0.004)


def test_only_requested_types_and_count_are_kept():
    r = run([q(), q(text="Q2?"), q(type="true_false", options=[], correct_answer=["true"], text="T?")],
            count=1, types=(QuestionType.SINGLE_CHOICE,))
    assert len(r.drafts) == 1
    assert [x.reason for x in r.rejected] == ["over_limit", "over_limit"]
    r = run([q(type="true_false", options=[], correct_answer=["true"], text="T?")], types=(QuestionType.SINGLE_CHOICE,))
    assert r.rejected[0].reason == "type_not_requested"


def test_answer_hints_are_flagged():
    r = run([
        q(type="short_answer", options=[], correct_answer=["bus"], text="Anna goes by bus. How does she go?"),
        q(text="Which?", options=[{"id": "a", "text": "Anna goes to school by bus every single morning"},
                                  {"id": "b", "text": "Car"}, {"id": "c", "text": "Walk"}]),
    ])
    assert r.drafts[0].warnings == ["answer_in_question"] and r.drafts[1].warnings == ["answer_stands_out"]


def test_settings_limits():
    def s(**k):
        return GenerationSettings(**{"page_start": 12, "page_end": 13, "question_count": 5, **k})

    c = ai.AIClient(cfg(), transport=FakeTransport([]), sleep=lambda x: None)
    for bad in (s(question_count=settings.AI_MAX_QUESTIONS_PER_JOB + 1), s(question_count=0),
                s(page_start=5, page_end=4), s(page_end=12 + settings.AI_MAX_PAGES_PER_JOB),
                s(types=(QuestionType.READING,)), s(page_start=100, page_end=101)):
        with pytest.raises(BadRequest):
            generate_questions(PAGES, bad, client=c)
    assert c.transport.calls == []  # nothing is sent when the settings are wrong


def test_prompt_marks_pages_and_book_text_is_not_logged(caplog):
    s = GenerationSettings(page_start=12, page_end=13, question_count=2, level=None)
    prompt = build_prompt(PAGES, s)
    assert "[page 12]\nAnna goes" in prompt and "[page 13]" in prompt and "Write 2 questions." in prompt
    with caplog.at_level(logging.DEBUG):
        run([q()])
    assert "Anna goes to school" not in caplog.text and "sk-test-not-real" not in caplog.text

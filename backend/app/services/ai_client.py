"""The only place that talks to an AI provider (Book-to-Test question generation).

Layers:
- a *transport* makes one request to one model and reports what happened in
  provider-neutral terms (`_Transient`, `_Refused`, `_Malformed`, `_ModelUnavailable`,
  or the final errors below). `AnthropicTransport` is the only implementation today;
  another provider is another transport, nothing else changes.
- `AIClient` owns the policy, explicit and tested: up to AI_MAX_RETRIES retries per
  model with exponential backoff (honouring Retry-After), then the next model from
  AI_FALLBACK_MODELS. Every response that came back is counted in `AIUsage`, with an
  estimated cost.

Callers (services/question_generator.py) see only `AIClient.generate_structured`,
the `AIUsage` record and the `AIError` subclasses. Model ids come from settings,
never from business logic. Nothing here logs the API key or the prompt text.
"""
from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings, settings as default_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# USD per million tokens, for cost *estimates* only (AI_PRICES overrides or extends it).
DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.10, "cache_write": 2.50},
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "cache_write": 5.00},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
    "claude-sonnet-5": {"input": 2.0, "output": 10.0, "cache_read": 0.20, "cache_write": 2.50},
}

BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0
RETRY_AFTER_MAX_SECONDS = 120.0


# ---------- errors the callers handle ----------

class AIError(Exception):
    """Base class; `code` is stable for the API and the UI to translate."""
    code = "ai_error"


class AINotConfigured(AIError):
    """No key, a rejected key or an unknown provider: nothing to retry."""
    code = "ai_not_configured"


class AIRequestRejected(AIError):
    """The provider rejected the request itself (4xx): retrying would not help."""
    code = "ai_request_rejected"


class AIRefused(AIError):
    """Every model declined the request (safety refusal)."""
    code = "ai_refused"


class AIUnavailable(AIError):
    """Rate limits, timeouts, network or server errors on every model, retries spent."""
    code = "ai_unavailable"


class AIMalformedResponse(AIError):
    """The answers never matched the requested structure, retries spent."""
    code = "ai_malformed_response"


class AIOutputTruncated(AIError):
    """The answer hit the output limit: ask for fewer questions or fewer pages."""
    code = "ai_output_truncated"


# ---------- what a transport reports (internal) ----------

class _Transient(Exception):
    def __init__(self, kind: str, retry_after: float | None = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.retry_after = retry_after


class _Refused(Exception):
    pass


class _Malformed(Exception):
    pass


class _ModelUnavailable(Exception):
    """This model id is unknown to the provider: try the next model."""


# ---------- usage and cost ----------

@dataclass
class TokenCounts:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, other: TokenCounts) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens


@dataclass
class AIUsage:
    """Everything a job spent, per model (failed and retried requests included)."""
    requests: int = 0
    by_model: dict[str, TokenCounts] = field(default_factory=dict)
    prices: dict[str, dict[str, float]] = field(default_factory=dict, repr=False)

    def record(self, model: str, tokens: TokenCounts | None) -> None:
        self.requests += 1
        if tokens is not None:
            self.by_model.setdefault(model, TokenCounts()).add(tokens)

    @property
    def totals(self) -> TokenCounts:
        total = TokenCounts()
        for t in self.by_model.values():
            total.add(t)
        return total

    def cost_usd(self) -> float | None:
        """Estimated cost; None when a model that was used has no price."""
        cost = 0.0
        for model, t in self.by_model.items():
            p = self.prices.get(model)
            if p is None:
                return None
            cost += (
                t.input_tokens * p.get("input", 0)
                + t.output_tokens * p.get("output", 0)
                + t.cache_read_tokens * p.get("cache_read", 0)
                + t.cache_write_tokens * p.get("cache_write", 0)
            ) / 1_000_000
        return round(cost, 6)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready record for the job row (book_jobs.usage)."""
        t = self.totals
        return {
            "requests": self.requests,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "cache_read_tokens": t.cache_read_tokens,
            "cache_write_tokens": t.cache_write_tokens,
            "estimated_cost_usd": self.cost_usd(),
            "by_model": {m: vars(c).copy() for m, c in self.by_model.items()},
        }


@dataclass
class StructuredResult(Generic[T]):
    output: T
    model: str  # the model that produced the accepted answer


# ---------- transports ----------

class Transport(Protocol):
    def call(
        self, *, model: str, system: str, prompt: str, schema: type[T], max_output_tokens: int,
        usage: AIUsage,
    ) -> T:
        """One request to one model. Records the tokens of any response in `usage`.
        Raises _Transient / _Refused / _Malformed / _ModelUnavailable, or a final AIError."""
        ...


class AnthropicTransport:
    """Claude through the official `anthropic` SDK, structured outputs from a Pydantic model."""

    def __init__(self, cfg: Settings) -> None:
        import anthropic

        if cfg.ANTHROPIC_API_KEY is None or not cfg.ANTHROPIC_API_KEY.get_secret_value().strip():
            raise AINotConfigured("ANTHROPIC_API_KEY is not set")
        self._anthropic = anthropic
        # Retries are AIClient's policy, so the SDK's own are off.
        self._client = anthropic.Anthropic(
            api_key=cfg.ANTHROPIC_API_KEY.get_secret_value(),
            timeout=cfg.AI_TIMEOUT_SECONDS,
            max_retries=0,
        )

    @staticmethod
    def _tokens(message: Any) -> TokenCounts | None:
        u = getattr(message, "usage", None)
        if u is None:
            return None
        return TokenCounts(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", None) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", None) or 0,
        )

    @staticmethod
    def _retry_after(err: Any) -> float | None:
        response = getattr(err, "response", None)
        value = response.headers.get("retry-after") if response is not None else None
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    def call(self, *, model, system, prompt, schema, max_output_tokens, usage):
        a = self._anthropic
        stream = None
        try:
            # Streaming: long answers never hit an HTTP timeout halfway.
            with self._client.messages.stream(
                model=model,
                max_tokens=max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
            ) as stream:
                message = stream.get_final_message()
        except (ValidationError, ValueError) as e:  # the JSON did not fit the schema
            snapshot = getattr(stream, "current_message_snapshot", None) if stream is not None else None
            usage.record(model, self._tokens(snapshot) if snapshot is not None else None)
            raise _Malformed(type(e).__name__) from None
        except a.RateLimitError as e:
            usage.record(model, None)
            raise _Transient("rate_limited", self._retry_after(e)) from None
        except (a.AuthenticationError, a.PermissionDeniedError):
            raise AINotConfigured("the provider rejected the API key") from None
        except a.NotFoundError:
            raise _ModelUnavailable(model) from None
        except a.APIStatusError as e:
            if e.status_code >= 500 or e.status_code in (408, 409):
                usage.record(model, None)
                raise _Transient(f"http_{e.status_code}", self._retry_after(e)) from None
            raise AIRequestRejected(f"http_{e.status_code}") from None
        except a.APITimeoutError:
            usage.record(model, None)
            raise _Transient("timeout") from None
        except a.APIConnectionError:
            usage.record(model, None)
            raise _Transient("network") from None

        usage.record(model, self._tokens(message))
        if message.stop_reason == "refusal":
            raise _Refused(getattr(getattr(message, "stop_details", None), "category", None) or "refusal")
        if message.stop_reason == "max_tokens":
            raise AIOutputTruncated("the answer reached the output limit")
        parsed = getattr(message, "parsed_output", None)
        if parsed is None:
            raise _Malformed("no parsed output")
        return parsed


def _transport_for(cfg: Settings) -> Transport:
    if cfg.AI_PROVIDER == "anthropic":
        return AnthropicTransport(cfg)
    raise AINotConfigured(f"unknown AI provider {cfg.AI_PROVIDER!r}")


# ---------- the policy ----------

class AIClient:
    def __init__(
        self,
        cfg: Settings | None = None,
        *,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cfg = cfg or default_settings
        self.transport = transport or _transport_for(self.cfg)
        self.models = list(dict.fromkeys([self.cfg.AI_MODEL, *self.cfg.AI_FALLBACK_MODELS]))
        self.prices = {**DEFAULT_PRICES, **self.cfg.AI_PRICES}
        self._sleep = sleep

    def new_usage(self) -> AIUsage:
        return AIUsage(prices=self.prices)

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(max(retry_after, 0.0), RETRY_AFTER_MAX_SECONDS)
        base = min(BACKOFF_BASE_SECONDS * 2**attempt, BACKOFF_MAX_SECONDS)
        return base * random.uniform(0.8, 1.2)

    def generate_structured(
        self, *, system: str, prompt: str, schema: type[T], usage: AIUsage,
        max_output_tokens: int | None = None,
    ) -> StructuredResult[T]:
        """Policy, per model in order (AI_MODEL, then AI_FALLBACK_MODELS):
        - rate limit / timeout / network / 5xx / malformed answer: retry the same model
          up to AI_MAX_RETRIES times with backoff;
        - refusal, unknown model id, or retries spent: next model;
        - output limit reached, rejected request, bad key: stop at once.
        The final error says why the last model gave up."""
        max_tokens = max_output_tokens or self.cfg.AI_MAX_OUTPUT_TOKENS
        last: AIError = AIUnavailable("no model was tried")
        for model in self.models:
            for attempt in range(self.cfg.AI_MAX_RETRIES + 1):
                try:
                    output = self.transport.call(
                        model=model, system=system, prompt=prompt, schema=schema,
                        max_output_tokens=max_tokens, usage=usage,
                    )
                    return StructuredResult(output=output, model=model)
                except _Refused as e:
                    log.warning("AI: %s declined the request (%s)", model, e)
                    last = AIRefused(f"{model} declined the request")
                    break
                except _ModelUnavailable:
                    log.error("AI: model %s is unknown to the provider", model)
                    last = AIRequestRejected(f"unknown model {model}")
                    break
                except _Transient as e:
                    last = AIUnavailable(f"{model}: {e.kind}")
                    if attempt < self.cfg.AI_MAX_RETRIES:
                        delay = self._delay(attempt, e.retry_after)
                        log.warning("AI: %s %s, retry %d in %.1fs", model, e.kind, attempt + 1, delay)
                        self._sleep(delay)
                except _Malformed as e:
                    last = AIMalformedResponse(f"{model}: {e}")
                    log.warning("AI: %s returned a malformed answer (%s), attempt %d", model, e, attempt + 1)
            log.warning("AI: giving up on %s (%s)", model, last.code)
        raise last


def is_configured(cfg: Settings | None = None) -> bool:
    """Whether generation can run at all (a key for the configured provider)."""
    cfg = cfg or default_settings
    if cfg.AI_PROVIDER == "anthropic":
        return cfg.ANTHROPIC_API_KEY is not None and bool(cfg.ANTHROPIC_API_KEY.get_secret_value().strip())
    return False


def get_ai_client() -> AIClient:
    return AIClient()

"""Book-to-Test: the background job queue, kept in PostgreSQL (no Redis, no Celery).

- `enqueue` adds a job in the caller's transaction (one active job per book and kind).
- The worker process (app/worker.py) takes jobs with `claim_next`:
  SELECT ... FOR UPDATE SKIP LOCKED, so two workers never take the same job.
- `run_job` calls the handler registered for the job's kind (services/book_processing.py)
  and records the outcome: done; cancelled; failed (FinalJobError, or retries spent);
  or back to the queue with a growing delay (RetryableJobError, unexpected errors).
- A heartbeat thread keeps `heartbeat_at` fresh while a job runs; `recover_stale`
  puts the jobs of a crashed worker back in the queue (or fails them after
  `max_attempts`).
- Progress and status changes reach the job's author live through the existing
  real-time channel (`realtime.publish`, delivered on commit); the page also polls.

Handlers get a `JobContext` for progress and cancellation checks. Nothing here logs
book text: only ids, kinds, codes.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import Conflict, NotFound
from app.models import Book, BookJob, User
from app.models.enums import ACTIVE_JOB_STATUSES, BookJobKind, BookJobStatus

log = logging.getLogger(__name__)

RECOVER_LOCK = 724_105  # advisory lock: one worker recovers stale jobs at a time
HEARTBEAT_SECONDS = 30
RETRY_BASE_SECONDS = 30
RETRY_MAX_SECONDS = 600
MAX_DETAIL = 500


class JobCancelled(Exception):
    """Raised by JobContext.check_cancel when the job was cancelled."""


class FinalJobError(Exception):
    """A failure retrying would not fix (a broken PDF, a refused request)."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class RetryableJobError(Exception):
    """A temporary failure (storage or network): the job goes back to the queue."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class Handler:
    run: Callable[[Session, BookJob, JobContext], None]
    on_failed: Callable[[Session, BookJob], None] | None = None
    on_cancelled: Callable[[Session, BookJob], None] | None = None


HANDLERS: dict[BookJobKind, Handler] = {}


def register(kind: BookJobKind, *, on_failed=None, on_cancelled=None):
    def wrap(fn):
        HANDLERS[kind] = Handler(fn, on_failed, on_cancelled)
        return fn
    return wrap


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- events ----------

def job_payload(job: BookJob) -> dict[str, Any]:
    return {
        "id": job.id, "book_id": job.book_id, "kind": job.kind.value, "status": job.status.value,
        "progress": job.progress, "error_code": job.error_code,
    }


def publish_job(db: Session, job: BookJob) -> None:
    """Live update for the job's author (delivered when the transaction commits)."""
    from app.services import realtime

    if job.created_by_id:
        realtime.publish(db, [{"user_id": job.created_by_id, "book_job": job_payload(job)}])


# ---------- the web side ----------

def enqueue(db: Session, book: Book, kind: BookJobKind, user: User | None,
            job_settings: dict[str, Any] | None = None) -> BookJob:
    """A new queued job (the caller commits). One active job per book and kind."""
    busy = db.scalar(select(BookJob.id).where(
        BookJob.book_id == book.id, BookJob.kind == kind, BookJob.status.in_(ACTIVE_JOB_STATUSES)
    ))
    if busy:
        raise Conflict("Эта книга уже обрабатывается")
    job = BookJob(
        book_id=book.id, kind=kind, settings=job_settings or {}, created_by_id=user.id if user else None,
        max_attempts=settings.BOOK_JOB_MAX_ATTEMPTS,
    )
    db.add(job)
    db.flush()
    publish_job(db, job)
    return job


def get_job(db: Session, job_id: int) -> BookJob:
    job = db.get(BookJob, job_id)
    if job is None:
        raise NotFound("Задание обработки не найдено")
    return job


def latest_jobs(db: Session, book_id: int, limit: int = 20) -> list[BookJob]:
    return list(db.scalars(
        select(BookJob).where(BookJob.book_id == book_id).order_by(BookJob.created_at.desc(), BookJob.id.desc()).limit(limit)
    ).all())


def cancel(db: Session, job: BookJob) -> BookJob:
    """A queued job stops at once; a running one at the handler's next check (the caller commits)."""
    if job.status == BookJobStatus.QUEUED:
        _finish(db, job, BookJobStatus.CANCELLED)
    elif job.status == BookJobStatus.RUNNING:
        job.cancel_requested = True
        publish_job(db, job)
    else:
        raise Conflict("Задание обработки уже завершено")
    return job


# ---------- the worker side ----------

def claim_next(worker_id: str, now: datetime | None = None) -> int | None:
    """Take the oldest due job, or None. Commits, so other workers skip it at once."""
    now = now or _now()
    with SessionLocal() as db:
        job = db.scalar(
            select(BookJob)
            .where(
                BookJob.status == BookJobStatus.QUEUED,
                BookJob.cancel_requested.is_(False),
                or_(BookJob.not_before.is_(None), BookJob.not_before <= now),
            )
            .order_by(BookJob.created_at, BookJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        job.status = BookJobStatus.RUNNING
        job.attempts += 1
        job.locked_by, job.locked_at, job.heartbeat_at = worker_id[:100], now, now
        job.started_at = job.started_at or now
        job.error_code = job.error_detail = None
        publish_job(db, job)
        db.commit()
        log.info("Job %s (%s) taken by %s, attempt %d", job.id, job.kind.value, worker_id, job.attempts)
        return job.id


class JobContext:
    """What a handler may do with its job: report progress, check for cancellation."""

    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
        self._last_pct = -1

    def progress(self, pct: int) -> None:
        pct = max(0, min(100, int(pct)))
        if pct == self._last_pct:
            return
        self._last_pct = pct
        with SessionLocal() as db:
            job = db.get(BookJob, self.job_id)
            if job is None:
                raise JobCancelled()  # the book was deleted
            job.progress, job.heartbeat_at = pct, _now()
            publish_job(db, job)
            db.commit()
            if job.cancel_requested:
                raise JobCancelled()

    def record_usage(self, usage: dict[str, Any]) -> None:
        """Add an AI run's tokens and cost to the job, in its own transaction: what was
        spent stays on record even when the job then fails or is retried."""
        with SessionLocal() as db:
            job = db.get(BookJob, self.job_id)
            if job is None:
                return
            job.usage = merge_usage(job.usage, usage)
            db.commit()

    def check_cancel(self) -> None:
        with SessionLocal() as db:
            requested = db.scalar(select(BookJob.cancel_requested).where(BookJob.id == self.job_id))
        if requested is None or requested:
            raise JobCancelled()


def merge_usage(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """Sum two AIUsage.to_dict() records (retries of the same job add up)."""
    if not old:
        return dict(new)
    out = dict(old)
    for k in ("requests", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
        out[k] = (old.get(k) or 0) + (new.get(k) or 0)
    cost_old, cost_new = old.get("estimated_cost_usd"), new.get("estimated_cost_usd")
    out["estimated_cost_usd"] = None if cost_old is None or cost_new is None else round(cost_old + cost_new, 6)
    by_model = {m: dict(c) for m, c in (old.get("by_model") or {}).items()}
    for m, c in (new.get("by_model") or {}).items():
        cur = by_model.setdefault(m, {})
        for k, v in c.items():
            cur[k] = (cur.get(k) or 0) + (v or 0)
    out["by_model"] = by_model
    return out


def _heartbeat(job_id: int, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_SECONDS):
        try:
            with SessionLocal() as db:
                db.execute(
                    text("UPDATE book_jobs SET heartbeat_at = now() WHERE id = :id AND status = 'running'"),
                    {"id": job_id},
                )
                db.commit()
        except Exception:  # the next beat retries; stale recovery covers a dead worker
            log.exception("Job %s: heartbeat failed", job_id)


def _finish(db: Session, job: BookJob, status: BookJobStatus, code: str | None = None,
            detail: str | None = None) -> None:
    job.status = status
    job.finished_at = _now()
    job.locked_by = None
    if status == BookJobStatus.DONE:
        job.progress = 100
    job.error_code = code
    job.error_detail = (detail or None) and detail[:MAX_DETAIL]
    handler = HANDLERS.get(job.kind)
    if status == BookJobStatus.FAILED and handler and handler.on_failed:
        handler.on_failed(db, job)
    if status == BookJobStatus.CANCELLED and handler and handler.on_cancelled:
        handler.on_cancelled(db, job)
    publish_job(db, job)


def _retry_or_fail(db: Session, job: BookJob, code: str, detail: str | None) -> BookJobStatus:
    if job.attempts >= job.max_attempts:
        _finish(db, job, BookJobStatus.FAILED, code, detail)
        return BookJobStatus.FAILED
    delay = min(RETRY_BASE_SECONDS * 2 ** (job.attempts - 1), RETRY_MAX_SECONDS)
    job.status = BookJobStatus.QUEUED
    job.not_before = _now() + timedelta(seconds=delay)
    job.locked_by = None
    job.error_code, job.error_detail = code, (detail or None) and detail[:MAX_DETAIL]
    publish_job(db, job)
    return BookJobStatus.QUEUED


def run_job(job_id: int) -> BookJobStatus | None:
    """Run a claimed job to its outcome. Returns the job's status afterwards (None: it is gone)."""
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(job_id, stop), name=f"job-{job_id}-heartbeat", daemon=True)
    beat.start()
    try:
        return _run(job_id)
    finally:
        stop.set()


def _run(job_id: int) -> BookJobStatus | None:
    with SessionLocal() as db:
        job = db.get(BookJob, job_id)
        if job is None or job.status != BookJobStatus.RUNNING:
            return job.status if job else None
        handler = HANDLERS.get(job.kind)
        outcome: tuple[str, str | None, str | None]
        try:
            if handler is None:
                raise FinalJobError("no_handler")
            handler.run(db, job, JobContext(job_id))
            db.flush()
            outcome = ("done", None, None)
        except JobCancelled:
            outcome = ("cancelled", None, None)
        except FinalJobError as e:
            outcome = ("failed", e.code, e.detail)
        except RetryableJobError as e:
            outcome = ("retry", e.code, e.detail)
        except Exception as e:  # an unexpected error: retried, then failed
            log.exception("Job %s (%s) crashed", job_id, job.kind.value)
            outcome = ("retry", "internal_error", type(e).__name__)

        kind, code, detail = outcome
        if kind != "done":
            db.rollback()  # drop the handler's half-done changes
            job = db.get(BookJob, job_id)
            if job is None:
                return None
        if kind == "done":
            _finish(db, job, BookJobStatus.DONE)
        elif kind == "cancelled":
            _finish(db, job, BookJobStatus.CANCELLED)
        elif kind == "failed":
            _finish(db, job, BookJobStatus.FAILED, code, detail)
        else:
            _retry_or_fail(db, job, code or "internal_error", detail)
        db.commit()
        log.info("Job %s (%s) -> %s%s", job_id, job.kind.value, job.status.value, f" ({job.error_code})" if job.error_code else "")
        return job.status


def recover_stale(now: datetime | None = None) -> int:
    """Running jobs whose worker stopped beating: back to the queue, or failed after
    max_attempts. Returns how many were touched."""
    now = now or _now()
    cutoff = now - timedelta(minutes=settings.BOOK_JOB_STALE_MINUTES)
    with SessionLocal() as db:
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": RECOVER_LOCK}):
            return 0
        stale = db.scalars(
            select(BookJob).where(
                BookJob.status == BookJobStatus.RUNNING,
                or_(BookJob.heartbeat_at.is_(None), BookJob.heartbeat_at < cutoff),
            ).with_for_update(skip_locked=True)
        ).all()
        for job in stale:
            log.warning("Job %s: worker %s stopped responding", job.id, job.locked_by)
            if job.cancel_requested:
                _finish(db, job, BookJobStatus.CANCELLED)
            else:
                _retry_or_fail(db, job, "worker_lost", None)
        db.commit()
        return len(stale)

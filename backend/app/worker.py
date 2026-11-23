"""Book-to-Test worker: `python -m app.worker` (the `worker` service in docker-compose.yml).

Takes jobs from the PostgreSQL queue (services/book_jobs.py) and runs them, so
long PDF processing and AI generation never run inside a web request. It does
not run the web app's background loops (subscriptions, e-mail, storage sweep).

- BOOK_WORKER_CONCURRENCY threads, each taking one job at a time;
- every minute one of them puts back the jobs of a worker that stopped
  responding (heartbeat older than BOOK_JOB_STALE_MINUTES);
- SIGTERM / SIGINT: finish the current job, then exit (a job cut off by a hard
  kill is recovered by the heartbeat check);
- touches a file every loop for the Docker healthcheck (`--check`).
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

from app.core.config import settings
from app.services import book_jobs
from app.services import book_processing  # importing it registers the job handlers

__all__ = ["book_processing", "check", "main", "run_once"]

log = logging.getLogger("app.worker")

ALIVE_FILE = Path(tempfile.gettempdir()) / "nexa-worker-alive"
ALIVE_MAX_AGE = 120  # seconds, for the healthcheck
RECOVER_EVERY = 60  # seconds


def worker_id(n: int = 0) -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{n}"


def run_once(wid: str = "inline") -> int | None:
    """Take and run one job; returns its id, or None when the queue is empty."""
    job_id = book_jobs.claim_next(wid)
    if job_id is not None:
        book_jobs.run_job(job_id)
    return job_id


def _loop(n: int, stop: threading.Event) -> None:
    wid = worker_id(n)
    last_recover = 0.0
    while not stop.is_set():
        try:
            if n == 0:
                ALIVE_FILE.touch()
                if time.monotonic() - last_recover > RECOVER_EVERY:
                    last_recover = time.monotonic()
                    book_jobs.recover_stale()
            if run_once(wid) is None:
                stop.wait(settings.BOOK_WORKER_POLL_SECONDS)
        except Exception:  # never let one bad poll stop the worker
            log.exception("Worker loop error")
            stop.wait(settings.BOOK_WORKER_POLL_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = threading.Event()

    def _stop(signum, _frame):
        log.info("Signal %s: finishing the current job and stopping", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    n = settings.BOOK_WORKER_CONCURRENCY
    log.info("Book-to-Test worker started: %d thread(s)", n)
    threads = [threading.Thread(target=_loop, args=(i, stop), name=f"book-worker-{i}") for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log.info("Book-to-Test worker stopped")


def check() -> int:
    """Healthcheck: 0 when the worker loop touched its file recently."""
    try:
        return 0 if time.time() - ALIVE_FILE.stat().st_mtime < ALIVE_MAX_AGE else 1
    except FileNotFoundError:
        return 1


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    main()

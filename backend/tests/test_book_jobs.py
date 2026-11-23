"""Book-to-Test, stage 2: the PostgreSQL job queue and the worker."""
import threading
from datetime import UTC, datetime, timedelta

from test_books import pdf, stored_key, upload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Book, BookJob, Notification
from app.models.enums import BookJobKind, BookJobStatus, BookStatus, NotificationType
from app.services import book_jobs, realtime
from app.services.book_jobs import FinalJobError, RetryableJobError
from app.storage.base import get_storage
from app.worker import ALIVE_FILE, check, run_once

API = "/api/v1"


def job_of(book_id: int, kind=BookJobKind.EXTRACT) -> BookJob:
    with SessionLocal() as db:
        return db.query(BookJob).filter_by(book_id=book_id, kind=kind).order_by(BookJob.id.desc()).first()


def book_row(book_id: int) -> Book:
    with SessionLocal() as db:
        return db.get(Book, book_id)


def notifications(user_id: int, type_: NotificationType) -> list[Notification]:
    with SessionLocal() as db:
        return db.query(Notification).filter_by(user_id=user_id, type=type_).all()


def test_upload_queues_processing_and_the_worker_finishes_it(client, school, monkeypatch):
    events = []
    real_publish = realtime.publish
    monkeypatch.setattr(realtime, "publish", lambda db, p: (events.extend(p), real_publish(db, p)))
    adm = school["adm"]
    b = upload(client, adm, pdf(25)).json()
    assert b["status"] == "processing" and b["processing"]["status"] == "queued" and b["processing"]["kind"] == "extract"

    assert run_once("w1") == b["processing"]["id"]
    assert run_once("w1") is None  # nothing left
    d = client.get(f"{API}/books/{b['id']}", headers=adm).json()
    assert d["status"] == "ready" and d["page_count"] == 25
    assert d["processing"]["status"] == "done" and d["processing"]["progress"] == 100 and d["processing"]["attempts"] == 1
    me = client.get(f"{API}/auth/me", headers=adm).json()["id"]
    n = notifications(me, NotificationType.BOOK_PROCESSED)
    assert len(n) == 1 and n[0].body == "Grammar in Use" and n[0].link == f"/methodist/books/{b['id']}"
    # progress went live to the author: queued, running, several progress steps, done
    statuses = [e["book_job"]["status"] for e in events if "book_job" in e]
    assert statuses[0] == "queued" and statuses[-1] == "done" and "running" in statuses
    assert len([e for e in events if "book_job" in e and e["book_job"]["status"] == "running"]) >= 3
    assert all(e["user_id"] == me for e in events if "book_job" in e)

    jobs = client.get(f"{API}/books/{b['id']}/jobs", headers=adm).json()
    assert [j["status"] for j in jobs] == ["done"]


def test_one_active_job_and_reprocess(client, school):
    adm = school["adm"]
    b = upload(client, adm).json()
    r = client.post(f"{API}/books/{b['id']}/reprocess", headers=adm)
    assert r.status_code == 409 and r.json()["detail"] == "Эта книга уже обрабатывается"
    run_once()
    r = client.post(f"{API}/books/{b['id']}/reprocess", headers=adm)
    assert r.status_code == 200 and r.json()["status"] == "processing" and r.json()["processing"]["status"] == "queued"
    run_once()
    assert book_row(b["id"]).status == BookStatus.READY
    assert len(client.get(f"{API}/books/{b['id']}/jobs", headers=adm).json()) == 2
    # rights
    jid = r.json()["processing"]["id"]
    for h in (school["ha"], school["h1"]):
        assert client.post(f"{API}/books/{b['id']}/reprocess", headers=h).status_code == 403
        assert client.get(f"{API}/books/jobs/{jid}", headers=h).status_code == 403
        assert client.post(f"{API}/books/jobs/{jid}/cancel", headers=h).status_code == 403
    assert client.get(f"{API}/books/jobs/999999", headers=adm).status_code == 404


def test_two_workers_never_take_the_same_job(client, school):
    upload(client, school["adm"])
    got: list[int | None] = []
    barrier = threading.Barrier(4)

    def take(n):
        barrier.wait()
        got.append(book_jobs.claim_next(f"w{n}"))

    threads = [threading.Thread(target=take, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len([x for x in got if x is not None]) == 1


def test_broken_file_fails_the_book_and_notifies(client, school):
    adm = school["adm"]
    b = upload(client, adm).json()
    get_storage().delete(stored_key(b["id"]))
    run_once()
    job = job_of(b["id"])
    assert job.status == BookJobStatus.FAILED and job.error_code == "file_missing" and job.attempts == 1
    book = book_row(b["id"])
    assert book.status == BookStatus.FAILED and book.error_code == "file_missing"
    me = client.get(f"{API}/auth/me", headers=adm).json()["id"]
    assert notifications(me, NotificationType.BOOK_FAILED)[0].title == "Не удалось обработать книгу"
    assert client.get(f"{API}/books/{b['id']}", headers=adm).json()["processing"]["error_code"] == "file_missing"


def test_retries_with_delay_then_fail(client, school, monkeypatch):
    calls = []

    def flaky(db, job, ctx):
        calls.append(job.attempts)
        if len(calls) == 1:
            raise RetryableJobError("storage_unavailable", "OSError")
        raise RuntimeError("boom")

    monkeypatch.setitem(book_jobs.HANDLERS, BookJobKind.GENERATE, book_jobs.Handler(flaky))
    b = upload(client, school["adm"]).json()
    run_once()  # the extract job
    with SessionLocal() as db:
        book_jobs.enqueue(db, db.get(Book, b["id"]), BookJobKind.GENERATE, None, {"pages": [1, 2]})
        db.commit()

    run_once()
    job = job_of(b["id"], BookJobKind.GENERATE)
    assert job.status == BookJobStatus.QUEUED and job.error_code == "storage_unavailable" and job.attempts == 1
    assert job.not_before > datetime.now(UTC) + timedelta(seconds=20)  # 30 s back-off
    assert run_once() is None  # not due yet

    later = datetime.now(UTC) + timedelta(hours=1)
    for _ in range(2):  # attempts 2 and 3 crash unexpectedly
        jid = book_jobs.claim_next("w", now=later)
        assert jid == job.id
        book_jobs.run_job(jid)
    job = job_of(b["id"], BookJobKind.GENERATE)
    assert job.status == BookJobStatus.FAILED and job.error_code == "internal_error"
    assert job.attempts == settings.BOOK_JOB_MAX_ATTEMPTS and calls == [1, 2, 3]
    assert job.error_detail == "RuntimeError"  # the type, never data


def test_final_error_is_not_retried(client, school, monkeypatch):
    def refuse(db, job, ctx):
        raise FinalJobError("ai_refused")

    monkeypatch.setitem(book_jobs.HANDLERS, BookJobKind.GENERATE, book_jobs.Handler(refuse))
    b = upload(client, school["adm"]).json()
    run_once()
    with SessionLocal() as db:
        book_jobs.enqueue(db, db.get(Book, b["id"]), BookJobKind.GENERATE, None)
        db.commit()
    run_once()
    job = job_of(b["id"], BookJobKind.GENERATE)
    assert job.status == BookJobStatus.FAILED and job.error_code == "ai_refused" and job.attempts == 1


def test_cancel_queued_and_running(client, school, monkeypatch):
    adm = school["adm"]
    b = upload(client, adm).json()
    jid = b["processing"]["id"]
    r = client.post(f"{API}/books/jobs/{jid}/cancel", headers=adm)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert book_row(b["id"]).status == BookStatus.UPLOADED  # back to "waiting"
    assert run_once() is None
    r = client.post(f"{API}/books/jobs/{jid}/cancel", headers=adm)
    assert r.status_code == 409

    # a running job stops at its next check
    seen = threading.Event()

    def slow(db, job, ctx):
        seen.set()
        ctx.check_cancel()

    monkeypatch.setitem(book_jobs.HANDLERS, BookJobKind.GENERATE, book_jobs.Handler(slow))
    with SessionLocal() as db:
        job = book_jobs.enqueue(db, db.get(Book, b["id"]), BookJobKind.GENERATE, None)
        db.commit()
        jid = job.id
    assert book_jobs.claim_next("w") == jid
    r = client.post(f"{API}/books/jobs/{jid}/cancel", headers=adm)
    assert r.json()["status"] == "running" and r.json()["cancel_requested"] is True
    assert book_jobs.run_job(jid) == BookJobStatus.CANCELLED and seen.is_set()


def test_stale_jobs_are_recovered(client, school):
    b = upload(client, school["adm"]).json()
    jid = book_jobs.claim_next("dead-worker")
    old = datetime.now(UTC) - timedelta(minutes=settings.BOOK_JOB_STALE_MINUTES + 1)
    with SessionLocal() as db:
        db.get(BookJob, jid).heartbeat_at = old
        db.commit()
    assert book_jobs.recover_stale() == 1
    job = job_of(b["id"])
    assert job.status == BookJobStatus.QUEUED and job.error_code == "worker_lost" and job.locked_by is None

    # the last allowed attempt: failed, and the book says so
    jid = book_jobs.claim_next("dead-again", now=datetime.now(UTC) + timedelta(hours=1))
    with SessionLocal() as db:
        j = db.get(BookJob, jid)
        j.attempts, j.heartbeat_at = j.max_attempts, old
        db.commit()
    book_jobs.recover_stale()
    assert job_of(b["id"]).status == BookJobStatus.FAILED
    assert book_row(b["id"]).status == BookStatus.FAILED and book_row(b["id"]).error_code == "worker_lost"
    # a live job is left alone
    assert book_jobs.recover_stale() == 0


def test_deleting_a_book_removes_its_jobs(client, school):
    adm = school["adm"]
    b = upload(client, adm).json()
    jid = book_jobs.claim_next("w")
    assert client.delete(f"{API}/books/{b['id']}", headers=adm).status_code == 204
    assert book_jobs.run_job(jid) is None  # the worker just finds nothing


def test_sse_carries_job_events_and_worker_healthcheck():
    import asyncio

    async def go():
        loop = asyncio.get_running_loop()
        broker = realtime.NotificationBroker()
        broker.bind_loop(loop)
        q = broker.subscribe(7)
        broker.dispatch({"user_id": 7, "book_job": {"id": 1, "status": "running", "progress": 40}})
        return await asyncio.wait_for(q.get(), 1)

    assert asyncio.run(go()) == ("book_job", {"id": 1, "status": "running", "progress": 40})
    ALIVE_FILE.touch()
    assert check() == 0

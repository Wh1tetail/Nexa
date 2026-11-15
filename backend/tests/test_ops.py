"""Operational safety: behaviour that matters when several workers run at once."""
from datetime import UTC, datetime, timedelta

import pytest
from conftest import make_user
from fastapi import HTTPException
from sqlalchemy import text

from app.core.database import SessionLocal
from app.middleware.rate_limit import AttemptLimiter, _hash
from app.models import AuthAttempt
from app.models.enums import UserRole
from app.services.subscription_service import EXPIRY_CHECK_LOCK, check_expirations

API = "/api/v1"


def test_expiry_check_skips_while_another_worker_runs_it(client, school):
    today = datetime.now(UTC).date()
    _, newcomer = make_user(UserRole.STUDENT, "newcomer@test.io", school["ta"], "Newcomer")  # no other subscription
    client.post(f"{API}/subscriptions", headers=school["aa"], json={
        "student_id": newcomer.id, "start_date": str(today - timedelta(days=30)),
        "end_date": str(today - timedelta(days=1)), "total_lessons": 8})

    with SessionLocal() as other_worker:
        # another worker is in the middle of the check (holds the advisory lock)
        assert other_worker.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": EXPIRY_CHECK_LOCK})
        with SessionLocal() as db:
            assert check_expirations(db) == 0  # skipped, nothing sent
        other_worker.rollback()  # lock released at the end of its transaction

    with SessionLocal() as db:
        assert check_expirations(db) == 1  # now it runs
    notes = client.get(f"{API}/notifications", headers=school["ha"]).json()
    assert sum(n["type"] == "subscription_expired" for n in notes) == 1


def test_login_limit_is_shared_between_workers():
    # two limiter objects = two worker processes; the state lives in PostgreSQL
    worker_a, worker_b = AttemptLimiter(3, 60), AttemptLimiter(3, 60)
    worker_a.hit("x@test.io")
    worker_b.hit("x@test.io")
    worker_a.check("x@test.io")  # 2 of 3: still allowed
    worker_b.hit("x@test.io")
    with pytest.raises(HTTPException) as exc:
        worker_a.check("x@test.io")
    assert exc.value.status_code == 429
    worker_b.check("other@test.io")  # other keys are not affected

    with SessionLocal() as db:  # keys are hashed: no e-mail addresses in the table
        keys = db.scalars(text("SELECT key FROM auth_attempts")).all()
    assert keys and all("@" not in k and len(k) == 64 for k in keys)

    worker_b.reset("x@test.io")  # successful login clears the counter everywhere
    worker_a.check("x@test.io")


def test_expired_attempts_do_not_count(client):
    limiter = AttemptLimiter(2, 60)
    with SessionLocal() as db:
        old = datetime.now(UTC) - timedelta(minutes=5)
        db.add_all([AuthAttempt(key=_hash("k"), attempted_at=old) for _ in range(5)])
        db.commit()
    limiter.check("k")  # old attempts are outside the window
    limiter.hit("k")  # ... and are purged on the next hit
    with SessionLocal() as db:
        assert db.scalar(text("SELECT count(*) FROM auth_attempts")) == 1

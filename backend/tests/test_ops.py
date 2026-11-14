"""Operational safety: behaviour that matters when several workers run at once."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.subscription_service import EXPIRY_CHECK_LOCK, check_expirations

API = "/api/v1"


def test_expiry_check_skips_while_another_worker_runs_it(client, school):
    today = datetime.now(UTC).date()
    client.post(f"{API}/subscriptions", headers=school["ha"], json={
        "student_id": school["s1"].id, "start_date": str(today - timedelta(days=30)),
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

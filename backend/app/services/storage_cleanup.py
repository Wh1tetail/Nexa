"""Removes stored files that no `attachments` row refers to any more.

Rows disappear by database cascade (a student, a test, a homework or a chat
message deleted) without the ORM ever seeing them, so their files stay in the
storage. This sweep compares the storage with the database:

- only objects older than STORAGE_SWEEP_GRACE_HOURS are considered, so a file
  that was just saved but whose row is not committed yet is never touched;
- a PostgreSQL advisory lock lets only one worker sweep at a time;
- `dry_run=True` reports what would be deleted (python -m scripts.sweep_storage).
"""
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Attachment
from app.storage.base import Storage, get_storage

log = logging.getLogger(__name__)

SWEEP_LOCK = 724_003
CHUNK = 1000


@dataclass
class SweepResult:
    checked: int = 0
    orphans: list[str] = field(default_factory=list)
    deleted: int = 0
    skipped: bool = False  # another worker holds the lock


def _chunks(items: Iterator[tuple[str, datetime]], size: int) -> Iterator[list[tuple[str, datetime]]]:
    batch: list[tuple[str, datetime]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def sweep_orphans(
    db: Session,
    storage: Storage | None = None,
    *,
    grace: timedelta | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> SweepResult:
    result = SweepResult()
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": SWEEP_LOCK}):
        result.skipped = True
        return result
    storage = storage or get_storage()
    cutoff = (now or datetime.now(UTC)) - (grace if grace is not None else timedelta(hours=settings.STORAGE_SWEEP_GRACE_HOURS))
    old = ((k, m) for k, m in storage.list_keys() if m <= cutoff)
    for batch in _chunks(old, CHUNK):
        keys = [k for k, _ in batch]
        result.checked += len(keys)
        known = set(db.scalars(select(Attachment.storage_key).where(Attachment.storage_key.in_(keys))).all())
        for key in keys:
            if key in known:
                continue
            result.orphans.append(key)
            if not dry_run:
                try:
                    storage.delete(key)
                    result.deleted += 1
                except Exception:  # keep going; the next sweep retries
                    log.exception("Storage sweep: could not delete %s", key)
    db.rollback()  # releases the advisory lock; nothing was written
    if result.orphans:
        log.info("Storage sweep: %d orphan file(s) %s", len(result.orphans), "found" if dry_run else "deleted")
    return result

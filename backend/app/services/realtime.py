"""Real-time notification delivery.

Flow:
1. Whenever a `Notification` row is flushed (or a user's `token_version` is
   bumped by logout / password change / deactivation), an `after_flush` hook runs
   `pg_notify('lingua_notifications', <json>)` in the SAME transaction —
   PostgreSQL delivers it only if the transaction commits (no phantom events).
2. A background thread LISTENs on that channel (one connection per worker
   process) and hands events to the asyncio loop.
3. `NotificationBroker` fans events out to the user's open SSE streams
   (`GET /api/v1/notifications/stream`).

Because the bus is PostgreSQL itself, it works with several uvicorn workers or
servers — each process receives every event and serves its own subscribers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import psycopg
from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Notification, User

log = logging.getLogger(__name__)

CHANNEL = "lingua_notifications"
MAX_BODY = 1000  # pg_notify payload limit is 8000 bytes
QUEUE_SIZE = 100


def notification_payload(n: Notification) -> dict[str, Any]:
    body = n.body[:MAX_BODY] if n.body else None
    return {
        "user_id": n.user_id,
        "notification": {
            "id": n.id,
            "type": n.type.value if hasattr(n.type, "value") else n.type,
            "title": n.title[:200],
            "body": body,
            "link": n.link,
            "is_read": False,
            "created_at": datetime.now(UTC).isoformat(),
        },
    }


def _token_version_bumps(session: Session) -> list[tuple[int, int]]:
    """(user_id, new token_version) for users whose sessions were just revoked
    (logout, password change/reset, deactivation all increment token_version)."""
    out = []
    for obj in session.dirty:
        if isinstance(obj, User):
            hist = inspect(obj).attrs.token_version.history
            if hist.has_changes() and hist.added:
                out.append((obj.id, int(hist.added[0])))
    return out


@event.listens_for(Session, "after_flush")
def _publish_realtime_events(session: Session, _ctx) -> None:
    payloads = [notification_payload(n) for n in session.new if isinstance(n, Notification)]
    payloads += [{"user_id": uid, "revoke": ver} for uid, ver in _token_version_bumps(session)]
    if not payloads:
        return
    conn = session.connection()
    for payload in payloads:
        conn.execute(
            text("SELECT pg_notify(:ch, :payload)"),
            {"ch": CHANNEL, "payload": json.dumps(payload, ensure_ascii=False)},
        )


class NotificationBroker:
    """Per-process registry of open streams, keyed by user id."""

    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, user_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subs[user_id].add(q)
        return q

    def unsubscribe(self, user_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(user_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(user_id, None)

    def subscriber_count(self, user_id: int | None = None) -> int:
        if user_id is not None:
            return len(self._subs.get(user_id, ()))
        return sum(len(s) for s in self._subs.values())

    def dispatch(self, payload: dict[str, Any]) -> None:
        """Must run on the event loop thread. Queue items are
        ("notification", data) or ("revoke", new_token_version)."""
        if "revoke" in payload:
            item: tuple[str, Any] = ("revoke", int(payload["revoke"]))
        else:
            item = ("notification", payload["notification"])
        for q in list(self._subs.get(payload.get("user_id"), ())):
            if item[0] == "revoke":
                while not q.empty():  # nothing else matters once the session is revoked
                    q.get_nowait()
            elif q.full():  # slow client: drop the oldest event
                q.get_nowait()
            q.put_nowait(item)

    def dispatch_threadsafe(self, payload: dict[str, Any]) -> None:
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self.dispatch, payload)


broker = NotificationBroker()


class PgListener:
    """LISTEN loop in a daemon thread (sync psycopg works with any asyncio
    loop on every OS, including Windows' Proactor loop)."""

    def __init__(self, broker: NotificationBroker) -> None:
        self.broker = broker
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.connected = threading.Event()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pg-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _dsn(self) -> str:
        return settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with psycopg.connect(self._dsn(), autocommit=True) as conn:
                    conn.execute(f"LISTEN {CHANNEL}")
                    self.connected.set()
                    log.info("Realtime: listening on '%s'", CHANNEL)
                    while not self._stop.is_set():
                        for n in conn.notifies(timeout=2):
                            try:
                                self.broker.dispatch_threadsafe(json.loads(n.payload))
                            except ValueError:
                                log.warning("Realtime: bad payload %r", n.payload[:100])
            except Exception:
                self.connected.clear()
                if not self._stop.is_set():
                    log.exception("Realtime listener failed, reconnecting in 3s")
                    self._stop.wait(3)
        self.connected.clear()


listener = PgListener(broker)

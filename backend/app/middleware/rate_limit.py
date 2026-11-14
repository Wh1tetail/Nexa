"""Brute-force limiter for sign-in / password reset, stored in PostgreSQL so the
limit holds across all uvicorn workers and servers.

Attempts are written on their own connection (autocommit), independent of the
request's session: a failed login raises 401 and the request transaction is
rolled back, but the attempt must still count. Keys are stored as SHA-256
hashes, so the table never holds e-mail addresses.
"""
import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, select

from app.core.database import engine
from app.models import AuthAttempt


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class AttemptLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max = max_attempts
        self.window = timedelta(seconds=window_seconds)

    def check(self, key: str) -> None:
        since = datetime.now(UTC) - self.window
        with engine.connect() as conn:
            n = conn.scalar(
                select(func.count()).select_from(AuthAttempt).where(
                    AuthAttempt.key == _hash(key), AuthAttempt.attempted_at > since
                )
            )
        if (n or 0) >= self.max:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Слишком много попыток. Попробуйте через несколько минут",
            )

    def hit(self, key: str) -> None:
        now = datetime.now(UTC)
        with engine.begin() as conn:
            conn.execute(insert(AuthAttempt).values(key=_hash(key), attempted_at=now))
            # housekeeping: drop this key's expired attempts (keeps the table small)
            conn.execute(delete(AuthAttempt).where(
                AuthAttempt.key == _hash(key), AuthAttempt.attempted_at <= now - self.window
            ))

    def reset(self, key: str) -> None:
        with engine.begin() as conn:
            conn.execute(delete(AuthAttempt).where(AuthAttempt.key == _hash(key)))


login_limiter = AttemptLimiter(max_attempts=10, window_seconds=15 * 60)

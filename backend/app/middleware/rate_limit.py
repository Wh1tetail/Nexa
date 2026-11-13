"""Tiny in-memory brute-force limiter for login / password reset.
For multi-instance deployments replace with Redis-backed storage."""
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status


class AttemptLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max = max_attempts
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _prune(self, key: str) -> list[float]:
        now = time.monotonic()
        hits = [t for t in self._hits[key] if now - t < self.window]
        self._hits[key] = hits
        return hits

    def check(self, key: str) -> None:
        with self._lock:
            if len(self._prune(key)) >= self.max:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Слишком много попыток. Попробуйте через несколько минут",
                )

    def hit(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


login_limiter = AttemptLimiter(max_attempts=10, window_seconds=15 * 60)

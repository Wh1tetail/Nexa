"""Time zone helpers.

All timestamps are stored in UTC. Wall-clock logic (weekly series, texts shown
to people) uses the user's IANA time zone (`users.timezone`), falling back to
settings.DEFAULT_TIMEZONE for users who never set one.
"""
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from app.core.config import settings


@lru_cache
def _known_zones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    return name in _known_zones()


def get_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or settings.DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.DEFAULT_TIMEZONE)


def to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz)


def from_wall_clock(naive_local: datetime, tz: ZoneInfo) -> datetime:
    """Interpret a naive wall-clock time in `tz` and return it in UTC.
    Non-existent times (spring-forward gap) resolve forward, ambiguous ones
    (fall-back) to the first occurrence — zoneinfo's fold=0 behaviour."""
    return naive_local.replace(tzinfo=tz, fold=0).astimezone(UTC)


def add_weeks_local(dt: datetime, weeks: int, tz: ZoneInfo) -> datetime:
    """Same weekday and same local time `weeks` weeks later (DST-safe)."""
    local = to_local(dt, tz).replace(tzinfo=None)
    return from_wall_clock(local + timedelta(weeks=weeks), tz)


def shift_wall_clock(dt: datetime, delta: timedelta, tz: ZoneInfo) -> datetime:
    """Move `dt` by `delta` measured on the local clock (DST-safe)."""
    local = to_local(dt, tz).replace(tzinfo=None)
    return from_wall_clock(local + delta, tz)


def wall_clock_delta(old: datetime, new: datetime, tz: ZoneInfo) -> timedelta:
    """Difference between two moments as seen on the local clock."""
    return to_local(new, tz).replace(tzinfo=None) - to_local(old, tz).replace(tzinfo=None)


def fmt_local(dt: datetime, tz: ZoneInfo, with_zone: bool = True) -> str:
    local = to_local(dt, tz)
    text = local.strftime("%d.%m.%Y %H:%M")
    return f"{text} ({tz.key})" if with_zone else text

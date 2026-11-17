from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AchievementCode, XPReason


class XPSettings(BaseModel):
    """XP per action (administrators change them; new awards use the new values)."""
    lesson: int = Field(default=10, ge=0, le=1000)
    test: int = Field(default=5, ge=0, le=1000)
    test_bonus: int = Field(default=5, ge=0, le=1000)
    bonus_threshold: int = Field(default=90, ge=50, le=100)  # % from which the test bonus is paid
    module: int = Field(default=30, ge=0, le=5000)
    level: int = Field(default=100, ge=0, le=10000)


class AchievementOut(BaseModel):
    code: AchievementCode
    earned_at: datetime | None
    progress: int | None = None  # e.g. lessons completed of 10, current streak of 7
    target: int | None = None


class XPEntry(BaseModel):
    reason: XPReason
    points: int
    title: str
    created_at: datetime


class GamificationOut(BaseModel):
    xp_total: int
    level: int  # gamification level (from XP)
    level_xp: int  # XP at which the current level started
    next_level_xp: int  # XP needed for the next level
    streak_days: int  # learning days in a row up to today (or yesterday)
    achievements: list[AchievementOut]
    recent: list[XPEntry]
    settings: XPSettings


class Awards(BaseModel):
    """What an action has just earned (for a toast)."""
    xp: int = 0
    achievements: list[AchievementCode] = []

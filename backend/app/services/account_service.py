"""Password links (reset / invitation)."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_reset_token
from app.models import PasswordResetToken, User


def issue_password_link(db: Session, user: User, lifetime: timedelta) -> str:
    """Create a single-use set-password token (previous ones are invalidated).
    Returns the frontend URL; only the token hash is stored. Caller commits."""
    now = datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw, token_hash = generate_reset_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=now + lifetime))
    return f"{settings.FRONTEND_URL}/reset-password?token={raw}"


def reset_link(db: Session, user: User) -> str:
    return issue_password_link(db, user, timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES))


def invite_link(db: Session, user: User) -> str:
    return issue_password_link(db, user, timedelta(hours=settings.INVITE_EXPIRE_HOURS))

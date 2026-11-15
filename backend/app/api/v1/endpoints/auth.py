import logging
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, CurrentUser
from app.core.config import settings
from app.core.exceptions import BadRequest, Unauthorized
from app.core.i18n import tr
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.middleware.rate_limit import login_limiter
from app.services.email_outbox import effective_prefs
from app.models import PasswordResetToken, User
from app.models.enums import UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
)
from app.schemas.common import Message
from app.schemas.user import MeOut, UpdateMeRequest
from app.services import account_service, email_service, subscription_service

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)


def _tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(user.id, "access", user.token_version, user.role.value),
        refresh_token=create_token(user.id, "refresh", user.token_version, user.role.value),
    )


def me_out(user: User, db: Session | None = None) -> MeOut:
    out = MeOut.model_validate(user)
    if user.role == UserRole.STUDENT and user.student_profile and db is not None:
        out.access_active = subscription_service.has_access(db, user.student_profile.id)
    out.email_prefs = effective_prefs(user)
    if user.role == UserRole.STUDENT and user.student_profile:
        sp = user.student_profile
        out.student_id = sp.id
        out.english_level = sp.english_level
        out.teacher_name = sp.teacher.user.full_name if sp.teacher else None
    if user.role == UserRole.TEACHER and user.teacher_profile:
        out.teacher_id = user.teacher_profile.id
    return out


@router.post("/login", response_model=TokenPair)
def login(data: LoginRequest, db: DB) -> TokenPair:
    login_limiter.check(data.email.lower())
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    # Same error for unknown email and wrong password (no user enumeration).
    if not user or not verify_password(data.password, user.password_hash):
        login_limiter.hit(data.email.lower())
        raise Unauthorized("Неверный email или пароль")
    if not user.is_active:
        raise Unauthorized("Аккаунт деактивирован. Обратитесь к администратору")
    login_limiter.reset(data.email.lower())
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: DB) -> TokenPair:
    try:
        payload = decode_token(data.refresh_token)
    except jwt.PyJWTError:
        raise Unauthorized("Сессия истекла, войдите снова") from None
    if payload.get("type") != "refresh":
        raise Unauthorized("Неверный тип токена")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active or user.token_version != payload.get("ver"):
        raise Unauthorized("Сессия недействительна")
    return _tokens(user)


@router.post("/logout", response_model=Message)
def logout(user: CurrentUser, db: DB) -> Message:
    # Invalidate every issued access/refresh token for this user.
    user.token_version += 1
    db.commit()
    return Message(detail=tr("Вы вышли из аккаунта"))


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, db: DB) -> MeOut:
    return me_out(user, db)


@router.patch("/me", response_model=MeOut)
def update_me(data: UpdateMeRequest, user: CurrentUser, db: DB) -> MeOut:
    changes = data.model_dump(exclude_unset=True)
    prefs = changes.pop("email_prefs", None)
    for field, value in changes.items():
        if value is not None:
            setattr(user, field, value)
    if prefs is not None:
        user.email_prefs = {**effective_prefs(user), **prefs}  # new dict: JSONB change is tracked
    db.commit()
    return me_out(user, db)


@router.post("/change-password", response_model=TokenPair)
def change_password(data: ChangePasswordRequest, user: CurrentUser, db: DB) -> TokenPair:
    if not verify_password(data.current_password, user.password_hash):
        raise BadRequest("Текущий пароль указан неверно")
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    return _tokens(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(data: ForgotPasswordRequest, db: DB, background: BackgroundTasks) -> ForgotPasswordResponse:
    login_limiter.check("reset:" + data.email.lower())
    login_limiter.hit("reset:" + data.email.lower())
    generic = tr("Если аккаунт с таким email существует, мы отправили инструкцию по восстановлению")
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not user.is_active:
        return ForgotPasswordResponse(detail=generic)
    url = account_service.reset_link(db, user)
    db.commit()
    background.add_task(email_service.password_reset, user.email, user.full_name, url, user.locale)
    # In DEBUG the link is also returned so the flow works without a mail server.
    return ForgotPasswordResponse(detail=generic, dev_reset_url=url if settings.DEBUG else None)


@router.post("/reset-password", response_model=Message)
def reset_password(data: ResetPasswordRequest, db: DB) -> Message:
    token = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(data.token))
    )
    if not token or token.used_at is not None or token.expires_at < datetime.now(UTC):
        raise BadRequest("Ссылка недействительна или устарела")
    user = db.get(User, token.user_id)
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    token.used_at = datetime.now(UTC)
    db.commit()
    return Message(detail=tr("Пароль изменён. Войдите с новым паролем"))

import asyncio
import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentUser, bearer
from app.core.exceptions import NotFound
from app.core.security import decode_token
from app.models import Notification
from app.schemas.common import Message
from app.schemas.notification import NotificationOut
from app.services.realtime import broker

router = APIRouter(prefix="/notifications", tags=["notifications"])


class UnreadCount(BaseModel):
    count: int


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: CurrentUser, db: DB, unread_only: bool = False, limit: int = 50, offset: int = 0
) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.is_read.is_(False))
    q = q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(min(limit, 200)).offset(offset)
    return list(db.scalars(q).all())


HEARTBEAT_SECONDS = 15  # client watchdog reconnects after 40s of silence


def sse(event_name: str, data: object) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def stream(
    user: CurrentUser,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> StreamingResponse:
    """Server-Sent Events stream of the current user's new notifications.

    Auth uses the regular `Authorization: Bearer` header (the client reads the
    stream with fetch, so the token never appears in a URL). The stream ends
    when the access token expires — the client refreshes it and reconnects.
    Events: `ready`, `notification` (JSON like NotificationOut), `expired`,
    `revoked` (logout / password change / deactivation — sent immediately, then
    the stream closes);
    `: ping` comments keep proxies from closing the connection.
    """
    token = decode_token(creds.credentials)  # already validated by CurrentUser
    expires_at = float(token["exp"])
    token_version = int(token["ver"])
    user_id = user.id

    async def events():
        queue = broker.subscribe(user_id)
        try:
            yield "retry: 5000\n" + sse("ready", {})
            while True:
                remaining = expires_at - time.time()
                if remaining <= 0:
                    yield sse("expired", {})
                    return
                try:
                    kind, data = await asyncio.wait_for(queue.get(), timeout=min(HEARTBEAT_SECONDS, remaining))
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if kind == "revoke":
                    if data > token_version:  # this stream's token is no longer valid
                        yield sse("revoked", {})
                        return
                    continue
                yield sse("notification", data)
        finally:
            broker.unsubscribe(user_id, queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: CurrentUser, db: DB) -> UnreadCount:
    n = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    )
    return UnreadCount(count=n or 0)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: CurrentUser, db: DB) -> Notification:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise NotFound("Уведомление не найдено")
    n.is_read = True
    db.commit()
    return n


@router.post("/read-all", response_model=Message)
def mark_all_read(user: CurrentUser, db: DB) -> Message:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return Message(detail="Все уведомления прочитаны")

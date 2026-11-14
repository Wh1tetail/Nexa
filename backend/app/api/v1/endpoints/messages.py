from fastapi import APIRouter, Query, status

from app.api.deps import DB, CurrentUser
from app.models import Message
from app.schemas.message import MessageCreate, MessageOut, ReadResult, ThreadOut, UnreadCount
from app.services import message_service

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/threads", response_model=list[ThreadOut])
def list_threads(user: CurrentUser, db: DB) -> list[dict]:
    return message_service.list_threads(db, user)


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: CurrentUser, db: DB) -> UnreadCount:
    return UnreadCount(count=message_service.unread_total(db, user))


@router.get("/threads/{student_id}", response_model=list[MessageOut])
def list_messages(
    student_id: int,
    user: CurrentUser,
    db: DB,
    before_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> list[Message]:
    thread = message_service.get_thread(db, user, student_id)
    return message_service.list_messages(db, thread, before_id, limit)


@router.post("/threads/{student_id}", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(student_id: int, data: MessageCreate, user: CurrentUser, db: DB) -> Message:
    thread = message_service.get_thread(db, user, student_id)
    return message_service.send_message(db, thread, data.body)


@router.post("/threads/{student_id}/read", response_model=ReadResult)
def mark_read(student_id: int, user: CurrentUser, db: DB) -> ReadResult:
    thread = message_service.get_thread(db, user, student_id)
    return ReadResult(count=message_service.mark_read(db, thread))

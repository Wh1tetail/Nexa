from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import DB, CurrentUser
from app.services.file_service import get_accessible_attachment
from app.storage.base import get_storage

router = APIRouter(prefix="/files", tags=["files"])

INLINE_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"}


@router.get("/{attachment_id}")
def download(attachment_id: int, user: CurrentUser, db: DB, inline: bool = False) -> StreamingResponse:
    att = get_accessible_attachment(db, user, attachment_id)
    disposition = "inline" if inline and att.mime_type in INLINE_TYPES else "attachment"
    return StreamingResponse(
        get_storage().open(att.storage_key),
        media_type=att.mime_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(att.original_name)}",
            "Content-Length": str(att.size_bytes),
            "Cache-Control": "private, no-store",
        },
    )

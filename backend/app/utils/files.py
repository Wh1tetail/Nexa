"""Upload validation: extension allow-list, size limit and MIME sniffing by
magic bytes (the client-declared Content-Type is never trusted on its own)."""
import re
import unicodedata
from dataclasses import dataclass

import filetype
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import BadRequest

# extension -> (canonical mime, set of acceptable sniffed mimes; None = text file)
ALLOWED: dict[str, tuple[str, set[str] | None]] = {
    "pdf": ("application/pdf", {"application/pdf"}),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
    ),
    "doc": ("application/msword", {"application/msword", "application/x-ole-storage", "application/x-msi"}),
    "pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
        },
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        },
    ),
    "jpg": ("image/jpeg", {"image/jpeg"}),
    "jpeg": ("image/jpeg", {"image/jpeg"}),
    "png": ("image/png", {"image/png"}),
    "webp": ("image/webp", {"image/webp"}),
    "gif": ("image/gif", {"image/gif"}),
    "heic": ("image/heic", {"image/heic", "image/heif"}),
    "mp3": ("audio/mpeg", {"audio/mpeg"}),
    "m4a": ("audio/mp4", {"audio/mp4", "audio/m4a", "video/mp4"}),
    "wav": ("audio/wav", {"audio/x-wav", "audio/wav"}),
    "ogg": ("audio/ogg", {"audio/ogg", "application/ogg", "video/ogg"}),
    "txt": ("text/plain", None),
}

ALLOWED_EXTENSIONS = sorted(ALLOWED)


@dataclass
class ValidatedFile:
    data: bytes
    original_name: str
    extension: str
    mime_type: str


def safe_filename(name: str) -> str:
    name = unicodedata.normalize("NFC", name).replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name).strip(" .")
    return (name or "file")[:200]


async def validate_upload(upload: UploadFile) -> ValidatedFile:
    original = safe_filename(upload.filename or "file")
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED:
        raise BadRequest(
            "Недопустимый формат файла «{name}». Разрешены: {allowed}",
            name=original, allowed=", ".join(ALLOWED_EXTENSIONS),
        )

    limit = settings.max_upload_bytes
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise BadRequest("Файл «{name}» превышает {mb} МБ", name=original, mb=settings.MAX_UPLOAD_SIZE_MB)
        chunks.append(chunk)
    data = b"".join(chunks)
    if size == 0:
        raise BadRequest("Файл «{name}» пустой", name=original)

    canonical, accepted = ALLOWED[ext]
    if accepted is None:
        # text file: must decode as UTF-8 and must not be a known binary format
        if filetype.guess(data) is not None:
            raise BadRequest("Содержимое файла «{name}» не соответствует расширению", name=original)
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise BadRequest("Файл «{name}» должен быть в кодировке UTF-8", name=original) from None
    else:
        kind = filetype.guess(data)
        if kind is None or kind.mime not in accepted:
            raise BadRequest("Содержимое файла «{name}» не соответствует расширению .{ext}", name=original, ext=ext)

    return ValidatedFile(data=data, original_name=original, extension=ext, mime_type=canonical)

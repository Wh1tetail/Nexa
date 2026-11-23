"""Pluggable file storage. LocalStorage for development, S3Storage for any
S3-compatible provider (AWS, MinIO, Yandex Object Storage, ...)."""
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
import shutil
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> None: ...

    def save_file(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        """Save from an open file without reading it into memory (large uploads)."""
        fileobj.seek(0)
        self.save(key, fileobj.read(), content_type)

    @abstractmethod
    def open(self, key: str) -> Iterator[bytes]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def list_keys(self) -> Iterator[tuple[str, datetime]]:
        """Every stored object as (key, last modified, UTC) — for the orphan sweep."""


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        # Path traversal guard
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_file(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fileobj.seek(0)
        with path.open("wb") as out:
            shutil.copyfileobj(fileobj, out, 1024 * 1024)

    def open(self, key: str) -> Iterator[bytes]:
        path = self._path(key)
        with path.open("rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list_keys(self) -> Iterator[tuple[str, datetime]]:
        for path in self.root.rglob("*"):
            if path.is_file():
                key = path.relative_to(self.root).as_posix()
                yield key, datetime.fromtimestamp(path.stat().st_mtime, UTC)


class S3Storage(Storage):
    def __init__(self) -> None:
        import boto3  # imported lazily: only needed when STORAGE_BACKEND=s3

        if not settings.S3_BUCKET:
            raise RuntimeError("S3_BUCKET must be set when STORAGE_BACKEND=s3")
        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
        )

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def save_file(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        fileobj.seek(0)
        self.client.upload_fileobj(fileobj, self.bucket, key, ExtraArgs={"ContentType": content_type})

    def open(self, key: str) -> Iterator[bytes]:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        yield from obj["Body"].iter_chunks(64 * 1024)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def list_keys(self) -> Iterator[tuple[str, datetime]]:
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            for obj in page.get("Contents", []):
                yield obj["Key"], obj["LastModified"]


@lru_cache
def get_storage() -> Storage:
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage(Path(settings.LOCAL_STORAGE_PATH))

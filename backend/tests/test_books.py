"""Book-to-Test, stage 1: uploading and storing PDF books."""
import io
import os
import time
from datetime import timedelta

from conftest import login, make_user
from pypdf import PdfWriter

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Attachment, Book
from app.models.enums import UserRole
from app.services.storage_cleanup import sweep_orphans
from app.storage.base import get_storage

API = "/api/v1"


def pdf(pages=3, password: str | None = None) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    if password:
        w.encrypt(password)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def upload(client, h, data=None, name="Grammar in Use.pdf", **form):
    fields = {"title": "Grammar in Use", "author": "R. Murphy", "language": "en", "level": "B1", **form}
    return client.post(f"{API}/books", headers=h, data={k: v for k, v in fields.items() if v is not None},
                       files={"file": (name, data if data is not None else pdf(), "application/pdf")})


def methodist(client):
    make_user(UserRole.METHODIST, "method@test.io", name="Mila Methodist")
    return login(client, "method@test.io")


def stored_key(book_id: int) -> str:
    with SessionLocal() as db:
        return db.query(Attachment).filter_by(book_id=book_id).one().storage_key


def test_methodist_uploads_lists_edits_and_deletes(client, school):
    hm = methodist(client)
    r = upload(client, hm, pdf(5))
    assert r.status_code == 201, r.text
    b = r.json()
    assert (b["title"], b["author"], b["language"], b["level"], b["page_count"], b["status"]) == (
        "Grammar in Use", "R. Murphy", "en", "B1", 5, "uploaded")
    assert b["uploaded_by_name"] == "Mila Methodist" and b["file"]["mime_type"] == "application/pdf"
    assert b["file"]["original_name"] == "Grammar in Use.pdf" and b["file"]["size_bytes"] > 0

    # books are shared by the editors: the admin sees and edits it too
    assert [x["id"] for x in client.get(f"{API}/books", headers=school["adm"]).json()] == [b["id"]]
    r = client.put(f"{API}/books/{b['id']}", headers=school["adm"],
                   json={"title": "  English Grammar in Use ", "author": "", "language": "ru", "level": None})
    assert r.status_code == 200 and (r.json()["title"], r.json()["author"], r.json()["language"]) == (
        "English Grammar in Use", None, "ru")
    assert client.get(f"{API}/books/{b['id']}", headers=hm).json()["level"] is None

    # the PDF opens for editors only, through the existing file endpoint
    fid = b["file"]["id"]
    r = client.get(f"{API}/files/{fid}?inline=true", headers=hm)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-") and r.headers["content-disposition"].startswith("inline")
    assert client.get(f"{API}/files/{fid}", headers=school["adm"]).status_code == 200
    assert client.get(f"{API}/files/{fid}", headers=school["ha"]).status_code == 404
    assert client.get(f"{API}/files/{fid}", headers=school["h1"]).status_code == 404

    key = stored_key(b["id"])
    assert key in {k for k, _ in get_storage().list_keys()}
    assert client.delete(f"{API}/books/{b['id']}", headers=hm).status_code == 204
    assert key not in {k for k, _ in get_storage().list_keys()}
    assert client.get(f"{API}/books/{b['id']}", headers=hm).status_code == 404
    with SessionLocal() as db:
        assert db.query(Attachment).filter_by(book_id=b["id"]).count() == 0


def test_only_library_editors(client, school):
    b = upload(client, school["adm"]).json()
    for h in (school["ha"], school["h1"]):
        assert client.get(f"{API}/books", headers=h).status_code == 403
        assert upload(client, h).status_code == 403
        assert client.get(f"{API}/books/{b['id']}", headers=h).status_code == 403
        assert client.delete(f"{API}/books/{b['id']}", headers=h).status_code == 403
    assert client.get(f"{API}/books").status_code == 401
    assert client.get(f"{API}/books/999999", headers=school["adm"]).status_code == 404


def test_pdf_checks(client, school, monkeypatch):
    h = school["adm"]

    def detail(r):
        assert r.status_code == 400, r.text
        return r.json()["detail"]

    assert detail(upload(client, h, b"hello", name="notes.txt")) == "Загрузите файл PDF"
    assert detail(upload(client, h, b"\x89PNG\r\n\x1a\nxxxx", name="scan.pdf")) == "Файл повреждён или это не PDF"
    assert detail(upload(client, h, b"%PDF-1.7\nthis is not a real pdf", name="broken.pdf")) == "Файл повреждён или это не PDF"
    assert detail(upload(client, h, pdf(2, password="secret"))) == "PDF защищён паролем — загрузите файл без защиты"
    assert detail(upload(client, h, b"", name="empty.pdf")) == "Файл «empty.pdf» пустой"
    monkeypatch.setattr(settings, "BOOK_MAX_PAGES", 4)
    assert detail(upload(client, h, pdf(5))) == "В PDF больше 4 страниц"
    assert upload(client, h, pdf(4)).status_code == 201
    monkeypatch.setattr(settings, "BOOK_MAX_UPLOAD_MB", 0)
    assert detail(upload(client, h, pdf(1))) == "Файл «Grammar in Use.pdf» превышает 0 МБ"
    # translated for the request's language
    r = client.post(f"{API}/books", headers={**h, "Accept-Language": "en"}, data={"title": "x"},
                    files={"file": ("a.doc", b"x", "application/msword")})
    assert r.json()["detail"] == "Upload a PDF file"

    # form validation: title is required, language and level are checked
    assert upload(client, h, title="   ").status_code == 422
    assert upload(client, h, language="de").status_code == 422
    assert upload(client, h, level="Z9").status_code == 422
    # nothing was stored for the rejected uploads
    with SessionLocal() as db:
        assert db.query(Book).count() == 1


def test_sweep_keeps_book_files(client, school):
    b = upload(client, school["adm"]).json()
    key = stored_key(b["id"])
    old = time.time() - 3 * 86400
    os.utime(get_storage()._path(key), (old, old))
    with SessionLocal() as db:
        res = sweep_orphans(db, grace=timedelta(hours=24))
    assert key not in res.orphans and key in {k for k, _ in get_storage().list_keys()}

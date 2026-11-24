"""Book-to-Test, stage 3: page texts, outline and detected chapters, chapter editing."""
import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
from test_books import upload

from app.core.database import SessionLocal
from app.models import BookChapter
from app.models.enums import ChapterOrigin
from app.services.pdf_extract import PageResult, clean_text, detect_chapters
from app.worker import run_once

API = "/api/v1"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_pdf(pages: list[str], outline=(), image_pages=()) -> bytes:
    """A PDF with real text (Helvetica), optional bookmarks [(title, page_index, [children])]
    and pages that are only a picture (a scan)."""
    w = PdfWriter()
    font = w._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for i, txt in enumerate(pages):
        page = w.add_blank_page(width=600, height=800)
        ops = []
        if txt:
            ops = ["BT /F1 12 Tf 14 TL 50 750 Td"] + [f"({_esc(line)}) Tj T*" for line in txt.split("\n")] + ["ET"]
        res = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        if i in image_pages:
            img = DecodedStreamObject()
            img.set_data(b"\x80")
            img.update({
                NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(1), NameObject("/Height"): NumberObject(1),
                NameObject("/ColorSpace"): NameObject("/DeviceGray"), NameObject("/BitsPerComponent"): NumberObject(8),
            })
            res[NameObject("/XObject")] = DictionaryObject({NameObject("/Im1"): w._add_object(img)})
            ops.append("q 400 0 0 600 100 100 cm /Im1 Do Q")
        content = DecodedStreamObject()
        content.set_data("\n".join(ops).encode("latin-1"))
        page[NameObject("/Contents")] = w._add_object(content)
        page[NameObject("/Resources")] = res

    def add(items, parent=None):
        for title, idx, children in items:
            ref = w.add_outline_item(title, idx, parent=parent)
            add(children, ref)

    add(outline)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def process(client, h, data: bytes) -> dict:
    b = upload(client, h, data).json()
    assert run_once() == b["processing"]["id"]
    return client.get(f"{API}/books/{b['id']}", headers=h).json()


def chapters(client, h, book_id):
    return [(c["title"], c["start_page"], c["end_page"], c["depth"]) for c in
            client.get(f"{API}/books/{book_id}/chapters", headers=h).json()]


def test_text_and_chapters_from_the_outline(client, school):
    h = school["adm"]
    pages = [f"Unit {1 if i < 3 else 2}\nPage {i + 1} text about travel and family." for i in range(6)]
    data = text_pdf(pages, outline=[("Unit 1 Greetings", 0, [("1.1 Hello", 1, [])]), ("Unit 2 Travel", 3, [])])
    b = process(client, h, data)
    assert b["status"] == "ready" and b["has_outline"] is True and b["text_pages"] == 6 and b["ocr_pages"] == 0
    assert chapters(client, h, b["id"]) == [
        ("Unit 1 Greetings", 1, 3, 1), ("1.1 Hello", 2, 3, 2), ("Unit 2 Travel", 4, 6, 1)]
    with SessionLocal() as db:
        assert {c.origin for c in db.query(BookChapter).filter_by(book_id=b["id"])} == {ChapterOrigin.OUTLINE}

    p = client.get(f"{API}/books/{b['id']}/pages?from=2&to=3", headers=h).json()
    assert [x["page_number"] for x in p] == [2, 3]
    assert "Page 2 text about travel" in p[0]["text"] and p[0]["source"] == "text_layer" and p[0]["needs_ocr"] is False
    assert client.get(f"{API}/books/{b['id']}/pages?from=1&to=21", headers=h).status_code == 400
    assert client.get(f"{API}/books/{b['id']}/pages?from=5&to=4", headers=h).status_code == 400
    assert client.get(f"{API}/books/{b['id']}/pages", headers=school["ha"]).status_code == 403


def test_detected_chapters_and_scans(client, school):
    h = school["adm"]
    pages = [
        "Contents\nUnit 1 Family 2\nUnit 2 Food 4\nUnit 3 Sport 7",  # a contents page: no chapters from it
        "Unit 1\nFamily\nMy family is big.",
        "Unit 1 Family\nWe live in Almaty.",  # the running head repeats: not a new chapter
        "Unit 2 Food\nI like apples.",
        "",  # a scan: no text, only a picture
        "",  # an empty page: not a scan
    ]
    b = process(client, h, text_pdf(pages, image_pages={4}))
    assert b["has_outline"] is False and b["text_pages"] == 4 and b["ocr_pages"] == 1
    assert chapters(client, h, b["id"]) == [("Unit 1 Family", 2, 3, 1), ("Unit 2 Food", 4, 6, 1)]
    p = client.get(f"{API}/books/{b['id']}/pages?from=5&to=6", headers=h).json()
    assert [(x["needs_ocr"], x["source"], x["text"]) for x in p] == [(True, "none", ""), (False, "none", "")]


def test_chapter_editing_and_reprocessing_keeps_it(client, school):
    h = school["adm"]
    b = process(client, h, text_pdf([f"Unit {i}\nText {i}" for i in range(1, 11)]))
    bid = b["id"]
    detected = client.get(f"{API}/books/{bid}/chapters", headers=h).json()
    assert len(detected) == 10 and {c["origin"] for c in detected} == {"detected"}

    # a methodist reshapes it: one chapter 1-4 with a section 2-3, its own sub-section, another 5-10
    for c in detected:
        client.delete(f"{API}/books/chapters/{c['id']}", headers=h)
    r = client.post(f"{API}/books/{bid}/chapters", headers=h, json={"title": " Starter ", "start_page": 1, "end_page": 4})
    assert r.status_code == 201
    top = r.json()[0]
    sec = client.post(f"{API}/books/{bid}/chapters", headers=h,
                      json={"title": "Warm-up", "start_page": 2, "end_page": 3, "parent_id": top["id"]}).json()[1]
    sub = client.post(f"{API}/books/{bid}/chapters", headers=h,
                      json={"title": "Words", "start_page": 2, "end_page": 2, "parent_id": sec["id"]}).json()[2]
    client.post(f"{API}/books/{bid}/chapters", headers=h, json={"title": "Main", "start_page": 5, "end_page": 10})
    assert chapters(client, h, bid) == [("Starter", 1, 4, 1), ("Warm-up", 2, 3, 2), ("Words", 2, 2, 3), ("Main", 5, 10, 1)]
    out = client.get(f"{API}/books/{bid}/chapters", headers=h).json()
    assert out[0]["page_count"] == 4 and {c["origin"] for c in out} == {"manual"}

    def bad(r, text):
        assert r.status_code == 400 and r.json()["detail"] == text, r.text

    new = f"{API}/books/{bid}/chapters"
    bad(client.post(new, headers=h, json={"title": "X", "start_page": 9, "end_page": 11}),
        "Страницы главы — от 1 до 10, начальная не больше конечной")
    bad(client.post(new, headers=h, json={"title": "X", "start_page": 5, "end_page": 4}),
        "Страницы главы — от 1 до 10, начальная не больше конечной")
    bad(client.post(new, headers=h, json={"title": "X", "start_page": 3, "end_page": 6, "parent_id": top["id"]}),
        "Подраздел должен быть внутри страниц главы (1–4)")
    bad(client.post(new, headers=h, json={"title": "X", "start_page": 2, "end_page": 2, "parent_id": sub["id"]}),
        "Не больше трёх уровней вложенности")
    bad(client.patch(f"{API}/books/chapters/{top['id']}", headers=h, json={"parent_id": sub["id"]}),
        "Глава не может быть подразделом самой себя")
    bad(client.patch(f"{API}/books/chapters/{top['id']}", headers=h, json={"end_page": 2}),
        "Подразделы выходят за страницы главы")
    assert client.post(new, headers=h, json={"title": "", "start_page": 1, "end_page": 1}).status_code == 422
    assert client.post(new, headers=h, json={"title": "X", "start_page": 1, "end_page": 1, "parent_id": 999999}).status_code == 404

    r = client.patch(f"{API}/books/chapters/{sec['id']}", headers=h, json={"title": "Warm up", "end_page": 4})
    assert r.status_code == 200 and ("Warm up", 2, 4, 2) in [(c["title"], c["start_page"], c["end_page"], c["depth"]) for c in r.json()]

    # processing again refreshes the texts but keeps the methodist's chapters
    client.post(f"{API}/books/{bid}/reprocess", headers=h)
    run_once()
    assert chapters(client, h, bid) == [("Starter", 1, 4, 1), ("Warm up", 2, 4, 2), ("Words", 2, 2, 3), ("Main", 5, 10, 1)]

    # deleting a chapter takes its sections with it
    r = client.delete(f"{API}/books/chapters/{top['id']}", headers=h)
    assert [c["title"] for c in r.json()] == ["Main"]
    for hh in (school["ha"], school["h1"]):
        assert client.post(new, headers=hh, json={"title": "X", "start_page": 1, "end_page": 1}).status_code == 403
        assert client.delete(f"{API}/books/chapters/{out[-1]['id']}", headers=hh).status_code == 403
    assert client.patch(f"{API}/books/chapters/999999", headers=h, json={"title": "X"}).status_code == 404


def test_heading_rules_in_other_languages_and_text_cleanup():
    pages = [
        PageResult(1, "Предисловие", False),
        PageResult(2, "Глава 1\nСемья\nТекст.", False),
        PageResult(3, "Глава 1. Семья\nЕщё текст.", False),
        PageResult(4, "Урок 2: Еда\nТекст.", False),
        PageResult(5, "2-тарау Отбасы", False),  # not at a line start as "Тарау 2": not a heading
    ]
    found = [(c.title, c.start_page, c.end_page) for c in detect_chapters(pages, 5)]
    assert found == [("Глава 1 Семья", 2, 3), ("Урок 2: Еда", 4, 5)]
    assert clean_text("inter-\nnational trade\r\n\r\n\r\n\r\nNew-\nYork  \n") == "international trade\n\nNew-\nYork"


# ---------- stage 4: OCR through a pluggable engine ----------

def test_ocr_engine_reads_scans_when_enabled(client, school, monkeypatch):
    from app.core.config import settings
    from app.services import ocr_service

    calls = []

    class FakeEngine:
        name = "fake"

        def recognize(self, pdf_path, page_number, languages):
            calls.append((page_number, languages, pdf_path.endswith(".pdf")))
            if page_number == 3:
                raise RuntimeError("unreadable scan")
            return ocr_service.OcrResult(text=f"Recognized text of page {page_number}.", confidence=0.87)

    h = school["adm"]
    pages = ["Unit 1 Family\nText.", "", "", "Unit 2 Food\nText."]
    data = text_pdf(pages, image_pages={1, 2})

    # off by default: scans stay marked
    b = process(client, h, data)
    assert b["ocr_pages"] == 2 and calls == []

    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(settings, "OCR_ENGINE", "missing")
    client.post(f"{API}/books/{b['id']}/reprocess", headers=h)
    run_once()  # an engine that isn't installed: the book is still processed, scans stay marked
    assert client.get(f"{API}/books/{b['id']}", headers=h).json()["ocr_pages"] == 2

    monkeypatch.setitem(ocr_service.ENGINES, "fake", FakeEngine)
    monkeypatch.setattr(settings, "OCR_ENGINE", "fake")
    client.post(f"{API}/books/{b['id']}/reprocess", headers=h)
    run_once()
    d = client.get(f"{API}/books/{b['id']}", headers=h).json()
    assert d["status"] == "ready" and d["ocr_pages"] == 1 and d["text_pages"] == 3
    assert calls == [(2, "eng+rus+kaz", True), (3, "eng+rus+kaz", True)]  # only the scans
    p = client.get(f"{API}/books/{b['id']}/pages?from=1&to=4", headers=h).json()
    assert [(x["source"], x["needs_ocr"]) for x in p] == [
        ("text_layer", False), ("ocr", False), ("none", True), ("text_layer", False)]
    assert p[1]["text"] == "Recognized text of page 2."
    with SessionLocal() as db:
        from app.models import BookPage

        assert db.query(BookPage).filter_by(book_id=b["id"], page_number=2).one().ocr_confidence == 0.87

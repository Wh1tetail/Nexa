"""Book-to-Test OCR: the Tesseract engine without Tesseract (the binary is faked).

The page is really rendered by pypdfium2; only the `tesseract` call is replaced,
so the tests run anywhere. The Docker image (CI smoke test) carries the real one.
"""
import subprocess

import pytest
from test_pdf_extract import text_pdf

from app.core.config import settings
from app.services import ocr_service, ocr_tesseract
from app.services.ocr_tesseract import TesseractEngine, parse_tsv, write_pgm

HEAD = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def row(level, block, par, line, word, conf, text):
    return f"{level}\t1\t{block}\t{par}\t{line}\t{word}\t0\t0\t10\t10\t{conf}\t{text}"


def test_tsv_becomes_lines_and_paragraphs_with_mean_confidence():
    tsv = "\n".join([
        HEAD,
        row(1, 0, 0, 0, 0, -1, ""),
        row(5, 1, 1, 1, 1, 90, "Мама"), row(5, 1, 1, 1, 2, 80, "мыла"),
        row(5, 1, 1, 2, 1, 70, "раму."),
        row(5, 1, 2, 1, 1, 60, "Unit"), row(5, 1, 2, 1, 2, -1, " "),
        "broken\trow",
    ])
    res = parse_tsv(tsv)
    assert res.text == "Мама мыла\nраму.\n\nUnit"
    assert res.confidence == 0.75
    assert parse_tsv(HEAD) == ocr_service.OcrResult(text="", confidence=None)


def test_pgm_drops_the_bitmap_padding(tmp_path):
    p = tmp_path / "x.pgm"
    write_pgm(str(p), 2, 2, 4, bytes([1, 2, 0, 0, 3, 4, 0, 0]))
    assert p.read_bytes() == b"P5\n2 2\n255\n" + bytes([1, 2, 3, 4])


@pytest.fixture
def fake_binary(monkeypatch):
    calls = []

    def run(args, **kw):
        if args[1] == "--list-langs":
            return subprocess.CompletedProcess(args, 0, stdout="List of available languages (3):\neng\nrus\nosd\n")
        img = open(args[1], "rb").read()
        calls.append({"args": args, "header": img.split(b"\n")[:3], "size": len(img), "timeout": kw["timeout"]})
        return subprocess.CompletedProcess(args, 0, stdout="\n".join([HEAD, row(5, 1, 1, 1, 1, 91, "Hello")]))

    monkeypatch.setattr(ocr_tesseract.shutil, "which", lambda name: "/usr/bin/tesseract")
    monkeypatch.setattr(ocr_tesseract.subprocess, "run", run)
    return calls


def test_engine_renders_the_page_and_reads_it(tmp_path, fake_binary, monkeypatch):
    monkeypatch.setattr(ocr_tesseract.tempfile, "tempdir", str(tmp_path))
    warned = []
    monkeypatch.setattr(ocr_tesseract.log, "warning", lambda msg, *a: warned.append(msg % a))
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(text_pdf(["one", ""], image_pages=[1]))
    res = TesseractEngine().recognize(str(pdf), 2, "eng+rus+kaz")
    assert res.text == "Hello" and res.confidence == 0.91
    (call,) = fake_binary
    # 600x800 pt at 300 dpi, 8-bit grayscale; a missing language is dropped, not fatal
    assert call["header"] == [b"P5", b"2500 3334", b"255"] and call["size"] > 2500 * 3333
    assert call["args"][2:] == ["stdout", "-l", "eng+rus", "--dpi", "300", "tsv"]
    assert call["timeout"] == settings.OCR_PAGE_TIMEOUT_SECONDS
    assert warned and "kaz" in warned[0]
    assert not list(tmp_path.glob("*.pgm"))


def test_tesseract_is_registered_and_missing_binary_turns_ocr_off(monkeypatch):
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(settings, "OCR_ENGINE", "tesseract")
    monkeypatch.setattr(ocr_tesseract.shutil, "which", lambda name: None)
    assert "tesseract" in ocr_service.ENGINES
    assert ocr_service.get_ocr_engine() is None


def test_a_failing_run_leaves_the_page_to_the_caller(tmp_path, fake_binary, monkeypatch):
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(text_pdf([""], image_pages=[0]))
    engine = TesseractEngine()
    monkeypatch.setattr(ocr_tesseract.subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(args, 1, stdout=""))
    with pytest.raises(RuntimeError):
        engine.recognize(str(pdf), 1, "eng")

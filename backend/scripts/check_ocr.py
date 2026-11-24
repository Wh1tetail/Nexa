"""Check that OCR works on this machine: python -m scripts.check_ocr

Builds a one-page PDF with a known English sentence, asks the configured OCR
engine (OCR_ENABLED / OCR_ENGINE) to read it from the rendered image and
compares the words. Exit code 0 = OCR works; used by the CI Docker smoke test.
"""
import io
import os
import sys
import tempfile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.core.config import settings
from app.services.ocr_service import get_ocr_engine

SAMPLE = "The quick brown fox jumps over the lazy dog"


def sample_pdf() -> bytes:
    w = PdfWriter()
    font = w._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    page = w.add_blank_page(width=600, height=200)
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 24 Tf 40 100 Td ({SAMPLE}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = w._add_object(content)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def main() -> int:
    print(f"OCR_ENABLED={settings.OCR_ENABLED} OCR_ENGINE={settings.OCR_ENGINE!r} OCR_LANGUAGES={settings.OCR_LANGUAGES!r}")
    engine = get_ocr_engine()
    if engine is None:
        print("OCR is off or the engine could not start (see the log above)")
        return 1
    installed = getattr(engine, "installed", None)
    if installed is not None:
        print("installed languages:", " ".join(sorted(installed)))
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(sample_pdf())
        res = engine.recognize(path, 1, settings.OCR_LANGUAGES)
    finally:
        os.unlink(path)
    words = set(res.text.lower().split())
    found = [w for w in SAMPLE.lower().split() if w in words]
    print(f"recognized: {res.text!r} (confidence {res.confidence})")
    if len(found) < 7:
        print("OCR result does not match the sample")
        return 1
    print("OCR works")
    return 0


if __name__ == "__main__":
    sys.exit(main())

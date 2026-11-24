"""Book-to-Test, stage 4: OCR for scanned pages, separate from the PDF parser.

The parser (services/pdf_extract.py) marks pages that have a picture but almost
no text as `needs_ocr`. When OCR is switched on (OCR_ENABLED) and an engine is
registered under OCR_ENGINE, the extract job asks the engine for those pages'
text; otherwise they stay marked and the methodist sees them.

Shipped engine: "tesseract" (services/ocr_tesseract.py; its apt packages are in
backend/Dockerfile). Another engine is a class with `recognize()` and a
`register_engine("name", factory)` call, plus its system packages - nothing
else changes. A factory that raises (e.g. the binary is missing) only turns
OCR off for that job.

An engine renders the page itself (it gets the PDF's path and the page number),
so the parser never depends on a renderer.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None = None  # 0..1 when the engine reports it


class OcrEngine(Protocol):
    name: str

    def recognize(self, pdf_path: str, page_number: int, languages: str) -> OcrResult:
        """Text of one page (page_number from 1). Raise to leave the page marked."""
        ...


ENGINES: dict[str, Callable[[], OcrEngine]] = {}


def register_engine(name: str, factory: Callable[[], OcrEngine]) -> None:
    ENGINES[name] = factory


def get_ocr_engine() -> OcrEngine | None:
    """The configured engine, or None (OCR off, or the engine is not available)."""
    if not settings.OCR_ENABLED:
        return None
    factory = ENGINES.get(settings.OCR_ENGINE)
    if factory is None:
        log.warning("OCR is enabled but engine %r is not installed; scanned pages stay marked", settings.OCR_ENGINE)
        return None
    try:
        return factory()
    except Exception:  # a missing system package must not fail the book
        log.exception("OCR engine %r could not start; scanned pages stay marked", settings.OCR_ENGINE)
        return None


def _tesseract() -> OcrEngine:
    from app.services.ocr_tesseract import TesseractEngine

    return TesseractEngine()


register_engine("tesseract", _tesseract)

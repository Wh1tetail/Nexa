"""Book-to-Test: the Tesseract OCR engine (registered in services/ocr_service.py).

A scanned page is rendered by pypdfium2 into a grayscale PGM file (no Pillow
needed) and read by the `tesseract` command line tool (apt packages in
backend/Dockerfile). The TSV output gives the words with their confidence; the
text is rebuilt line by line. The page image lives only in a temporary file.
"""
from __future__ import annotations

import importlib
import logging
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict

from app.core.config import settings
from app.services.ocr_service import OcrResult

log = logging.getLogger(__name__)

DPI = 300
MAX_SIDE_PX = 5000  # a poster-sized page is scaled down rather than rendered huge


def available_languages(binary: str) -> set[str]:
    out = subprocess.run([binary, "--list-langs"], capture_output=True, text=True, timeout=30, check=True)
    # the first line is a header ("List of available languages ...")
    return {x.strip() for x in out.stdout.splitlines()[1:] if x.strip()}


def write_pgm(path: str, width: int, height: int, stride: int, buffer: bytes) -> None:
    """A binary 8-bit grayscale PGM; rows are copied without the bitmap's padding."""
    with open(path, "wb") as f:
        f.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
        if stride == width:
            f.write(buffer[: width * height])
        else:
            for y in range(height):
                f.write(buffer[y * stride: y * stride + width])


def parse_tsv(tsv: str) -> OcrResult:
    """Words of `tesseract ... tsv` back into lines and paragraphs, mean word confidence 0..1."""
    lines: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    confs: list[float] = []
    rows = tsv.splitlines()
    for row in rows[1:]:  # header row
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        word = cols[11].strip()
        if not word:
            continue
        try:
            key = (int(cols[2]), int(cols[3]), int(cols[4]))  # block, paragraph, line
            conf = float(cols[10])
        except ValueError:
            continue
        lines[key].append(word)
        if conf >= 0:
            confs.append(conf)
    out: list[str] = []
    prev: tuple[int, int] | None = None
    for key in sorted(lines):
        if prev is not None and key[:2] != prev:
            out.append("")  # a blank line between paragraphs
        out.append(" ".join(lines[key]))
        prev = key[:2]
    confidence = round(sum(confs) / len(confs) / 100, 3) if confs else None
    return OcrResult(text="\n".join(out), confidence=confidence)


class TesseractEngine:
    name = "tesseract"

    def __init__(self) -> None:
        binary = shutil.which("tesseract")
        if binary is None:
            raise RuntimeError("tesseract is not installed")
        importlib.import_module("pypdfium2")  # fail at start, not on the first page
        self.binary = binary
        self.installed = available_languages(binary)

    def _languages(self, wanted: str) -> str:
        langs = [x for x in wanted.split("+") if x]
        ok = [x for x in langs if x in self.installed]
        missing = [x for x in langs if x not in self.installed]
        if missing:
            log.warning("Tesseract has no data for %s; using %s", "+".join(missing), "+".join(ok) or "eng")
        return "+".join(ok) or "eng"

    def recognize(self, pdf_path: str, page_number: int, languages: str) -> OcrResult:
        import pypdfium2 as pdfium
        import pypdfium2.raw as pdfium_c

        fd, img_path = tempfile.mkstemp(suffix=".pgm", prefix="nexa-ocr-")
        os.close(fd)
        try:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                page = doc[page_number - 1]
                w, h = page.get_size()  # points (1/72 inch)
                scale = min(DPI / 72, MAX_SIDE_PX / max(w, h, 1))
                bitmap = page.render(scale=scale, grayscale=True, force_bitmap_format=pdfium_c.FPDFBitmap_Gray)
                write_pgm(img_path, bitmap.width, bitmap.height, bitmap.stride, bytes(bitmap.buffer))
                bitmap.close()
                page.close()
            finally:
                doc.close()
            done = subprocess.run(
                [self.binary, img_path, "stdout", "-l", self._languages(languages), "--dpi", str(DPI), "tsv"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=settings.OCR_PAGE_TIMEOUT_SECONDS,
            )
            if done.returncode != 0:
                raise RuntimeError(f"tesseract exited with {done.returncode}")
            return parse_tsv(done.stdout)
        finally:
            try:
                os.unlink(img_path)
            except OSError:
                pass

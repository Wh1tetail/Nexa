"""Book-to-Test, stage 3: reading a PDF's text and structure (pypdf, no system packages).

Pure functions over an open `pypdf.PdfReader`; the worker's `extract` job
(services/book_processing.py) stores the result. Nothing here logs page text.

- `read_page`: the page's text layer, cleaned; a page with almost no text and a
  picture on it is marked as a scan that needs OCR (stage 4 recognizes it).
- `outline_chapters`: chapters and subsections from the PDF's own table of
  contents (bookmarks), with page ranges.
- `detect_chapters`: when there is no outline, headings such as "Unit 3",
  "Chapter 4", "Глава 2", "Урок 5" at the top of a page start a chapter. Running
  heads that repeat on every page of a chapter and contents pages listing many
  units are ignored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MAX_PAGE_CHARS = 20_000
MAX_TITLE = 300
MAX_DEPTH = 3  # chapter > section > subsection

HEADING = re.compile(
    r"^\s*(chapter|unit|lesson|module|part|section|глава|урок|раздел|модуль|часть|тарау|сабақ|бөлім)"
    r"\s+(\d{1,3}|[ivxlcdm]{1,7})\b[\s.:\-–—]*(.*)$",
    re.IGNORECASE,
)
TOP_LINES = 5  # a heading must be among the first lines of a page
CONTENTS_PAGE = 3  # this many headings on one page: it is a table of contents


@dataclass
class PageResult:
    number: int
    text: str
    needs_ocr: bool
    source: str = "text_layer"  # "text_layer" / "ocr" / "none" (PageTextSource values)
    confidence: float | None = None  # OCR only

    def __post_init__(self) -> None:
        if not self.text and self.source == "text_layer":
            self.source = "none"


@dataclass
class ChapterDraft:
    title: str
    start_page: int
    end_page: int = 0
    children: list[ChapterDraft] = field(default_factory=list)


# ---------- pages ----------

def clean_text(raw: str) -> str:
    t = (raw or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    t = re.sub(r"(\w)-\n(\w)", lambda m: m.group(1) + m.group(2) if m.group(2).islower() else m.group(0), t)
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:MAX_PAGE_CHARS]


def page_has_image(page: Any) -> bool:
    try:
        resources = page.get("/Resources")
        resources = resources.get_object() if resources is not None else {}
        xobjects = resources.get("/XObject")
        if xobjects is None:
            return False
        for ref in xobjects.get_object().values():
            if ref.get_object().get("/Subtype") == "/Image":
                return True
    except Exception:  # an odd resource dictionary is not a reason to fail the book
        return False
    return False


def read_page(page: Any, number: int, min_chars: int) -> PageResult:
    try:
        text = clean_text(page.extract_text() or "")
    except Exception:  # one unreadable page does not fail the book
        text = ""
    letters = len(re.sub(r"\s", "", text))
    return PageResult(number=number, text=text, needs_ocr=letters < min_chars and page_has_image(page))


# ---------- chapters from the outline ----------

def _set_ends(nodes: list[ChapterDraft], last_page: int) -> None:
    nodes.sort(key=lambda n: n.start_page)
    for i, n in enumerate(nodes):
        nxt = nodes[i + 1].start_page if i + 1 < len(nodes) else last_page + 1
        n.end_page = max(n.start_page, min(last_page, nxt - 1))
        n.children = [c for c in n.children if n.start_page <= c.start_page <= n.end_page]
        _set_ends(n.children, n.end_page)


def outline_chapters(reader: Any, total: int) -> list[ChapterDraft]:
    """Chapters from the PDF bookmarks; [] when there are none."""
    try:
        outline = reader.outline
    except Exception:
        return []

    def walk(items: list, depth: int) -> list[ChapterDraft]:
        out: list[ChapterDraft] = []
        for item in items:
            if isinstance(item, list):  # the children of the previous item
                if out and depth < MAX_DEPTH:
                    out[-1].children.extend(walk(item, depth + 1))
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
                title = str(item.title or "").strip()[:MAX_TITLE]
            except Exception:
                continue
            if title and 1 <= page <= total:
                out.append(ChapterDraft(title=title, start_page=page))
        return out

    chapters = walk(outline or [], 1)
    _set_ends(chapters, total)
    return chapters


# ---------- chapters from headings ----------

def _heading(lines: list[str]) -> tuple[str, str] | None:
    """(key, title) of a chapter heading among the first lines, e.g. ("unit 3", "Unit 3 Travel")."""
    for i, line in enumerate(lines[:TOP_LINES]):
        m = HEADING.match(line)
        if not m:
            continue
        key = f"{m.group(1).lower()} {m.group(2).lower()}"
        title = line.strip()
        rest = m.group(3).strip()
        if not rest and i + 1 < len(lines):  # "Unit 3" on its own line, the name on the next
            nxt = lines[i + 1].strip()
            if nxt and len(nxt) <= 80 and not HEADING.match(nxt):
                title = f"{title} {nxt}"
        return key, re.sub(r"\s+", " ", title)[:MAX_TITLE]
    return None


def detect_chapters(pages: list[PageResult], total: int) -> list[ChapterDraft]:
    chapters: list[ChapterDraft] = []
    seen: set[str] = set()
    for p in pages:
        lines = [ln.strip() for ln in p.text.split("\n") if ln.strip()]
        if sum(1 for ln in lines if HEADING.match(ln)) >= CONTENTS_PAGE:
            continue  # a contents page
        found = _heading(lines)
        if found is None or found[0] in seen:  # a running head repeats the chapter's heading
            continue
        seen.add(found[0])
        chapters.append(ChapterDraft(title=found[1], start_page=p.number))
    _set_ends(chapters, total)
    return chapters

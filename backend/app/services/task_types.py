"""Fill in the Gaps, Matching and content blocks (Audio, Reading) in tests.

Settings live in TestQuestion.config. Students see a public version (no
answers) until the test is graded and the teacher allows showing answers.

Fill in the Gaps template: text with gaps in braces.
    "Tom usually {goes} to school. He {likes|loves::like} English."
    {a|b}      accepted answers (any of them)
    {a::hint}  a hint shown at the gap
Answers are a list aligned with the gaps; Matching answers a list aligned
with the pairs (the chosen right-hand text).
"""
import random
import re
from typing import Any

from app.models.enums import CONTENT_TYPES, QuestionType

GAP = re.compile(r"\{([^{}]+)\}")
MAX_GAPS = 50
MAX_PAIRS = 20
MAX_BANK = 30
FILL_MODES = ("input", "dropdown", "drag")


class TaskError(ValueError):
    """A template/config the teacher has to fix (message is a translatable template)."""


# ---------- validation (teacher input -> stored config) ----------

def parse_template(template: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Text segments around the gaps and the gaps (answers, hint)."""
    segments, gaps, pos = [], [], 0
    for m in GAP.finditer(template):
        segments.append(template[pos:m.start()])
        body, _, hint = m.group(1).partition("::")
        answers = [a.strip() for a in body.split("|") if a.strip()]
        if not answers:
            raise TaskError("У каждого пропуска должен быть правильный ответ")
        gaps.append({"answers": answers, "hint": hint.strip() or None})
        pos = m.end()
    segments.append(template[pos:])
    return segments, gaps


def _words(values: Any, limit: int) -> list[str]:
    out = []
    for v in values or []:
        v = str(v).strip()[:200]
        if v and v not in out:
            out.append(v)
    return out[:limit]


def normalize_config(qtype: QuestionType, config: dict[str, Any]) -> tuple[dict[str, Any], int | None]:
    """Validated config for storage and, when the type fixes it, the points."""
    if qtype == QuestionType.FILL_GAPS:
        template = str(config.get("template") or "")
        if len(template) > 20000:
            raise TaskError("Текст задания слишком длинный")
        _, gaps = parse_template(template)
        if not gaps:
            raise TaskError("Отметьте пропуски: заключите правильный ответ в фигурные скобки")
        if len(gaps) > MAX_GAPS:
            raise TaskError("Не более 50 пропусков в задании")
        points = list(config.get("gap_points") or [])
        for i, gap in enumerate(gaps):
            p = points[i] if i < len(points) else 1
            if not isinstance(p, int) or not 1 <= p <= 20:
                raise TaskError("Баллы за пропуск — от 1 до 20")
            gap["points"] = p
        mode = config.get("mode") or "input"
        if mode not in FILL_MODES:
            raise TaskError("Неизвестный режим ответа")
        stored = {
            "template": template,
            "gaps": gaps,
            "mode": mode,
            "case_sensitive": bool(config.get("case_sensitive")),
            "distractors": _words(config.get("distractors"), MAX_BANK),
        }
        return stored, sum(g["points"] for g in gaps)

    if qtype == QuestionType.MATCHING:
        pairs = []
        for p in config.get("pairs") or []:
            left, right = str(p.get("left") or "").strip()[:300], str(p.get("right") or "").strip()[:300]
            if left and right:
                pairs.append({"left": left, "right": right})
        if not 2 <= len(pairs) <= MAX_PAIRS:
            raise TaskError("Добавьте от 2 до 20 пар")
        if len({p["right"] for p in pairs}) != len(pairs):
            raise TaskError("Правые части пар должны различаться")
        return {"pairs": pairs, "distractors": _words(config.get("distractors"), MAX_BANK)}, None

    if qtype == QuestionType.AUDIO:
        file_id = config.get("attachment_id")
        if not isinstance(file_id, int):
            raise TaskError("Выберите аудиофайл")
        plays = config.get("max_plays")
        if plays is not None and (not isinstance(plays, int) or not 1 <= plays <= 10):
            raise TaskError("Количество прослушиваний — от 1 до 10")
        return {
            "attachment_id": file_id,
            "max_plays": plays,
            "body": str(config.get("body") or "").strip()[:5000] or None,
        }, 0

    if qtype == QuestionType.READING:
        body = str(config.get("body") or "").strip()
        if not body:
            raise TaskError("Добавьте текст для чтения")
        if len(body) > 30000:
            raise TaskError("Текст для чтения слишком длинный")
        image = config.get("image_id")
        if image is not None and not isinstance(image, int):
            raise TaskError("Выберите изображение из материалов теста")
        return {"body": body, "image_id": image}, 0

    return {}, None


def file_ids(qtype: QuestionType, config: dict[str, Any]) -> list[int]:
    """Test files a config refers to (they must belong to the test)."""
    if qtype == QuestionType.AUDIO:
        return [config["attachment_id"]]
    if qtype == QuestionType.READING and config.get("image_id"):
        return [config["image_id"]]
    return []


# ---------- answers and scoring ----------

def _norm(s: str, case_sensitive: bool) -> str:
    s = " ".join(str(s).replace("’", "'").split())
    return s if case_sensitive else s.lower()


def clean_answer(qtype: QuestionType, config: dict[str, Any], value: list[str]) -> list[str]:
    """Keep one string per gap / pair (empty = not answered)."""
    n = len(config["gaps"]) if qtype == QuestionType.FILL_GAPS else len(config["pairs"])
    value = [str(v)[:200] for v in value[:n]]
    return value + [""] * (n - len(value))


def grade(qtype: QuestionType, config: dict[str, Any], points: int, answer: list[str]) -> tuple[bool, float]:
    if qtype == QuestionType.FILL_GAPS:
        cs = config.get("case_sensitive", False)
        got, all_ok = 0.0, True
        for i, gap in enumerate(config["gaps"]):
            given = _norm(answer[i], cs) if i < len(answer) else ""
            ok = bool(given) and given in {_norm(a, cs) for a in gap["answers"]}
            got += gap["points"] if ok else 0
            all_ok &= ok
        return all_ok, float(got)
    # matching: partial credit per pair
    pairs = config["pairs"]
    right = sum(1 for i, p in enumerate(pairs) if i < len(answer) and answer[i] == p["right"])
    return right == len(pairs), round(points * right / len(pairs), 2)


def gap_results(config: dict[str, Any], answer: list[str]) -> list[bool]:
    cs = config.get("case_sensitive", False)
    return [
        bool(answer[i:i + 1] and _norm(answer[i], cs) in {_norm(a, cs) for a in g["answers"]})
        for i, g in enumerate(config["gaps"])
    ]


# ---------- what the student sees ----------

def public_config(qtype: QuestionType, config: dict[str, Any], reveal: bool, seed: str) -> dict[str, Any]:
    """Config without answers; word banks and right-hand lists are shuffled with
    a stable seed (the order never shows the answer and never changes on reload)."""
    rng = random.Random(seed)
    if qtype == QuestionType.FILL_GAPS:
        segments, _ = parse_template(config["template"])
        out: dict[str, Any] = {
            "segments": segments,
            "gaps": [{"hint": g["hint"], "points": g["points"]} for g in config["gaps"]],
            "mode": config["mode"],
            "case_sensitive": config.get("case_sensitive", False),
        }
        if config["mode"] != "input":
            bank = list(dict.fromkeys([g["answers"][0] for g in config["gaps"]] + config.get("distractors", [])))
            rng.shuffle(bank)
            out["bank"] = bank
        if reveal:
            out["answers"] = [g["answers"] for g in config["gaps"]]
            out["template"] = config["template"]
            out["distractors"] = config.get("distractors", [])
        return out
    if qtype == QuestionType.MATCHING:
        rights = [p["right"] for p in config["pairs"]] + config.get("distractors", [])
        rng.shuffle(rights)
        out = {"lefts": [p["left"] for p in config["pairs"]], "rights": rights}
        if reveal:
            out["answers"] = [p["right"] for p in config["pairs"]]
            out["pairs"] = config["pairs"]
            out["distractors"] = config.get("distractors", [])
        return out
    if qtype in CONTENT_TYPES:
        return dict(config)
    return {}

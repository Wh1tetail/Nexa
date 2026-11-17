"""Lesson blocks of courses: validation, the student view and checking exercises.

`LessonBlock.content` holds the block's settings; exercise blocks also keep
`content["questions"]`: questions in the test question format (QuestionIn), so
grading and the answer views are shared with tests.

    text            {body}                                 Markdown-like text
    grammar         {body, examples: [str]}
    vocabulary      {words: [{word, translation, transcription, example}]}
    image           {attachment_id, caption}
    audio           {attachment_id, body, transcript}
    video           {provider: youtube|vimeo, video_id} or {attachment_id}; caption
    reading         {body, image_id} + questions
    listening       {attachment_id, max_plays, body, transcript} + questions
    quiz            {body} + questions (any kind)
    fill_gaps       exactly one fill_gaps question
    multiple_choice exactly one single/multiple choice or True/False question
    matching        exactly one matching question

Files are the lesson's materials (`Attachment.course_lesson_id`).
"""
import re
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.models.enums import LessonBlockType as B
from app.models.enums import QuestionType as Q
from app.schemas.test import QuestionOut
from app.services import test_service
from app.services.task_types import TaskError

MAX_QUESTIONS = 30
MAX_WORDS = 200
SCORED = {Q.SINGLE_CHOICE, Q.MULTIPLE_CHOICE, Q.TRUE_FALSE, Q.SHORT_ANSWER, Q.FILL_GAPS, Q.MATCHING}
# blocks made of exactly one question of these kinds
SINGLE: dict[B, set[Q]] = {
    B.FILL_GAPS: {Q.FILL_GAPS},
    B.MULTIPLE_CHOICE: {Q.SINGLE_CHOICE, Q.MULTIPLE_CHOICE, Q.TRUE_FALSE},
    B.MATCHING: {Q.MATCHING},
}
MANY = {B.READING, B.LISTENING, B.QUIZ}
EXERCISES = MANY | set(SINGLE)

YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _text(value: Any, limit: int) -> str | None:
    s = str(value or "").strip()
    if len(s) > limit:
        raise TaskError("Текст блока слишком длинный")
    return s or None


def _file_id(value: Any, required: bool, message: str) -> int | None:
    if value is None or value == "":
        if required:
            raise TaskError(message)
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TaskError(message)
    return value


def parse_video_url(url: str) -> dict[str, str]:
    """YouTube / Vimeo link -> {provider, video_id}; nothing else can be embedded."""
    u = urlparse(url.strip())
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if u.scheme not in ("http", "https"):
        raise TaskError("Вставьте ссылку на видео YouTube или Vimeo")
    vid = None
    if host in ("youtube.com", "youtube-nocookie.com", "music.youtube.com"):
        parts = [p for p in u.path.split("/") if p]
        if parts[:1] == ["watch"]:
            vid = (parse_qs(u.query).get("v") or [None])[0]
        elif len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
            vid = parts[1]
    elif host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    if vid is not None:
        if not YOUTUBE_ID.match(vid):
            raise TaskError("Вставьте ссылку на видео YouTube или Vimeo")
        return {"provider": "youtube", "video_id": vid}
    if host in ("vimeo.com", "player.vimeo.com"):
        m = re.search(r"/(?:video/)?(\d{1,12})(?:/|$)", u.path)
        if m:
            return {"provider": "vimeo", "video_id": m.group(1)}
    raise TaskError("Вставьте ссылку на видео YouTube или Vimeo")


def normalize(btype: B, content: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Validated content for storage. `questions` are already valid QuestionIn dumps."""
    c = content or {}
    if btype in EXERCISES:
        if btype in SINGLE:
            if len(questions) != 1 or Q(questions[0]["type"]) not in SINGLE[btype]:
                raise TaskError("Неверный тип задания для этого блока")
        else:
            if not questions:
                raise TaskError("Добавьте хотя бы один вопрос")
            if len(questions) > MAX_QUESTIONS:
                raise TaskError("Не более {n} вопросов в блоке", n=MAX_QUESTIONS)
            if any(Q(q["type"]) not in SCORED for q in questions):
                raise TaskError("Неверный тип задания для этого блока")
    elif questions:
        raise TaskError("В этом блоке не бывает вопросов")

    if btype in (B.TEXT, B.GRAMMAR):
        body = _text(c.get("body"), 30000)
        if not body:
            raise TaskError("Добавьте текст")
        out: dict[str, Any] = {"body": body}
        if btype == B.GRAMMAR:
            examples = [e for e in (_text(x, 500) for x in (c.get("examples") or [])[:30]) if e]
            out["examples"] = examples
        return out
    if btype == B.VOCABULARY:
        words = []
        for w in (c.get("words") or [])[:MAX_WORDS + 1]:
            if not isinstance(w, dict):
                continue
            word = _text(w.get("word"), 200)
            if not word:
                continue
            words.append({
                "word": word,
                "translation": _text(w.get("translation"), 300),
                "transcription": _text(w.get("transcription"), 100),
                "example": _text(w.get("example"), 500),
            })
        if not words:
            raise TaskError("Добавьте хотя бы одно слово")
        if len(words) > MAX_WORDS:
            raise TaskError("Не более {n} слов в словаре", n=MAX_WORDS)
        return {"words": words}
    if btype == B.IMAGE:
        return {
            "attachment_id": _file_id(c.get("attachment_id"), True, "Выберите изображение из материалов урока"),
            "caption": _text(c.get("caption"), 500),
        }
    if btype == B.AUDIO:
        return {
            "attachment_id": _file_id(c.get("attachment_id"), True, "Выберите аудиофайл"),
            "body": _text(c.get("body"), 5000),
            "transcript": _text(c.get("transcript"), 20000),
        }
    if btype == B.VIDEO:
        caption = _text(c.get("caption"), 500)
        if "attachment_id" in c and not c.get("url"):  # the file option was chosen
            file_id = _file_id(c.get("attachment_id"), True, "Выберите видеофайл из материалов урока")
            return {"attachment_id": file_id, "caption": caption}
        url = str(c.get("url") or "").strip()
        if url:
            return {**parse_video_url(url), "caption": caption}
        provider, vid = c.get("provider"), str(c.get("video_id") or "")
        if provider == "youtube" and YOUTUBE_ID.match(vid):
            return {"provider": provider, "video_id": vid, "caption": caption}
        if provider == "vimeo" and vid.isdigit() and len(vid) <= 12:
            return {"provider": provider, "video_id": vid, "caption": caption}
        raise TaskError("Вставьте ссылку на видео YouTube или Vimeo")
    if btype == B.READING:
        body = _text(c.get("body"), 30000)
        if not body:
            raise TaskError("Добавьте текст для чтения")
        return {
            "body": body,
            "image_id": _file_id(c.get("image_id"), False, "Выберите изображение из материалов урока"),
            "questions": questions,
        }
    if btype == B.LISTENING:
        plays = c.get("max_plays")
        if plays is not None and (not isinstance(plays, int) or not 1 <= plays <= 10):
            raise TaskError("Количество прослушиваний — от 1 до 10")
        return {
            "attachment_id": _file_id(c.get("attachment_id"), True, "Выберите аудиофайл"),
            "max_plays": plays,
            "body": _text(c.get("body"), 5000),
            "transcript": _text(c.get("transcript"), 20000),
            "questions": questions,
        }
    # quiz and single exercises
    return {"body": _text(c.get("body"), 5000), "questions": questions}


def file_ids(btype: B, content: dict[str, Any]) -> list[tuple[int, str]]:
    """Lesson files a block refers to, with the kind they must be (image/audio/video/any)."""
    out: list[tuple[int, str]] = []
    kind = {B.IMAGE: "image", B.AUDIO: "audio", B.LISTENING: "audio", B.VIDEO: "video"}.get(btype)
    if kind and content.get("attachment_id"):
        out.append((content["attachment_id"], kind))
    if content.get("image_id"):
        out.append((content["image_id"], "image"))
    for q in content.get("questions") or []:
        out.extend((i, "any") for i in q.get("attachment_ids") or [])
    return out


def remap_files(content: dict[str, Any], id_map: dict[int, int]) -> dict[str, Any]:
    """Content of a copied block pointing at the copied files."""
    c = dict(content)
    for k in ("attachment_id", "image_id"):
        if c.get(k) in id_map:
            c[k] = id_map[c[k]]
    if "questions" in c:
        c["questions"] = [
            {**q, "attachment_ids": [id_map[i] for i in q.get("attachment_ids") or [] if i in id_map]}
            for q in c["questions"]
        ]
    return c


def drop_file(content: dict[str, Any], file_id: int) -> dict[str, Any]:
    """Content without references to a deleted file (a block whose main file it
    was keeps an empty reference and shows a placeholder)."""
    c = dict(content)
    for k in ("attachment_id", "image_id"):
        if c.get(k) == file_id:
            c[k] = None
    if "questions" in c:
        c["questions"] = [
            {**q, "attachment_ids": [i for i in q.get("attachment_ids") or [] if i != file_id]}
            for q in c["questions"]
        ]
    return c


# ---------- student view and checking ----------

def _q(block_id: int, i: int, raw: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=i, position=i, type=Q(raw["type"]), text=raw["text"], options=raw.get("options") or [],
        correct_answer=raw.get("correct_answer") or [], points=raw.get("points", 1),
        explanation=raw.get("explanation"), attachment_ids=raw.get("attachment_ids") or [],
        config=raw.get("config") or {}, seed=f"lb{block_id}-{i}",
    )


def view_questions(block_id: int, content: dict[str, Any], reveal: bool) -> list[QuestionOut]:
    """Questions as students see them (answers only when revealed); ids are the
    question's index in the block."""
    out = []
    for i, raw in enumerate(content.get("questions") or []):
        q = _q(block_id, i, raw)
        out.append(test_service.question_out(q, reveal, seed=q.seed))  # type: ignore[arg-type]
    return out


def public_content(content: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in content.items() if k != "questions"}


def check(block_id: int, content: dict[str, Any], answers: dict[int, list[str]]) -> list[dict[str, Any]]:
    """Grade the answers to a block's questions. Short answers are checked against
    the accepted answers only (no teacher review in lessons)."""
    results = []
    for i, raw in enumerate(content.get("questions") or []):
        q = _q(block_id, i, raw)
        value = test_service.clean_value(q, [str(v) for v in answers.get(i, [])][:60])
        ok, points = test_service.auto_grade(q, value)
        results.append({
            "question_id": i,
            "answer": value,
            "is_correct": bool(ok),
            "points_awarded": float(points or 0),
            "max_points": q.points,
        })
    return results

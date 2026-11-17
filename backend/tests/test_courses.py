"""Stage 17: courses / programmes and the lesson builder."""
import pytest
from conftest import login, make_user

from app.core.database import SessionLocal
from app.models import Attachment, CourseLesson
from app.models.enums import UserRole
from app.services.lesson_blocks import parse_video_url
from app.services.task_types import TaskError

API = "/api/v1"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x0f" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64

CHOICE = {"type": "single_choice", "text": "She ___ to school.", "points": 1, "correct_answer": ["a"],
          "options": [{"id": "a", "text": "goes"}, {"id": "b", "text": "go"}], "explanation": "He/she/it + -s"}
GAPS = {"type": "fill_gaps", "text": "Complete the text", "config": {"template": "I {am} from {Spain|Kazakhstan}."}}
MATCH = {"type": "matching", "text": "Match", "config": {"pairs": [{"left": "cat", "right": "кошка"},
                                                                   {"left": "dog", "right": "собака"}]}}
SHORT = {"type": "short_answer", "text": "Past of go?", "points": 2, "correct_answer": ["went"]}


@pytest.fixture
def ed(client, school):
    make_user(UserRole.METHODIST, "method@test.io", name="Mila Methodist")
    return {**school, "hm": login(client, "method@test.io")}


def _course(client, h, **fields):
    r = client.post(f"{API}/courses", headers=h, json={"title": "General English", "levels": ["A2", "A1"], **fields})
    assert r.status_code == 201, r.text
    return r.json()


def _module(client, h, level_id, title="Introduction"):
    r = client.post(f"{API}/courses/levels/{level_id}/modules", headers=h, json={"title": title})
    assert r.status_code == 201, r.text
    return next(m for lv in r.json()["levels"] for m in lv["modules"] if m["title"] == title)


def _lesson(client, h, module_id, title="Greetings"):
    r = client.post(f"{API}/courses/modules/{module_id}/lessons", headers=h, json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, h, lesson_id, files):
    r = client.post(f"{API}/courses/lessons/{lesson_id}/files", headers=h,
                    files=[("files", (n, d, m)) for n, d, m in files])
    assert r.status_code == 201, r.text
    return {f["original_name"]: f["id"] for f in r.json()}


def _save(client, h, lesson_id, blocks, **fields):
    body = {"title": "Greetings", "blocks": blocks, **fields}
    return client.put(f"{API}/courses/lessons/{lesson_id}", headers=h, json=body)


def test_structure_order_and_visibility(client, ed):
    hm, ha = ed["hm"], ed["ha"]
    c = _course(client, hm)
    assert [lv["level"] for lv in c["levels"]] == ["A1", "A2"] and c["levels"][0]["title"] == "A1 Beginner"
    assert c["author_name"] == "Mila Methodist" and c["published"] is False
    a1 = c["levels"][0]["id"]
    m1 = _module(client, hm, a1, "Introduction")
    m2 = _module(client, hm, a1, "Daily Life")
    l1 = _lesson(client, hm, m1["id"], "Greetings")
    l2 = _lesson(client, hm, m1["id"], "Introducing Yourself")
    assert l1["published"] is False and l1["path"]["module_title"] == "Introduction"
    # a level appears once per course
    r = client.post(f"{API}/courses/{c['id']}/levels", headers=hm, json={"level": "A1"})
    assert r.status_code == 400 and r.json()["detail"] == "Этот уровень уже есть в курсе"

    # reorder and move
    r = client.patch(f"{API}/courses/lessons/{l2['id']}", headers=hm, json={"position": 0})
    mods = r.json()["levels"][0]["modules"]
    assert [x["title"] for x in mods[0]["lessons"]] == ["Introducing Yourself", "Greetings"]
    r = client.patch(f"{API}/courses/modules/{m2['id']}", headers=hm, json={"position": 0})
    assert [x["title"] for x in r.json()["levels"][0]["modules"]] == ["Daily Life", "Introduction"]
    r = client.patch(f"{API}/courses/lessons/{l1['id']}", headers=hm, json={"module_id": m2["id"]})
    mods = {m["title"]: m for m in r.json()["levels"][0]["modules"]}
    assert [x["title"] for x in mods["Daily Life"]["lessons"]] == ["Greetings"]
    assert [x["position"] for x in mods["Introduction"]["lessons"]] == [0]

    # an empty lesson can't be published
    r = client.patch(f"{API}/courses/lessons/{l1['id']}", headers=hm, json={"published": True})
    assert r.status_code == 400

    # teachers: nothing until the course is published, then published lessons only
    assert client.get(f"{API}/courses", headers=ha).json() == []
    assert client.get(f"{API}/courses/{c['id']}", headers=ha).status_code == 404
    client.put(f"{API}/courses/{c['id']}", headers=hm, json={"title": "General English", "published": True})
    assert _save(client, hm, l1["id"], [{"type": "text", "content": {"body": "Hello!"}}], published=True).status_code == 200
    items = client.get(f"{API}/courses", headers=ha).json()
    assert len(items) == 1 and items[0]["lessons_count"] == 1 and items[0]["draft_lessons_count"] == 0
    tree = client.get(f"{API}/courses/{c['id']}", headers=ha).json()
    a1_t = tree["levels"][0]
    assert [m["title"] for m in a1_t["modules"]] == ["Daily Life"]  # Introduction has drafts only
    assert client.get(f"{API}/courses/lessons/{l2['id']}/view", headers=ha).status_code == 404
    assert client.get(f"{API}/courses/lessons/{l1['id']}/view", headers=ha).status_code == 200
    editor_items = client.get(f"{API}/courses", headers=hm).json()
    assert editor_items[0]["lessons_count"] == 2 and editor_items[0]["draft_lessons_count"] == 1

    # only methodists and admins edit; students see nothing here
    assert client.post(f"{API}/courses", headers=ha, json={"title": "Mine"}).status_code == 403
    assert client.get(f"{API}/courses/lessons/{l1['id']}", headers=ha).status_code == 403  # the editable form
    assert client.patch(f"{API}/courses/lessons/{l1['id']}", headers=ha, json={"title": "x"}).status_code == 403
    assert client.get(f"{API}/courses", headers=ed["h1"]).status_code == 403
    assert client.get(f"{API}/courses", headers=ed["adm"]).json()[0]["lessons_count"] == 2

    # deleting a module takes its lessons
    r = client.delete(f"{API}/courses/modules/{m1['id']}", headers=hm)
    assert [m["title"] for m in r.json()["levels"][0]["modules"]] == ["Daily Life"]
    assert client.get(f"{API}/courses/lessons/{l2['id']}", headers=hm).status_code == 404


def test_lesson_builder_blocks(client, ed):
    hm = ed["hm"]
    c = _course(client, hm, published=True)
    m = _module(client, hm, c["levels"][0]["id"])
    les = _lesson(client, hm, m["id"])
    f = _upload(client, hm, les["id"], [("hello.mp3", MP3, "audio/mpeg"), ("map.png", PNG, "image/png"),
                                        ("intro.mp4", MP4, "video/mp4")])
    blocks = [
        {"type": "text", "title": "Hello", "content": {"body": "**Hi!** How are you?"}},
        {"type": "grammar", "content": {"body": "to be: am / is / are", "examples": ["I am Tom.", " ", "She is here."]}},
        {"type": "vocabulary", "content": {"words": [{"word": "hello", "translation": "привет", "transcription": "həˈləʊ"},
                                                     {"word": " "}]}},
        {"type": "image", "content": {"attachment_id": f["map.png"], "caption": "The world"}},
        {"type": "audio", "content": {"attachment_id": f["hello.mp3"], "transcript": "Hello, Tom!"}},
        {"type": "video", "content": {"url": "https://youtu.be/dQw4w9WgXcQ?t=5", "caption": "Watch"}},
        {"type": "video", "content": {"attachment_id": f["intro.mp4"]}},
        {"type": "reading", "content": {"body": "Tom is from Spain.", "image_id": f["map.png"]}, "questions": [CHOICE]},
        {"type": "listening", "content": {"attachment_id": f["hello.mp3"], "max_plays": 2}, "questions": [SHORT]},
        {"type": "quiz", "content": {"body": "Check yourself"}, "questions": [CHOICE, GAPS, MATCH]},
        {"type": "fill_gaps", "questions": [GAPS]},
        {"type": "multiple_choice", "questions": [CHOICE]},
        {"type": "matching", "questions": [MATCH]},
    ]
    r = _save(client, hm, les["id"], blocks, description="First words", duration_minutes=40)
    assert r.status_code == 200, r.text
    d = r.json()
    assert [b["type"] for b in d["blocks"]][:3] == ["text", "grammar", "vocabulary"]
    assert d["blocks"][1]["content"]["examples"] == ["I am Tom.", "She is here."]
    assert len(d["blocks"][2]["content"]["words"]) == 1
    assert d["blocks"][5]["content"] == {"provider": "youtube", "video_id": "dQw4w9WgXcQ", "caption": "Watch"}
    assert d["blocks"][7]["questions"][0]["correct_answer"] == ["a"]  # the editor sees answers
    assert "questions" not in d["blocks"][7]["content"]

    # saving again keeps the ids of the blocks it sends, drops the others
    ids = [b["id"] for b in d["blocks"]]
    again = [{**b, "id": i} for b, i in zip(blocks, ids)][1:]
    d2 = _save(client, hm, les["id"], again).json()
    assert [b["id"] for b in d2["blocks"]] == ids[1:]

    # validation
    bad = [
        ({"type": "video", "content": {"url": "https://evil.example.com/v.mp4"}}, "Вставьте ссылку на видео YouTube или Vimeo"),
        ({"type": "image", "content": {"attachment_id": f["hello.mp3"]}}, "Файл «hello.mp3» не подходит для этого блока"),
        ({"type": "image", "content": {"attachment_id": 999999}}, "Файл не найден в материалах урока"),
        ({"type": "fill_gaps", "questions": [MATCH]}, "Неверный тип задания для этого блока"),
        ({"type": "quiz", "questions": []}, "Добавьте хотя бы один вопрос"),
        ({"type": "text", "content": {"body": "x"}, "questions": [CHOICE]}, "В этом блоке не бывает вопросов"),
        ({"type": "vocabulary", "content": {"words": []}}, "Добавьте хотя бы одно слово"),
        ({"type": "text", "content": {"body": " "}}, "Добавьте текст"),
    ]
    for block, message in bad:
        r = _save(client, hm, les["id"], [block])
        assert r.status_code in (400, 422) and r.json()["detail"] == message, (block, r.text)
    r = client.put(f"{API}/courses/lessons/{les['id']}", headers={**hm, "Accept-Language": "en"},
                   json={"title": "x", "blocks": [{"type": "quiz", "questions": []}]})
    assert r.json()["detail"] == "Add at least one question"
    assert _save(client, hm, les["id"], [], published=True).status_code == 422

    # the student view has no answers; checking grades and reveals
    _save(client, hm, les["id"], blocks, published=True)
    v = client.get(f"{API}/courses/lessons/{les['id']}/view", headers=ed["ha"]).json()
    quiz = next(b for b in v["blocks"] if b["type"] == "quiz")
    assert all(q["correct_answer"] is None and q["explanation"] is None for q in quiz["questions"])
    assert "answers" not in quiz["questions"][1]["config"] and "pairs" not in quiz["questions"][2]["config"]
    r = client.post(f"{API}/courses/lessons/{les['id']}/blocks/{quiz['id']}/check", headers=ed["ha"],
                    json={"answers": {"0": ["a"], "1": ["am", "Kazakhstan"], "2": ["собака", "кошка"]}})
    res = r.json()
    assert [x["is_correct"] for x in res["results"]] == [True, True, False]
    assert res["score"] == 3 and res["max_score"] == 4
    assert res["questions"][0]["correct_answer"] == ["a"] and res["questions"][0]["explanation"] == "He/she/it + -s"
    listening = next(b for b in v["blocks"] if b["type"] == "listening")
    r = client.post(f"{API}/courses/lessons/{les['id']}/blocks/{listening['id']}/check", headers=ed["ha"],
                    json={"answers": {"0": ["  WENT "]}})
    assert r.json()["results"][0]["is_correct"] is True and r.json()["score"] == 2
    text = v["blocks"][0]
    assert client.post(f"{API}/courses/lessons/{les['id']}/blocks/{text['id']}/check", headers=ed["ha"],
                       json={"answers": {}}).status_code == 404

    # files: methodists and (once published) teachers; nobody else
    assert client.get(f"{API}/files/{f['map.png']}", headers=hm).status_code == 200
    assert client.get(f"{API}/files/{f['map.png']}", headers=ed["ha"]).status_code == 200
    assert client.get(f"{API}/files/{f['map.png']}", headers=ed["h1"]).status_code == 404
    client.patch(f"{API}/courses/lessons/{les['id']}", headers=hm, json={"published": False})
    assert client.get(f"{API}/files/{f['map.png']}", headers=ed["ha"]).status_code == 404

    # deleting a file clears the blocks' references to it
    assert client.delete(f"{API}/courses/lessons/{les['id']}/files/{f['map.png']}", headers=hm).status_code == 204
    d = client.get(f"{API}/courses/lessons/{les['id']}", headers=hm).json()
    assert next(b for b in d["blocks"] if b["type"] == "image")["content"]["attachment_id"] is None
    assert next(b for b in d["blocks"] if b["type"] == "reading")["content"]["image_id"] is None


def test_copies_have_their_own_files(client, ed):
    hm = ed["hm"]
    c = _course(client, hm)
    a1, a2 = c["levels"][0]["id"], c["levels"][1]["id"]
    m = _module(client, hm, a1)
    les = _lesson(client, hm, m["id"])
    f = _upload(client, hm, les["id"], [("map.png", PNG, "image/png")])
    _save(client, hm, les["id"], [{"type": "image", "content": {"attachment_id": f["map.png"]}},
                                  {"type": "reading", "content": {"body": "Text"},
                                   "questions": [{**CHOICE, "attachment_ids": [f["map.png"]]}]}], published=True)

    copy = client.post(f"{API}/courses/lessons/{les['id']}/copy", headers=hm, json={}).json()
    assert copy["title"] == "Greetings (copy)" and copy["published"] is False
    new_file = copy["files"][0]["id"]
    assert new_file != f["map.png"]
    assert copy["blocks"][0]["content"]["attachment_id"] == new_file
    assert copy["blocks"][1]["questions"][0]["attachment_ids"] == [new_file]
    tree = client.get(f"{API}/courses/{c['id']}", headers=hm).json()
    assert [x["title"] for x in tree["levels"][0]["modules"][0]["lessons"]] == ["Greetings", "Greetings (copy)"]

    # a module copied into another level brings copies of all its lessons
    tree = client.post(f"{API}/courses/modules/{m['id']}/copy", headers=hm, json={"target_id": a2}).json()
    copied = tree["levels"][1]["modules"][0]
    assert copied["title"] == "Introduction" and [x["published"] for x in copied["lessons"]] == [False, False]
    with SessionLocal() as db:
        keys = [a.storage_key for a in db.query(Attachment).filter(Attachment.course_lesson_id.isnot(None))]
        assert len(keys) == len(set(keys)) == 4

    # deleting the original leaves the copies intact
    assert client.delete(f"{API}/courses/lessons/{les['id']}", headers=hm).status_code == 200
    assert client.get(f"{API}/files/{new_file}", headers=hm).status_code == 200
    # deleting the course removes everything
    assert client.delete(f"{API}/courses/{c['id']}", headers=hm).status_code == 204
    with SessionLocal() as db:
        assert db.query(CourseLesson).count() == 0
        assert db.query(Attachment).filter(Attachment.course_lesson_id.isnot(None)).count() == 0


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=x", ("youtube", "dQw4w9WgXcQ")),
    ("https://youtu.be/dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
    ("https://youtube.com/shorts/dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
    ("https://m.youtube.com/embed/dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
    ("https://vimeo.com/76979871", ("vimeo", "76979871")),
    ("https://player.vimeo.com/video/76979871?h=1", ("vimeo", "76979871")),
])
def test_video_links(url, expected):
    v = parse_video_url(url)
    assert (v["provider"], v["video_id"]) == expected


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "https://youtube.com/watch?v=short", "https://example.com/watch?v=dQw4w9WgXcQ",
    "https://vimeo.com/channels/staff", "ftp://youtu.be/dQw4w9WgXcQ",
])
def test_bad_video_links(url):
    with pytest.raises(TaskError):
        parse_video_url(url)

"""Shared test library: sections (nested), tags, filters and copies.

Library tests have no owning teacher (`Test.is_library`). Methodists and admins
edit them; teachers see published ones and use them by copying into their own
tests (the original is never changed by a teacher).
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BadRequest, NotFound
from app.models import Attachment, Test, TestQuestion, TestSection, TestTag, User
from app.models.enums import CONTENT_TYPES, QuestionType, UserRole
from app.models.test import test_section_links
from app.schemas.homework import AttachmentOut
from app.schemas.library import LibraryItem, LibraryTestDetail, SectionOut, SectionRef, TagOut
from app.services import test_service as svc
from app.storage.base import get_storage

EDITORS = (UserRole.METHODIST, UserRole.ADMIN)


def is_editor(user: User) -> bool:
    return user.role in EDITORS


# ---------- sections ----------

def all_sections(db: Session) -> list[TestSection]:
    return list(db.scalars(select(TestSection).order_by(TestSection.position, TestSection.name)).all())


def descendants(sections: list[TestSection], root_id: int) -> set[int]:
    children: dict[int | None, list[int]] = {}
    for s in sections:
        children.setdefault(s.parent_id, []).append(s.id)
    out, stack = set(), [root_id]
    while stack:
        sid = stack.pop()
        out.add(sid)
        stack += children.get(sid, [])
    return out


def section_tree(db: Session, user: User) -> list[SectionOut]:
    sections = all_sections(db)
    visible = select(Test.id).where(Test.is_library.is_(True))
    if not is_editor(user):
        visible = visible.where(Test.published.is_(True))
    links = db.execute(
        select(test_section_links.c.section_id, test_section_links.c.test_id)
        .where(test_section_links.c.test_id.in_(visible))
    ).all()
    by_section: dict[int, set[int]] = {}
    for sid, tid in links:
        by_section.setdefault(sid, set()).add(tid)
    out = []
    for s in sections:
        tests = set().union(*(by_section.get(d, set()) for d in descendants(sections, s.id)))
        out.append(SectionOut(
            id=s.id, parent_id=s.parent_id, name=s.name, position=s.position,
            direct_count=len(by_section.get(s.id, set())), tests_count=len(tests),
        ))
    return out


def get_section(db: Session, section_id: int) -> TestSection:
    s = db.get(TestSection, section_id)
    if s is None:
        raise NotFound("Раздел не найден")
    return s


def check_parent(db: Session, section: TestSection | None, parent_id: int | None) -> None:
    if parent_id is None:
        return
    get_section(db, parent_id)
    if section is not None and parent_id in descendants(all_sections(db), section.id):
        raise BadRequest("Раздел нельзя вложить в самого себя")


# ---------- tags ----------

def tag_list(db: Session, user: User) -> list[TagOut]:
    from app.models.test import test_tag_links as tl
    q = (
        select(TestTag.id, TestTag.name, func.count(tl.c.test_id))
        .join(tl, tl.c.tag_id == TestTag.id)
        .join(Test, Test.id == tl.c.test_id)
        .where(Test.is_library.is_(True))
        .group_by(TestTag.id)
        .order_by(TestTag.name)
    )
    if not is_editor(user):
        q = q.where(Test.published.is_(True))
    return [TagOut(id=i, name=n, tests_count=c) for i, n, c in db.execute(q).all()]


def set_tags(db: Session, test: Test, names: list[str]) -> None:
    existing = {t.name: t for t in db.scalars(select(TestTag).where(TestTag.name.in_(names))).all()} if names else {}
    tags = []
    for n in names:
        tag = existing.get(n)
        if tag is None:
            tag = TestTag(name=n)
            db.add(tag)
            existing[n] = tag
        tags.append(tag)
    test.tags = tags


def set_sections(db: Session, test: Test, section_ids: list[int]) -> None:
    ids = list(dict.fromkeys(section_ids))
    sections = list(db.scalars(select(TestSection).where(TestSection.id.in_(ids))).all()) if ids else []
    if len(sections) != len(ids):
        raise NotFound("Раздел не найден")
    test.sections = sections


# ---------- tests ----------

def _load_options():
    return (
        selectinload(Test.questions), selectinload(Test.sections), selectinload(Test.tags),
        selectinload(Test.author), selectinload(Test.files),
    )


def get_test(db: Session, user: User, test_id: int) -> Test:
    test = db.scalar(select(Test).options(*_load_options()).where(Test.id == test_id, Test.is_library.is_(True)))
    if test is None or (not test.published and not is_editor(user)):
        raise NotFound("Тест не найден")
    return test


def list_tests(
    db: Session,
    user: User,
    *,
    search: str | None = None,
    level=None,
    section_id: int | None = None,
    tag: str | None = None,
    question_type: QuestionType | None = None,
    author_id: int | None = None,
    published: bool | None = None,
) -> list[LibraryItem]:
    q = select(Test).options(*_load_options()).where(Test.is_library.is_(True))
    if not is_editor(user):
        q = q.where(Test.published.is_(True))
    elif published is not None:
        q = q.where(Test.published.is_(published))
    if search:
        pattern = f"%{search.strip().lower()}%"
        q = q.where(or_(func.lower(Test.title).like(pattern), func.lower(func.coalesce(Test.description, "")).like(pattern)))
    if level:
        q = q.where(Test.level == level)
    if section_id:
        ids = descendants(all_sections(db), section_id)
        q = q.where(Test.id.in_(select(test_section_links.c.test_id).where(test_section_links.c.section_id.in_(ids))))
    if tag:
        q = q.where(Test.tags.any(TestTag.name == tag.strip().lower()))
    if question_type:
        q = q.where(Test.questions.any(TestQuestion.type == question_type))
    if author_id:
        q = q.where(Test.author_id == author_id)
    tests = list(db.scalars(q.order_by(func.coalesce(Test.updated_at, Test.created_at).desc())).unique().all())
    copies = _copies(db, [t.id for t in tests])
    return [to_item(t, copies.get(t.id, 0)) for t in tests]


def _copies(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(Test.source_test_id, func.count()).where(Test.source_test_id.in_(ids), Test.is_library.is_(False))
        .group_by(Test.source_test_id)
    ).all()
    return dict(rows)


def to_item(t: Test, copies: int = 0) -> LibraryItem:
    return LibraryItem(
        id=t.id,
        title=t.title,
        description=t.description,
        level=t.level,
        published=t.published,
        author_id=t.author_id,
        author_name=t.author.full_name if t.author else None,
        sections=[SectionRef(id=s.id, name=s.name) for s in sorted(t.sections, key=lambda s: s.name)],
        tags=sorted(g.name for g in t.tags),
        questions_count=sum(1 for q in t.questions if q.type not in CONTENT_TYPES),
        question_types=list(dict.fromkeys(q.type for q in t.questions)),
        time_limit_minutes=t.time_limit_minutes,
        created_at=t.created_at,
        updated_at=t.updated_at,
        copies=copies,
    )


def to_detail(db: Session, t: Test) -> LibraryTestDetail:
    item = to_item(t, _copies(db, [t.id]).get(t.id, 0))
    return LibraryTestDetail(
        **item.model_dump(),
        **svc.settings_of(t),
        questions=[svc.question_out(q, reveal=True) for q in t.questions],
        files=[AttachmentOut.model_validate(f) for f in t.files],
    )


def apply(db: Session, test: Test, data) -> None:
    """Fill a library test from LibraryTestIn (questions are re-built)."""
    test.title = data.title
    test.description = data.description
    test.time_limit_minutes = data.time_limit_minutes
    test.level = data.level
    test.published = data.published
    svc.apply_settings(test, data)
    svc.build_questions(test, data.questions)
    set_sections(db, test, data.section_ids)
    set_tags(db, test, data.tags)
    test.updated_at = datetime.now(UTC)


# ---------- copies ----------

def copy_test(db: Session, src: Test, *, uploader: User, teacher_id: int | None, title: str | None = None) -> Test:
    """A full copy (questions, settings, files). teacher_id=None makes a library
    draft, otherwise a teacher's own test. Files are duplicated in the storage,
    so deleting one test never removes the other's files."""
    storage = get_storage()
    copy = Test(
        teacher_id=teacher_id,
        is_library=teacher_id is None,
        published=False,
        author_id=uploader.id,
        level=src.level,
        source_test_id=src.id,
        title=(title or src.title)[:200],
        description=src.description,
        time_limit_minutes=src.time_limit_minutes,
        available_from=None,
        shuffle_questions=src.shuffle_questions,
        shuffle_options=src.shuffle_options,
        show_correct_answers=src.show_correct_answers,
        passing_percent=src.passing_percent,
        max_attempts=src.max_attempts,
        updated_at=datetime.now(UTC),
    )
    db.add(copy)
    db.flush()
    id_map: dict[int, int] = {}
    for f in src.files:
        data = b"".join(storage.open(f.storage_key))
        ext = f.storage_key.rsplit(".", 1)[-1]
        key = f"{datetime.now(UTC):%Y/%m}/{uuid.uuid4().hex}.{ext}"
        storage.save(key, data, f.mime_type)
        a = Attachment(uploaded_by_id=uploader.id, test_id=copy.id, original_name=f.original_name,
                       storage_key=key, mime_type=f.mime_type, size_bytes=f.size_bytes)
        db.add(a)
        db.flush()
        id_map[f.id] = a.id
    for q in src.questions:
        config = dict(q.config or {})
        for k in ("attachment_id", "image_id"):
            if config.get(k) in id_map:
                config[k] = id_map[config[k]]
        copy.questions.append(TestQuestion(
            position=q.position, type=q.type, text=q.text, options=list(q.options),
            correct_answer=list(q.correct_answer), points=q.points, explanation=q.explanation,
            attachment_ids=[id_map[i] for i in (q.attachment_ids or []) if i in id_map], config=config,
        ))
    if teacher_id is None:
        copy.sections = list(src.sections)
        copy.tags = list(src.tags)
    db.flush()
    return copy

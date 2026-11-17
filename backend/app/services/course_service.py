"""Courses: access, the course tree, ordering and copies.

Methodists and admins edit everything (drafts included). Teachers read
published courses and, inside them, published lessons only; anything else is
404 for them. Students get access in a later stage, through assignments.
"""
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BadRequest, NotFound
from app.models import Attachment, Course, CourseLesson, CourseLevel, CourseModule, LessonBlock, User
from app.models.enums import LessonBlockType, UserRole
from app.schemas.course import (
    BlockEdit,
    BlockView,
    CourseDetail,
    CourseItem,
    LessonDetail,
    LessonIn,
    LessonPath,
    LessonSummary,
    LessonView,
    LevelOut,
    ModuleOut,
)
from app.schemas.homework import AttachmentOut
from app.services import file_service
from app.services import lesson_blocks as lb

EDITORS = (UserRole.METHODIST, UserRole.ADMIN)


def is_editor(user: User) -> bool:
    return user.role in EDITORS


def now() -> datetime:
    return datetime.now(UTC)


# ---------- loading with access checks ----------

def get_course(db: Session, user: User, course_id: int) -> Course:
    c = db.get(Course, course_id)
    if c is None or (not is_editor(user) and not c.published):
        raise NotFound("Курс не найден")
    return c


def get_level(db: Session, user: User, level_id: int) -> CourseLevel:
    lv = db.get(CourseLevel, level_id)
    if lv is None:
        raise NotFound("Уровень не найден")
    get_course(db, user, lv.course_id)
    return lv


def get_module(db: Session, user: User, module_id: int) -> CourseModule:
    m = db.get(CourseModule, module_id)
    if m is None:
        raise NotFound("Модуль не найден")
    get_course(db, user, m.level.course_id)
    return m


def get_lesson(db: Session, user: User, lesson_id: int) -> CourseLesson:
    les = db.get(CourseLesson, lesson_id)
    if les is None or (not is_editor(user) and not les.published):
        raise NotFound("Урок не найден")
    get_course(db, user, les.module.level.course_id)
    return les


def touch_course(course: Course) -> None:
    course.updated_at = now()


# ---------- ordering ----------

T = TypeVar("T", CourseLevel, CourseModule, CourseLesson)


def place(siblings: list[T], item: T, index: int | None) -> None:
    """Put `item` at `index` among its siblings (None = last) and renumber them."""
    rest = [s for s in siblings if s is not item]
    i = len(rest) if index is None else max(0, min(index, len(rest)))
    rest.insert(i, item)
    for pos, s in enumerate(rest):
        s.position = pos


def renumber(items: list) -> None:
    for pos, s in enumerate(sorted(items, key=lambda x: x.position)):
        s.position = pos


def next_position(items: list) -> int:
    return max((x.position for x in items), default=-1) + 1


# ---------- the tree ----------

def _lesson_summary(les: CourseLesson, blocks: dict[int, int]) -> LessonSummary:
    return LessonSummary(
        id=les.id, title=les.title, published=les.published, position=les.position,
        duration_minutes=les.duration_minutes, blocks_count=blocks.get(les.id, 0), updated_at=les.updated_at,
    )


def _block_counts(db: Session, lesson_ids: list[int]) -> dict[int, int]:
    if not lesson_ids:
        return {}
    rows = db.execute(
        select(LessonBlock.lesson_id, func.count()).where(LessonBlock.lesson_id.in_(lesson_ids)).group_by(LessonBlock.lesson_id)
    ).all()
    return dict(rows)


def _item(course: Course, editor: bool) -> CourseItem:
    lessons = [les for lv in course.levels for m in lv.modules for les in m.lessons]
    visible = [x for x in lessons if editor or x.published]
    return CourseItem(
        id=course.id, title=course.title, description=course.description, published=course.published,
        author_name=course.author.full_name if course.author else None,
        level_codes=[lv.level for lv in course.levels],
        modules_count=sum(len(lv.modules) for lv in course.levels),
        lessons_count=len(visible),
        draft_lessons_count=sum(1 for x in lessons if not x.published) if editor else 0,
        created_at=course.created_at, updated_at=course.updated_at,
    )


def _tree_options():
    return selectinload(Course.levels).selectinload(CourseLevel.modules).selectinload(CourseModule.lessons)


def list_courses(db: Session, user: User) -> list[CourseItem]:
    editor = is_editor(user)
    q = select(Course).options(_tree_options(), selectinload(Course.author)).order_by(Course.title, Course.id)
    if not editor:
        q = q.where(Course.published.is_(True))
    return [_item(c, editor) for c in db.scalars(q).all()]


def course_detail(db: Session, user: User, course_id: int) -> CourseDetail:
    db.expire_all()
    course = get_course(db, user, course_id)
    editor = is_editor(user)
    lessons = [les for lv in course.levels for m in lv.modules for les in m.lessons]
    blocks = _block_counts(db, [x.id for x in lessons])
    levels = []
    for lv in course.levels:
        modules = []
        for m in lv.modules:
            ls = [_lesson_summary(x, blocks) for x in m.lessons if editor or x.published]
            if ls or editor:  # teachers do not see empty (draft-only) modules
                modules.append(ModuleOut(id=m.id, level_id=lv.id, title=m.title, description=m.description,
                                         position=m.position, lessons=ls))
        levels.append(LevelOut(id=lv.id, course_id=course.id, level=lv.level, title=lv.title,
                               description=lv.description, position=lv.position, modules=modules))
    return CourseDetail(**_item(course, editor).model_dump(), levels=levels)


def lesson_path(user: User, les: CourseLesson) -> LessonPath:
    m = les.module
    lv = m.level
    course = lv.course
    editor = is_editor(user)
    order = [x for level in course.levels for mod in level.modules for x in mod.lessons if editor or x.published]
    i = next(k for k, x in enumerate(order) if x.id == les.id)
    return LessonPath(
        course_id=course.id, course_title=course.title, course_published=course.published,
        level_id=lv.id, level=lv.level, level_title=lv.title, module_id=m.id, module_title=m.title,
        prev_id=order[i - 1].id if i > 0 else None,
        next_id=order[i + 1].id if i + 1 < len(order) else None,
    )


def lesson_detail(db: Session, user: User, lesson_id: int) -> LessonDetail:
    db.expire_all()
    les = get_lesson(db, user, lesson_id)
    return LessonDetail(
        id=les.id, title=les.title, description=les.description, duration_minutes=les.duration_minutes,
        published=les.published, updated_at=les.updated_at, path=lesson_path(user, les),
        files=[AttachmentOut.model_validate(f) for f in les.files],
        blocks=[
            BlockEdit(id=b.id, position=b.position, type=b.type, title=b.title,
                      content=lb.public_content(b.content), questions=list(b.content.get("questions") or []))
            for b in les.blocks
        ],
    )


def lesson_view(db: Session, user: User, lesson_id: int) -> LessonView:
    les = get_lesson(db, user, lesson_id)
    return LessonView(
        id=les.id, title=les.title, description=les.description, duration_minutes=les.duration_minutes,
        published=les.published, path=lesson_path(user, les),
        files=[AttachmentOut.model_validate(f) for f in les.files],
        blocks=[
            BlockView(id=b.id, position=b.position, type=b.type, title=b.title,
                      content=lb.public_content(b.content), questions=lb.view_questions(b.id, b.content, False))
            for b in les.blocks
        ],
    )


# ---------- saving a lesson ----------

def _check_files(les: CourseLesson, btype: LessonBlockType, content: dict) -> None:
    files = {f.id: f for f in les.files}
    for fid, kind in lb.file_ids(btype, content):
        f = files.get(fid)
        if f is None:
            raise BadRequest("Файл не найден в материалах урока")
        if kind != "any" and not f.mime_type.startswith(kind + "/"):
            raise BadRequest("Файл «{name}» не подходит для этого блока", name=f.original_name)


def apply_lesson(db: Session, les: CourseLesson, data: LessonIn) -> None:
    """Replace the lesson's content. Blocks sent with their id keep it (later
    progress refers to block ids); blocks left out are deleted."""
    les.title = data.title
    les.description = data.description
    les.duration_minutes = data.duration_minutes
    les.published = data.published
    les.updated_at = now()
    existing = {b.id: b for b in les.blocks}
    for pos, bi in enumerate(data.blocks):
        content = bi.content
        _check_files(les, bi.type, content)
        block = existing.pop(bi.id, None) if bi.id is not None else None
        if block is None:
            block = LessonBlock(type=bi.type)
            les.blocks.append(block)
        block.type = bi.type
        block.title = bi.title
        block.content = content
        block.position = pos
    for b in existing.values():
        les.blocks.remove(b)
    touch_course(les.module.level.course)


# ---------- copies ----------

def copy_lesson(db: Session, src: CourseLesson, module: CourseModule, uploader: User, *, title: str | None = None,
                index: int | None = None) -> CourseLesson:
    """A draft copy with its own copies of the files (deleting one never touches the other)."""
    les = CourseLesson(
        title=(title or src.title)[:200], description=src.description, duration_minutes=src.duration_minutes,
        published=False, position=0, updated_at=now(),
    )
    module.lessons.append(les)
    db.flush()
    id_map = {f.id: file_service.duplicate_attachment(db, f, uploader, course_lesson_id=les.id).id for f in src.files}
    for b in src.blocks:
        les.blocks.append(LessonBlock(type=b.type, title=b.title, position=b.position,
                                      content=lb.remap_files(b.content, id_map)))
    place(list(module.lessons), les, index)
    return les


def copy_module(db: Session, src: CourseModule, level: CourseLevel, uploader: User, *, title: str | None = None,
                index: int | None = None) -> CourseModule:
    m = CourseModule(title=(title or src.title)[:200], description=src.description, position=0)
    level.modules.append(m)
    db.flush()
    for les in src.lessons:
        copy_lesson(db, les, m, uploader)
    place(list(level.modules), m, index)
    return m


def delete_lesson_files(db: Session, lessons: list[CourseLesson]) -> None:
    """Stored objects of lesson files (rows go with the lessons by cascade)."""
    for les in lessons:
        for f in list(les.files):
            les.files.remove(f)
            file_service.delete_attachment(db, f)


def lessons_of_course(course: Course) -> list[CourseLesson]:
    return [x for lv in course.levels for m in lv.modules for x in m.lessons]


def remove_file(les: CourseLesson, att: Attachment) -> None:
    for b in les.blocks:
        b.content = lb.drop_file(b.content, att.id)

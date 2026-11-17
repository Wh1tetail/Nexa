"""Courses / programmes: methodists and admins build them, teachers browse published ones."""
from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.deps import DB, LibraryEditor, LibraryReader
from app.core.exceptions import BadRequest, NotFound
from app.models import Attachment, Course, CourseLesson, CourseLevel, CourseModule
from app.schemas.course import (
    LEVEL_TITLES,
    CheckRequest,
    CheckResult,
    CopyRequest,
    CourseDetail,
    CourseIn,
    CourseItem,
    LessonCreate,
    LessonDetail,
    LessonIn,
    LessonUpdate,
    LessonView,
    LevelIn,
    LevelUpdate,
    ModuleIn,
    ModuleUpdate,
    QuestionResult,
)
from app.schemas.homework import AttachmentOut
from app.services import course_service as cs
from app.services import file_service
from app.services import lesson_blocks as lb
from app.utils.files import VIDEO, validate_upload

router = APIRouter(prefix="/courses", tags=["courses"])

MAX_FILES = 30


def _done(db: DB, user, course_id: int) -> CourseDetail:
    db.commit()
    return cs.course_detail(db, user, course_id)


# ---------- courses ----------

@router.get("", response_model=list[CourseItem])
def list_courses(user: LibraryReader, db: DB) -> list[CourseItem]:
    return cs.list_courses(db, user)


@router.post("", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
def create_course(data: CourseIn, user: LibraryEditor, db: DB) -> CourseDetail:
    course = Course(title=data.title, description=data.description, published=data.published,
                    author_id=user.id, updated_at=cs.now())
    for i, level in enumerate(sorted(data.levels)):
        course.levels.append(CourseLevel(level=level, title=LEVEL_TITLES[level], position=i))
    db.add(course)
    db.flush()
    return _done(db, user, course.id)


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, user: LibraryReader, db: DB) -> CourseDetail:
    return cs.course_detail(db, user, course_id)


@router.put("/{course_id}", response_model=CourseDetail)
def update_course(course_id: int, data: CourseIn, user: LibraryEditor, db: DB) -> CourseDetail:
    """Title, description and publishing (levels are managed separately)."""
    course = cs.get_course(db, user, course_id)
    course.title, course.description, course.published = data.title, data.description, data.published
    cs.touch_course(course)
    return _done(db, user, course.id)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, user: LibraryEditor, db: DB) -> Response:
    course = cs.get_course(db, user, course_id)
    cs.delete_lesson_files(db, cs.lessons_of_course(course))
    db.delete(course)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- levels ----------

@router.post("/{course_id}/levels", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
def add_level(course_id: int, data: LevelIn, user: LibraryEditor, db: DB) -> CourseDetail:
    course = cs.get_course(db, user, course_id)
    if any(lv.level == data.level for lv in course.levels):
        raise BadRequest("Этот уровень уже есть в курсе")
    title = (data.title or "").strip() or LEVEL_TITLES[data.level]
    course.levels.append(CourseLevel(level=data.level, title=title, description=(data.description or "").strip() or None,
                                     position=cs.next_position(course.levels)))
    cs.touch_course(course)
    return _done(db, user, course.id)


@router.patch("/levels/{level_id}", response_model=CourseDetail)
def update_level(level_id: int, data: LevelUpdate, user: LibraryEditor, db: DB) -> CourseDetail:
    lv = cs.get_level(db, user, level_id)
    if data.title is not None:
        lv.title = data.title.strip() or lv.title
    if "description" in data.model_fields_set:
        lv.description = (data.description or "").strip() or None
    if data.position is not None:
        cs.place(list(lv.course.levels), lv, data.position)
    cs.touch_course(lv.course)
    return _done(db, user, lv.course_id)


@router.delete("/levels/{level_id}", response_model=CourseDetail)
def delete_level(level_id: int, user: LibraryEditor, db: DB) -> CourseDetail:
    lv = cs.get_level(db, user, level_id)
    course = lv.course
    cs.delete_lesson_files(db, [x for m in lv.modules for x in m.lessons])
    course.levels.remove(lv)
    cs.touch_course(course)
    return _done(db, user, course.id)


# ---------- modules ----------

@router.post("/levels/{level_id}/modules", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
def add_module(level_id: int, data: ModuleIn, user: LibraryEditor, db: DB) -> CourseDetail:
    lv = cs.get_level(db, user, level_id)
    lv.modules.append(CourseModule(title=data.title.strip(), description=(data.description or "").strip() or None,
                                   position=cs.next_position(lv.modules)))
    cs.touch_course(lv.course)
    return _done(db, user, lv.course_id)


@router.patch("/modules/{module_id}", response_model=CourseDetail)
def update_module(module_id: int, data: ModuleUpdate, user: LibraryEditor, db: DB) -> CourseDetail:
    m = cs.get_module(db, user, module_id)
    course = m.level.course
    if data.title is not None:
        m.title = data.title.strip() or m.title
    if "description" in data.model_fields_set:
        m.description = (data.description or "").strip() or None
    if data.level_id is not None and data.level_id != m.level_id:
        target = cs.get_level(db, user, data.level_id)
        if target.course_id != course.id:
            raise NotFound("Уровень не найден")
        old = m.level
        old.modules.remove(m)
        target.modules.append(m)
        cs.renumber(old.modules)
        cs.place(list(target.modules), m, data.position)
    elif data.position is not None:
        cs.place(list(m.level.modules), m, data.position)
    cs.touch_course(course)
    return _done(db, user, course.id)


@router.delete("/modules/{module_id}", response_model=CourseDetail)
def delete_module(module_id: int, user: LibraryEditor, db: DB) -> CourseDetail:
    m = cs.get_module(db, user, module_id)
    lv = m.level
    cs.delete_lesson_files(db, list(m.lessons))
    lv.modules.remove(m)
    cs.touch_course(lv.course)
    return _done(db, user, lv.course_id)


@router.post("/modules/{module_id}/copy", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
def copy_module(module_id: int, data: CopyRequest, user: LibraryEditor, db: DB) -> CourseDetail:
    """A copy of the module with all its lessons (as drafts), next to it or in another level (any course)."""
    src = cs.get_module(db, user, module_id)
    if data.target_id is None:
        target, index, title = src.level, src.position + 1, f"{src.title} (copy)"
    else:
        target, index, title = cs.get_level(db, user, data.target_id), None, None
    cs.copy_module(db, src, target, user, title=title, index=index)
    cs.touch_course(target.course)
    return _done(db, user, target.course_id)


# ---------- lessons ----------

@router.post("/modules/{module_id}/lessons", response_model=LessonDetail, status_code=status.HTTP_201_CREATED)
def add_lesson(module_id: int, data: LessonCreate, user: LibraryEditor, db: DB) -> LessonDetail:
    m = cs.get_module(db, user, module_id)
    les = CourseLesson(title=data.title.strip(), position=cs.next_position(m.lessons), updated_at=cs.now())
    m.lessons.append(les)
    cs.touch_course(m.level.course)
    db.commit()
    return cs.lesson_detail(db, user, les.id)


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
def get_lesson(lesson_id: int, user: LibraryEditor, db: DB) -> LessonDetail:
    """The editable lesson, with answers (editors only)."""
    return cs.lesson_detail(db, user, lesson_id)


@router.put("/lessons/{lesson_id}", response_model=LessonDetail)
def save_lesson(lesson_id: int, data: LessonIn, user: LibraryEditor, db: DB) -> LessonDetail:
    les = cs.get_lesson(db, user, lesson_id)
    cs.apply_lesson(db, les, data)
    db.commit()
    return cs.lesson_detail(db, user, les.id)


@router.patch("/lessons/{lesson_id}", response_model=CourseDetail)
def update_lesson(lesson_id: int, data: LessonUpdate, user: LibraryEditor, db: DB) -> CourseDetail:
    les = cs.get_lesson(db, user, lesson_id)
    course = les.module.level.course
    if data.title is not None:
        les.title = data.title.strip() or les.title
    if data.published is not None:
        if data.published and not les.blocks:
            raise BadRequest("Добавьте в урок хотя бы один блок, прежде чем публиковать")
        les.published = data.published
    if data.module_id is not None and data.module_id != les.module_id:
        target = cs.get_module(db, user, data.module_id)
        if target.level.course_id != course.id:
            raise NotFound("Модуль не найден")
        old = les.module
        old.lessons.remove(les)
        target.lessons.append(les)
        cs.renumber(old.lessons)
        cs.place(list(target.lessons), les, data.position)
    elif data.position is not None:
        cs.place(list(les.module.lessons), les, data.position)
    les.updated_at = cs.now()
    cs.touch_course(course)
    return _done(db, user, course.id)


@router.delete("/lessons/{lesson_id}", response_model=CourseDetail)
def delete_lesson(lesson_id: int, user: LibraryEditor, db: DB) -> CourseDetail:
    les = cs.get_lesson(db, user, lesson_id)
    m = les.module
    course_id = m.level.course_id
    cs.delete_lesson_files(db, [les])
    m.lessons.remove(les)
    cs.touch_course(m.level.course)
    return _done(db, user, course_id)


@router.post("/lessons/{lesson_id}/copy", response_model=LessonDetail, status_code=status.HTTP_201_CREATED)
def copy_lesson(lesson_id: int, data: CopyRequest, user: LibraryEditor, db: DB) -> LessonDetail:
    """A draft copy, next to the original or in another module (any course)."""
    src = cs.get_lesson(db, user, lesson_id)
    if data.target_id is None:
        target, index, title = src.module, src.position + 1, f"{src.title} (copy)"
    else:
        target, index, title = cs.get_module(db, user, data.target_id), None, None
    copy = cs.copy_lesson(db, src, target, user, title=title, index=index)
    cs.touch_course(target.level.course)
    db.commit()
    return cs.lesson_detail(db, user, copy.id)


@router.post("/lessons/{lesson_id}/files", response_model=list[AttachmentOut], status_code=status.HTTP_201_CREATED)
async def upload_files(lesson_id: int, user: LibraryEditor, db: DB, files: list[UploadFile] = File(...)) -> list[AttachmentOut]:
    les = cs.get_lesson(db, user, lesson_id)
    if len(les.files) + len(files) > MAX_FILES:
        raise BadRequest("Не более {n} файлов в уроке", n=MAX_FILES)
    validated = [await validate_upload(f, VIDEO) for f in files]  # nothing is stored if any file is rejected
    saved = [file_service.store_validated(db, vf, user, course_lesson_id=les.id) for vf in validated]
    les.updated_at = cs.now()
    db.commit()
    return [AttachmentOut.model_validate(a) for a in saved]


@router.delete("/lessons/{lesson_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(lesson_id: int, file_id: int, user: LibraryEditor, db: DB) -> Response:
    les = cs.get_lesson(db, user, lesson_id)
    att = db.get(Attachment, file_id)
    if att is None or att.course_lesson_id != les.id:
        raise NotFound("Файл не найден")
    cs.remove_file(les, att)  # blocks stop pointing at it
    les.files.remove(att)
    file_service.delete_attachment(db, att)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- reading a lesson as a student would ----------

@router.get("/lessons/{lesson_id}/view", response_model=LessonView)
def view_lesson(lesson_id: int, user: LibraryReader, db: DB) -> LessonView:
    """The lesson without answers (preview for editors, content for teachers)."""
    return cs.lesson_view(db, user, lesson_id)


@router.post("/lessons/{lesson_id}/blocks/{block_id}/check", response_model=CheckResult)
def check_block(lesson_id: int, block_id: int, data: CheckRequest, user: LibraryReader, db: DB) -> CheckResult:
    """Check answers to a block's exercises; returns the results and the questions with answers."""
    les = cs.get_lesson(db, user, lesson_id)
    block = next((b for b in les.blocks if b.id == block_id), None)
    if block is None or block.type not in lb.EXERCISES:
        raise NotFound("Задание не найдено")
    results = [QuestionResult(**r) for r in lb.check(block.id, block.content, data.answers)]
    return CheckResult(
        results=results,
        questions=lb.view_questions(block.id, block.content, True),
        score=round(sum(r.points_awarded for r in results), 2),
        max_score=sum(r.max_points for r in results),
    )

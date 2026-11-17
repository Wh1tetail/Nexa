"""Shared test library: methodists and admins edit, teachers browse, preview and copy."""
from fastapi import APIRouter, File, Response, UploadFile, status
from sqlalchemy import delete, insert, select

from app.api.deps import DB, CurrentTeacher, LibraryEditor, LibraryReader
from app.core.exceptions import BadRequest, NotFound
from app.models import Attachment, Test, TestSection
from app.models.enums import EnglishLevel, QuestionType
from app.models.test import test_section_links
from app.schemas.homework import AttachmentOut
from app.schemas.library import (
    LibraryItem,
    LibraryTestDetail,
    LibraryTestIn,
    MoveRequest,
    SectionIn,
    SectionOut,
    SectionUpdate,
    TagOut,
)
from app.schemas.test import TestDetail
from app.services import file_service
from app.services import library_service as lib
from app.utils.files import validate_upload

router = APIRouter(prefix="/library", tags=["library"])

MAX_FILES = 20


# ---------- sections and tags ----------

@router.get("/sections", response_model=list[SectionOut])
def list_sections(user: LibraryReader, db: DB) -> list[SectionOut]:
    return lib.section_tree(db, user)


@router.post("/sections", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
def create_section(data: SectionIn, user: LibraryEditor, db: DB) -> SectionOut:
    lib.check_parent(db, None, data.parent_id)
    s = TestSection(name=data.name.strip(), parent_id=data.parent_id, position=1000)
    db.add(s)
    db.commit()
    return next(x for x in lib.section_tree(db, user) if x.id == s.id)


@router.patch("/sections/{section_id}", response_model=SectionOut)
def update_section(section_id: int, data: SectionUpdate, user: LibraryEditor, db: DB) -> SectionOut:
    s = lib.get_section(db, section_id)
    if data.name:
        s.name = data.name.strip()
    if data.move_to_root:
        s.parent_id = None
    elif data.parent_id is not None:
        lib.check_parent(db, s, data.parent_id)
        s.parent_id = data.parent_id
    if data.position is not None:
        s.position = data.position
    db.commit()
    return next(x for x in lib.section_tree(db, user) if x.id == s.id)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(section_id: int, _: LibraryEditor, db: DB) -> Response:
    """Removes the section and its subsections; the tests stay in the library."""
    db.delete(lib.get_section(db, section_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tags", response_model=list[TagOut])
def list_tags(user: LibraryReader, db: DB) -> list[TagOut]:
    return lib.tag_list(db, user)


# ---------- tests ----------

@router.get("/tests", response_model=list[LibraryItem])
def list_tests(
    user: LibraryReader,
    db: DB,
    search: str | None = None,
    level: EnglishLevel | None = None,
    section_id: int | None = None,
    tag: str | None = None,
    question_type: QuestionType | None = None,
    author_id: int | None = None,
    published: bool | None = None,
) -> list[LibraryItem]:
    """Teachers see published tests; editors also drafts (filter with published)."""
    return lib.list_tests(
        db, user, search=search, level=level, section_id=section_id, tag=tag,
        question_type=question_type, author_id=author_id, published=published,
    )


@router.post("/tests/move", status_code=status.HTTP_204_NO_CONTENT)
def move_tests(data: MoveRequest, _: LibraryEditor, db: DB) -> Response:
    """Put tests into a section (a test may be in several); optionally out of another."""
    lib.get_section(db, data.section_id)
    ids = set(db.scalars(select(Test.id).where(Test.id.in_(data.test_ids), Test.is_library.is_(True))).all())
    if len(ids) != len(set(data.test_ids)):
        raise NotFound("Тест не найден")
    if data.from_section_id:
        db.execute(delete(test_section_links).where(
            test_section_links.c.section_id == data.from_section_id, test_section_links.c.test_id.in_(ids)))
    present = set(db.scalars(select(test_section_links.c.test_id).where(
        test_section_links.c.section_id == data.section_id, test_section_links.c.test_id.in_(ids))).all())
    for tid in ids - present:
        db.execute(insert(test_section_links).values(test_id=tid, section_id=data.section_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tests/{test_id}", response_model=LibraryTestDetail)
def get_test(test_id: int, user: LibraryReader, db: DB) -> LibraryTestDetail:
    """Full preview with the correct answers."""
    return lib.to_detail(db, lib.get_test(db, user, test_id))


@router.post("/tests", response_model=LibraryTestDetail, status_code=status.HTTP_201_CREATED)
def create_test(data: LibraryTestIn, user: LibraryEditor, db: DB) -> LibraryTestDetail:
    test = Test(is_library=True, teacher_id=None, author_id=user.id, title=data.title)
    db.add(test)
    lib.apply(db, test, data)
    db.commit()
    return lib.to_detail(db, lib.get_test(db, user, test.id))


@router.put("/tests/{test_id}", response_model=LibraryTestDetail)
def update_test(test_id: int, data: LibraryTestIn, user: LibraryEditor, db: DB) -> LibraryTestDetail:
    """Editing never touches teachers' copies (they are separate tests)."""
    test = lib.get_test(db, user, test_id)
    lib.apply(db, test, data)
    db.commit()
    db.expire_all()
    return lib.to_detail(db, lib.get_test(db, user, test_id))


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(test_id: int, user: LibraryEditor, db: DB) -> Response:
    test = lib.get_test(db, user, test_id)
    for f in list(test.files):
        file_service.delete_attachment(db, f)
    db.delete(test)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tests/{test_id}/files", response_model=list[AttachmentOut], status_code=status.HTTP_201_CREATED)
async def upload_files(test_id: int, user: LibraryEditor, db: DB, files: list[UploadFile] = File(...)) -> list[AttachmentOut]:
    test = lib.get_test(db, user, test_id)
    if len(test.files) + len(files) > MAX_FILES:
        raise BadRequest("Не более {n} файлов в тесте", n=MAX_FILES)
    validated = [await validate_upload(f) for f in files]  # nothing is stored if any file is rejected
    saved = [file_service.store_validated(db, vf, user, test_id=test.id) for vf in validated]
    db.commit()
    return [AttachmentOut.model_validate(a) for a in saved]


@router.delete("/tests/{test_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(test_id: int, file_id: int, user: LibraryEditor, db: DB) -> Response:
    test = lib.get_test(db, user, test_id)
    att = db.get(Attachment, file_id)
    if att is None or att.test_id != test.id:
        raise NotFound("Файл не найден")
    for q in test.questions:  # questions stop showing it
        if file_id in (q.attachment_ids or []):
            q.attachment_ids = [i for i in q.attachment_ids if i != file_id]
    test.files.remove(att)
    file_service.delete_attachment(db, att)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tests/{test_id}/duplicate", response_model=LibraryTestDetail, status_code=status.HTTP_201_CREATED)
def duplicate_test(test_id: int, user: LibraryEditor, db: DB) -> LibraryTestDetail:
    """A new library draft with the same content (and its own copies of the files)."""
    src = lib.get_test(db, user, test_id)
    copy = lib.copy_test(db, src, uploader=user, teacher_id=None, title=f"{src.title} (copy)")
    db.commit()
    return lib.to_detail(db, lib.get_test(db, user, copy.id))


@router.post("/tests/{test_id}/copy", response_model=TestDetail, status_code=status.HTTP_201_CREATED)
def copy_to_my_tests(test_id: int, teacher: CurrentTeacher, db: DB) -> TestDetail:
    """The teacher gets an own, editable copy (not assigned yet); the original stays as it is."""
    from app.api.v1.endpoints.tests import _detail, _load

    src = lib.get_test(db, teacher.user, test_id)
    copy = lib.copy_test(db, src, uploader=teacher.user, teacher_id=teacher.id)
    db.commit()
    return _detail(_load(db, teacher, copy.id))

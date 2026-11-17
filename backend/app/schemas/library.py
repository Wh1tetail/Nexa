from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import EnglishLevel, QuestionType
from app.schemas.homework import AttachmentOut
from app.schemas.test import QuestionIn, QuestionOut, TestSettings


class SectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None


class SectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = None
    move_to_root: bool = False  # parent_id=None alone means "unchanged"
    position: int | None = Field(default=None, ge=0, le=10000)


class SectionOut(BaseModel):
    id: int
    parent_id: int | None
    name: str
    position: int
    direct_count: int  # tests in this section itself
    tests_count: int  # including subsections


class TagOut(BaseModel):
    id: int
    name: str
    tests_count: int


class SectionRef(BaseModel):
    id: int
    name: str


class LibraryTestIn(TestSettings):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    time_limit_minutes: int | None = Field(default=None, gt=0, le=600)
    questions: list[QuestionIn] = Field(min_length=1, max_length=200)
    level: EnglishLevel | None = None
    section_ids: list[int] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=15)
    published: bool = False

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = " ".join(t.strip().lower().split())[:40]
            if t and t not in out:
                out.append(t)
        return out


class LibraryItem(BaseModel):
    id: int
    title: str
    description: str | None
    level: EnglishLevel | None
    published: bool
    author_id: int | None
    author_name: str | None
    sections: list[SectionRef]
    tags: list[str]
    questions_count: int
    question_types: list[QuestionType]  # what kinds of tasks it contains
    time_limit_minutes: int | None
    created_at: datetime
    updated_at: datetime | None
    copies: int  # personal copies made by teachers


class LibraryTestDetail(LibraryItem, TestSettings):
    questions: list[QuestionOut]
    files: list[AttachmentOut] = []


class MoveRequest(BaseModel):
    """Put tests into a section; with from_section_id they leave that one."""
    test_ids: list[int] = Field(min_length=1, max_length=200)
    section_id: int
    from_section_id: int | None = None

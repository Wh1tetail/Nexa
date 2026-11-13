from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EnglishLevel


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    level: EnglishLevel | None = None
    description: str | None = None
    student_ids: list[int] = []


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    level: EnglishLevel | None = None
    description: str | None = None
    student_ids: list[int] | None = None


class GroupMember(BaseModel):
    id: int
    full_name: str
    english_level: EnglishLevel


class GroupOut(BaseModel):
    id: int
    name: str
    level: EnglishLevel | None
    description: str | None
    created_at: datetime
    students: list[GroupMember]

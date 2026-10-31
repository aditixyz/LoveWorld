from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MemoryVisibility = Literal["private", "shared"]


class MemoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    memory_date: date | None = None
    visibility: MemoryVisibility = "private"

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Title must not be blank.")
        return value


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    memory_date: date | None = None
    visibility: MemoryVisibility | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Title must not be blank.")
        return value

    @model_validator(mode="after")
    def update_must_include_a_field(self) -> "MemoryUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "visibility" in self.model_fields_set and self.visibility is None:
            raise ValueError("Visibility must be 'private' or 'shared'.")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title must not be null.")
        return self


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    memory_date: date | None
    visibility: MemoryVisibility
    created_by: int
    created_at: datetime
    updated_at: datetime


class MemoryPage(BaseModel):
    items: list[MemoryResponse]
    total: int
    limit: int
    offset: int

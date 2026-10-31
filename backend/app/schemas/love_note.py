from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LoveNoteVisibility = Literal["private", "shared"]


class LoveNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    visibility: LoveNoteVisibility = "private"

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Title must not be blank.")
        return value

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Content must not be blank.")
        return value


class LoveNoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    visibility: LoveNoteVisibility | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Title must not be blank.")
        return value

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Content must not be blank.")
        return value

    @model_validator(mode="after")
    def update_must_include_valid_fields(self) -> "LoveNoteUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "content" in self.model_fields_set and self.content is None:
            raise ValueError("Content must not be null.")
        if "visibility" in self.model_fields_set and self.visibility is None:
            raise ValueError("Visibility must be 'private' or 'shared'.")
        return self


class LoveNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    visibility: LoveNoteVisibility
    created_by: int
    created_at: datetime
    updated_at: datetime


class LoveNotePage(BaseModel):
    items: list[LoveNoteResponse]
    total: int
    limit: int
    offset: int

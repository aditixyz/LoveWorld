from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PhotoVisibility = Literal["private", "shared"]


class PhotoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    original_filename: str = Field(min_length=1, max_length=255)
    caption: str | None = Field(default=None, max_length=5000)
    visibility: PhotoVisibility = "private"

    @field_validator("original_filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Original filename must not be blank.")
        return value

    @field_validator("caption")
    @classmethod
    def caption_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Caption must not be blank.")
        return value


class PhotoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    original_filename: str | None = Field(default=None, min_length=1, max_length=255)
    caption: str | None = Field(default=None, max_length=5000)
    visibility: PhotoVisibility | None = None

    @field_validator("original_filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Original filename must not be blank.")
        return value

    @field_validator("caption")
    @classmethod
    def caption_must_not_be_blank(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("Caption must not be blank.")
        return value

    @model_validator(mode="after")
    def update_must_include_valid_fields(self) -> "PhotoUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if (
            "original_filename" in self.model_fields_set
            and self.original_filename is None
        ):
            raise ValueError("Original filename must not be null.")
        if "visibility" in self.model_fields_set and self.visibility is None:
            raise ValueError("Visibility must be 'private' or 'shared'.")
        return self


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    caption: str | None
    visibility: PhotoVisibility
    uploaded_by: int
    created_at: datetime


class PhotoPage(BaseModel):
    items: list[PhotoResponse]
    total: int
    limit: int
    offset: int

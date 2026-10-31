from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

TimelineVisibility = Literal["private", "shared"]


class TimelineMemoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["memory"]
    id: int
    timeline_date: datetime
    visibility: TimelineVisibility
    title: str
    description: str | None
    memory_date: date | None
    created_by: int
    created_at: datetime
    updated_at: datetime


class TimelinePhotoItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["photo"]
    id: int
    timeline_date: datetime
    visibility: TimelineVisibility
    original_filename: str
    caption: str | None
    uploaded_by: int
    created_at: datetime


TimelineItem = Annotated[
    TimelineMemoryItem | TimelinePhotoItem,
    Field(discriminator="type"),
]


class TimelinePage(BaseModel):
    items: list[TimelineItem]
    total: int
    limit: int
    offset: int

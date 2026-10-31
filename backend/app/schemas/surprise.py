from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SurpriseResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["memory", "photo", "love_note"]
    resource_id: int
    title: str
    preview: str | None
    created_at: datetime


class TodaySurpriseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_date: date
    surprise: SurpriseResource | None

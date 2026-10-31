import logging
from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    String,
    Text,
    cast,
    func,
    literal,
    or_,
    select,
    type_coerce,
    union_all,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.errors import log_database_error
from app.db.models import Memory, Photo, User
from app.db.session import get_db
from app.schemas.timeline import (
    TimelineMemoryItem,
    TimelinePage,
    TimelinePhotoItem,
)

router = APIRouter(prefix="/timeline", tags=["timeline"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def _memory_timeline_date(db: Session):
    if db.get_bind().dialect.name == "sqlite":
        return func.datetime(
            func.coalesce(Memory.memory_date, Memory.created_at)
        )
    memory_date_at_utc_midnight = type_coerce(
        func.timezone(
            "UTC",
            cast(Memory.memory_date, DateTime()),
        ),
        DateTime(timezone=True),
    )
    return func.coalesce(memory_date_at_utc_midnight, Memory.created_at)


def _photo_timeline_date(db: Session):
    if db.get_bind().dialect.name == "sqlite":
        return func.datetime(Photo.created_at)
    return Photo.created_at


@router.get("", response_model=TimelinePage)
def get_timeline(
    db: DatabaseSession,
    user: AuthenticatedUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TimelinePage:
    memory_access = or_(
        Memory.created_by == user.id,
        Memory.visibility == "shared",
    )
    photo_access = or_(
        Photo.uploaded_by == user.id,
        Photo.visibility == "shared",
    )
    memory_items = select(
        literal("memory").label("type"),
        Memory.id.label("id"),
        _memory_timeline_date(db).label("timeline_date"),
        Memory.visibility.label("visibility"),
        Memory.title.label("title"),
        Memory.description.label("description"),
        Memory.memory_date.label("memory_date"),
        Memory.created_by.label("created_by"),
        Memory.created_at.label("created_at"),
        Memory.updated_at.label("updated_at"),
        cast(literal(None), String()).label("original_filename"),
        cast(literal(None), String()).label("caption"),
        cast(literal(None), Integer()).label("uploaded_by"),
    ).where(memory_access)
    photo_items = select(
        literal("photo").label("type"),
        Photo.id.label("id"),
        _photo_timeline_date(db).label("timeline_date"),
        Photo.visibility.label("visibility"),
        cast(literal(None), String()).label("title"),
        cast(literal(None), Text()).label("description"),
        cast(literal(None), Date()).label("memory_date"),
        cast(literal(None), Integer()).label("created_by"),
        Photo.created_at.label("created_at"),
        cast(literal(None), DateTime(timezone=True)).label("updated_at"),
        Photo.original_filename.label("original_filename"),
        Photo.caption.label("caption"),
        Photo.uploaded_by.label("uploaded_by"),
    ).where(photo_access)
    timeline = union_all(memory_items, photo_items).subquery()

    try:
        total = db.scalar(select(func.count()).select_from(timeline)) or 0
        rows = db.execute(
            select(timeline)
            .order_by(
                timeline.c.timeline_date.desc(),
                timeline.c.type.asc(),
                timeline.c.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).mappings().all()
    except SQLAlchemyError as error:
        log_database_error(logger, "timeline.list", error)
        try:
            db.rollback()
        except SQLAlchemyError as rollback_error:
            log_database_error(logger, "timeline.list.rollback", rollback_error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database operation unavailable",
        ) from None

    items = []
    for row in rows:
        if row["type"] == "memory":
            timeline_date = row["timeline_date"]
            if row["memory_date"] is not None:
                timeline_date = datetime.combine(
                    row["memory_date"],
                    time.min,
                    tzinfo=UTC,
                )
            items.append(
                TimelineMemoryItem.model_validate(
                    {
                        "type": row["type"],
                        "id": row["id"],
                        "timeline_date": timeline_date,
                        "visibility": row["visibility"],
                        "title": row["title"],
                        "description": row["description"],
                        "memory_date": row["memory_date"],
                        "created_by": row["created_by"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
            )
        else:
            items.append(
                TimelinePhotoItem.model_validate(
                    {
                        "type": row["type"],
                        "id": row["id"],
                        "timeline_date": row["timeline_date"],
                        "visibility": row["visibility"],
                        "original_filename": row["original_filename"],
                        "caption": row["caption"],
                        "uploaded_by": row["uploaded_by"],
                        "created_at": row["created_at"],
                    }
                )
            )
    return TimelinePage(items=items, total=total, limit=limit, offset=offset)

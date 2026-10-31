import hashlib
import logging
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, literal, or_, select, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.errors import log_database_error
from app.db.models import LoveNote, Memory, Photo, User
from app.db.session import get_db
from app.schemas.surprise import SurpriseResource, TodaySurpriseResponse

router = APIRouter(prefix="/surprises", tags=["surprises"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
_PREVIEW_LENGTH = 280


def _utc_today() -> date:
    return datetime.now(UTC).date()


def _selection_seed(user_id: int, display_date: date) -> int:
    digest = hashlib.sha256(
        f"daily-surprise:{user_id}:{display_date.isoformat()}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _database_unavailable(
    db: Session,
    error: SQLAlchemyError,
) -> HTTPException:
    log_database_error(logger, "surprise.today", error)
    try:
        db.rollback()
    except SQLAlchemyError as rollback_error:
        log_database_error(logger, "surprise.today.rollback", rollback_error)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


def _preview(value: str | None) -> str | None:
    if value is None or len(value) <= _PREVIEW_LENGTH:
        return value
    return f"{value[:_PREVIEW_LENGTH].rstrip()}..."


@router.get("/today", response_model=TodaySurpriseResponse)
def get_today_surprise(
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> TodaySurpriseResponse:
    display_date = _utc_today()
    memory_access = or_(
        Memory.created_by == user.id,
        Memory.visibility == "shared",
    )
    photo_access = or_(
        Photo.uploaded_by == user.id,
        Photo.visibility == "shared",
    )
    note_access = or_(
        LoveNote.created_by == user.id,
        LoveNote.visibility == "shared",
    )
    eligible = union_all(
        select(
            literal("memory").label("type"),
            Memory.id.label("resource_id"),
            Memory.title.label("title"),
            func.substr(
                Memory.description,
                1,
                _PREVIEW_LENGTH + 1,
            ).label("preview"),
            Memory.created_at.label("created_at"),
        ).where(memory_access),
        select(
            literal("photo").label("type"),
            Photo.id.label("resource_id"),
            literal("Photo").label("title"),
            func.substr(
                Photo.caption,
                1,
                _PREVIEW_LENGTH + 1,
            ).label("preview"),
            Photo.created_at.label("created_at"),
        ).where(photo_access),
        select(
            literal("love_note").label("type"),
            LoveNote.id.label("resource_id"),
            func.coalesce(LoveNote.title, literal("Love note")).label("title"),
            func.substr(
                LoveNote.content,
                1,
                _PREVIEW_LENGTH + 1,
            ).label("preview"),
            LoveNote.created_at.label("created_at"),
        ).where(note_access),
    ).subquery()
    ranked = (
        select(
            eligible,
            func.row_number()
            .over(order_by=(eligible.c.type, eligible.c.resource_id))
            .label("candidate_rank"),
            func.count().over().label("eligible_count"),
        )
        .subquery()
    )
    seed = _selection_seed(user.id, display_date)
    selected_rank = (seed % ranked.c.eligible_count) + 1

    try:
        row = db.execute(
            select(ranked).where(ranked.c.candidate_rank == selected_rank)
        ).mappings().one_or_none()
    except SQLAlchemyError as error:
        raise _database_unavailable(db, error) from None

    surprise = None
    if row is not None:
        surprise = SurpriseResource(
            type=row["type"],
            resource_id=row["resource_id"],
            title=row["title"],
            preview=_preview(row["preview"]),
            created_at=row["created_at"],
        )
    return TodaySurpriseResponse(display_date=display_date, surprise=surprise)

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.authorization import (
    assign_resource_owner,
    require_resource_access,
    require_resource_owner,
)
from app.auth.dependencies import get_current_user
from app.db.errors import log_database_error
from app.db.models import LoveNote, User
from app.db.session import get_db
from app.schemas.love_note import (
    LoveNoteCreate,
    LoveNotePage,
    LoveNoteResponse,
    LoveNoteUpdate,
)

router = APIRouter(prefix="/love-notes", tags=["love-notes"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def _database_unavailable(
    db: Session,
    operation: str,
    error: SQLAlchemyError,
) -> HTTPException:
    log_database_error(logger, operation, error)
    try:
        db.rollback()
    except SQLAlchemyError as rollback_error:
        log_database_error(logger, f"{operation}.rollback", rollback_error)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


@router.post(
    "",
    response_model=LoveNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_love_note(
    note_data: LoveNoteCreate,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> LoveNoteResponse:
    note = assign_resource_owner(
        LoveNote(**note_data.model_dump()),
        user,
    )
    try:
        db.add(note)
        db.commit()
        db.refresh(note)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "love_note.create", error) from None
    return LoveNoteResponse.model_validate(note)


@router.get("", response_model=LoveNotePage)
def list_love_notes(
    db: DatabaseSession,
    user: AuthenticatedUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LoveNotePage:
    access_filter = or_(
        LoveNote.created_by == user.id,
        LoveNote.visibility == "shared",
    )
    try:
        total = db.scalar(
            select(func.count()).select_from(LoveNote).where(access_filter)
        )
        notes = db.scalars(
            select(LoveNote)
            .where(access_filter)
            .order_by(LoveNote.created_at.desc(), LoveNote.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "love_note.list", error) from None
    return LoveNotePage(
        items=[LoveNoteResponse.model_validate(note) for note in notes],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{note_id}", response_model=LoveNoteResponse)
def get_love_note(
    note_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> LoveNoteResponse:
    try:
        note = require_resource_access(db.get(LoveNote, note_id), user)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "love_note.read", error) from None
    return LoveNoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=LoveNoteResponse)
def update_love_note(
    note_id: int,
    note_data: LoveNoteUpdate,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> LoveNoteResponse:
    try:
        note = require_resource_owner(db.get(LoveNote, note_id), user)
        for field, value in note_data.model_dump(exclude_unset=True).items():
            setattr(note, field, value)
        db.commit()
        db.refresh(note)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "love_note.update", error) from None
    return LoveNoteResponse.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_love_note(
    note_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> Response:
    try:
        note = require_resource_owner(db.get(LoveNote, note_id), user)
        db.delete(note)
        db.commit()
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "love_note.delete", error) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)

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
from app.db.models import Memory, User
from app.db.session import get_db
from app.schemas.memory import MemoryCreate, MemoryPage, MemoryResponse, MemoryUpdate

router = APIRouter(prefix="/memories", tags=["memories"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def _database_unavailable(db: Session) -> HTTPException:
    try:
        db.rollback()
    except SQLAlchemyError:
        logger.error("Database rollback failed while handling a memory operation")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_memory(
    memory_data: MemoryCreate,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> MemoryResponse:
    memory = assign_resource_owner(
        Memory(**memory_data.model_dump()),
        user,
    )
    db.add(memory)
    try:
        db.commit()
        db.refresh(memory)
    except SQLAlchemyError:
        raise _database_unavailable(db) from None
    return MemoryResponse.model_validate(memory)


@router.get("", response_model=MemoryPage)
def list_memories(
    db: DatabaseSession,
    user: AuthenticatedUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MemoryPage:
    access_filter = or_(
        Memory.created_by == user.id,
        Memory.visibility == "shared",
    )
    try:
        total = db.scalar(
            select(func.count()).select_from(Memory).where(access_filter)
        )
        memories = db.scalars(
            select(Memory)
            .where(access_filter)
            .order_by(Memory.created_at.desc(), Memory.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    except SQLAlchemyError:
        raise _database_unavailable(db) from None
    return MemoryPage(
        items=[MemoryResponse.model_validate(memory) for memory in memories],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> MemoryResponse:
    try:
        memory = db.get(Memory, memory_id)
        memory = require_resource_access(memory, user)
    except SQLAlchemyError:
        raise _database_unavailable(db) from None
    return MemoryResponse.model_validate(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory(
    memory_id: int,
    memory_data: MemoryUpdate,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> MemoryResponse:
    try:
        memory = require_resource_owner(db.get(Memory, memory_id), user)
        for field, value in memory_data.model_dump(exclude_unset=True).items():
            setattr(memory, field, value)
        db.commit()
        db.refresh(memory)
    except SQLAlchemyError:
        raise _database_unavailable(db) from None
    return MemoryResponse.model_validate(memory)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_memory(
    memory_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> Response:
    try:
        memory = require_resource_owner(db.get(Memory, memory_id), user)
        db.delete(memory)
        db.commit()
    except SQLAlchemyError:
        raise _database_unavailable(db) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)

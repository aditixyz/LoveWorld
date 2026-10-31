from typing import Protocol, TypeVar

from fastapi import HTTPException, status

from app.db.models import User


class OwnedResource(Protocol):
    owner_id: int
    visibility: str


ResourceT = TypeVar("ResourceT", bound=OwnedResource)


def assign_resource_owner(resource: ResourceT, user: User) -> ResourceT:
    resource.owner_id = user.id
    return resource


def require_resource_owner(resource: ResourceT | None, user: User) -> ResourceT:
    if resource is None or resource.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    return resource


def require_resource_access(resource: ResourceT | None, user: User) -> ResourceT:
    if resource is None or (
        resource.owner_id != user.id and resource.visibility != "shared"
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    return resource

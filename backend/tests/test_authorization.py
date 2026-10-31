from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.auth.authorization import (
    assign_resource_owner,
    require_resource_access,
    require_resource_owner,
)
from app.db.models import LoveNote, Memory, Photo, User


def _user(user_id: int) -> User:
    return User(
        id=user_id,
        username=f"user-{user_id}",
        password_hash="not-used-in-this-test",
        display_name=f"User {user_id}",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("resource", "owner_attribute"),
    [
        (Memory(title="A memory", created_by=1), "created_by"),
        (LoveNote(content="A note", created_by=1), "created_by"),
        (
            Photo(
                original_filename="photo.jpg",
                storage_key="photos/photo.jpg",
                uploaded_by=1,
            ),
            "uploaded_by",
        ),
    ],
)
def test_owner_can_access_private_resources(resource, owner_attribute: str) -> None:
    assert require_resource_access(resource, _user(1)) is resource
    assert require_resource_owner(resource, _user(1)) is resource
    assert getattr(resource, owner_attribute) == 1


def test_another_user_cannot_access_private_resource() -> None:
    resource = Memory(title="Private memory", created_by=1)

    with pytest.raises(HTTPException) as error:
        require_resource_access(resource, _user(2))

    assert error.value.status_code == 404
    assert error.value.detail == "Resource not found"


def test_shared_resource_can_be_read_but_not_modified_by_non_owner() -> None:
    resource = Memory(title="Shared memory", created_by=1, visibility="shared")

    assert require_resource_access(resource, _user(2)) is resource
    with pytest.raises(HTTPException) as error:
        require_resource_owner(resource, _user(2))
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("resource", "owner_attribute"),
    [
        (Memory(title="A memory", created_by=2), "created_by"),
        (LoveNote(content="A note", created_by=2), "created_by"),
        (
            Photo(
                original_filename="photo.jpg",
                storage_key="photos/photo.jpg",
                uploaded_by=2,
            ),
            "uploaded_by",
        ),
    ],
)
def test_owner_assignment_uses_authenticated_user_not_client_id(
    resource,
    owner_attribute: str,
) -> None:
    assigned = assign_resource_owner(resource, _user(1))

    assert assigned.owner_id == 1
    assert getattr(assigned, owner_attribute) == 1


def test_missing_resource_is_not_found() -> None:
    with pytest.raises(HTTPException) as error:
        require_resource_access(None, _user(1))

    assert error.value.status_code == 404

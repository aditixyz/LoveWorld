import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.db.base import Base
from app.db.models import Memory, Photo, User
from app.db.session import get_db
from app.main import app

TEST_SECRET = "timeline-api-test-secret-with-enough-entropy"


@pytest.fixture
def timeline_context() -> Iterator[tuple[Session, User, User, Settings]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    owner = User(
        account_slot=1,
        username="timeline-owner",
        password_hash=hash_password("owner-password-for-tests"),
        display_name="Timeline Owner",
    )
    other_user = User(
        account_slot=2,
        username="timeline-other",
        password_hash=hash_password("other-password-for-tests"),
        display_name="Timeline Other",
    )
    db.add_all([owner, other_user])
    db.commit()
    db.refresh(owner)
    db.refresh(other_user)
    settings = Settings(
        _env_file=None,
        app_environment="test",
        jwt_secret=TEST_SECRET,
    )

    def override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    yield db, owner, other_user, settings
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _request(path: str, token: str | None = None, **kwargs: Any) -> Response:
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    async def send() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.get(path, headers=headers, **kwargs)

    return asyncio.run(send())


def _token(user: User, settings: Settings) -> str:
    return create_access_token(user.id, settings)


def _create_memory(
    db: Session,
    owner: User,
    title: str,
    *,
    created_at: datetime,
    memory_date: date | None = None,
    visibility: str = "private",
) -> Memory:
    memory = Memory(
        title=title,
        description=f"{title} description",
        memory_date=memory_date,
        visibility=visibility,
        created_by=owner.id,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def _create_photo(
    db: Session,
    owner: User,
    filename: str,
    *,
    created_at: datetime,
    visibility: str = "private",
) -> Photo:
    photo = Photo(
        original_filename=filename,
        storage_key=f"{uuid4().hex}.jpg",
        caption=f"{filename} caption",
        visibility=visibility,
        uploaded_by=owner.id,
        created_at=created_at,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def test_timeline_requires_authentication(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    response = _request("/timeline")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_timeline_combines_resources_and_uses_effective_dates(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = timeline_context
    created_at = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    recent_photo = _create_photo(
        db,
        owner,
        "recent.jpg",
        created_at=datetime(2026, 10, 31, 12, 0, tzinfo=UTC),
    )
    fallback_memory = _create_memory(
        db,
        owner,
        "Fallback",
        created_at=datetime(2026, 10, 31, 10, 30, tzinfo=UTC),
    )
    dated_memory = _create_memory(
        db,
        owner,
        "Dated",
        created_at=created_at,
        memory_date=date(2026, 10, 29),
    )
    earlier_photo = _create_photo(
        db,
        owner,
        "earlier.jpg",
        created_at=datetime(2026, 10, 28, 12, 0, tzinfo=UTC),
    )

    response = _request("/timeline", _token(owner, settings))

    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["type"], item["id"]) for item in items] == [
        ("photo", recent_photo.id),
        ("memory", fallback_memory.id),
        ("memory", dated_memory.id),
        ("photo", earlier_photo.id),
    ]
    assert items[1]["timeline_date"] == fallback_memory.created_at.isoformat()
    assert items[2]["timeline_date"].startswith("2026-10-29T00:00:00")
    assert items[2]["created_at"] == dated_memory.created_at.isoformat()


def test_timeline_enforces_private_and_shared_visibility(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = timeline_context
    when = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    owner_private_memory = _create_memory(
        db, owner, "Owner private", created_at=when
    )
    owner_shared_photo = _create_photo(
        db, owner, "owner-shared.jpg", created_at=when, visibility="shared"
    )
    other_private_memory = _create_memory(
        db, other_user, "Other private", created_at=when
    )
    other_shared_memory = _create_memory(
        db, other_user, "Other shared", created_at=when, visibility="shared"
    )
    other_private_photo = _create_photo(
        db, other_user, "other-private.jpg", created_at=when
    )

    response = _request("/timeline", _token(owner, settings))

    assert response.status_code == 200
    items = response.json()["items"]
    returned_ids = {(item["type"], item["id"]) for item in items}
    assert returned_ids == {
        ("memory", owner_private_memory.id),
        ("photo", owner_shared_photo.id),
        ("memory", other_shared_memory.id),
    }
    assert ("memory", other_private_memory.id) not in returned_ids
    assert ("photo", other_private_photo.id) not in returned_ids


def test_timeline_paginates_combined_records_with_stable_equal_date_order(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = timeline_context
    when = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    _create_photo(db, owner, "first-photo.jpg", created_at=when)
    first_memory = _create_memory(db, owner, "First memory", created_at=when)
    _create_photo(db, owner, "second-photo.jpg", created_at=when)
    second_memory = _create_memory(db, owner, "Second memory", created_at=when)
    older = _create_photo(
        db,
        owner,
        "older.jpg",
        created_at=datetime(2026, 10, 30, 12, 0, tzinfo=UTC),
    )
    token = _token(owner, settings)

    page_one = _request("/timeline?limit=2&offset=0", token)
    page_two = _request("/timeline?limit=2&offset=2", token)
    page_three = _request("/timeline?limit=2&offset=4", token)

    first_page_keys = [
        (item["type"], item["id"]) for item in page_one.json()["items"]
    ]
    second_page_keys = [
        (item["type"], item["id"]) for item in page_two.json()["items"]
    ]
    third_page_keys = [
        (item["type"], item["id"]) for item in page_three.json()["items"]
    ]
    assert first_page_keys == [
        ("memory", second_memory.id),
        ("memory", first_memory.id),
    ]
    assert second_page_keys == [
        ("photo", 2),
        ("photo", 1),
    ]
    assert third_page_keys == [("photo", older.id)]
    assert page_one.json()["total"] == 5
    assert page_two.json()["limit"] == 2
    assert page_two.json()["offset"] == 2


def test_timeline_empty_response_and_sensitive_field_exclusion(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = timeline_context
    empty = _request("/timeline", _token(owner, settings))
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}

    memory = _create_memory(
        db,
        owner,
        "Safe memory",
        created_at=datetime(2026, 10, 31, 12, 0, tzinfo=UTC),
    )
    photo = _create_photo(
        db,
        owner,
        "safe.jpg",
        created_at=datetime(2026, 10, 31, 13, 0, tzinfo=UTC),
    )
    response = _request("/timeline", _token(owner, settings))

    assert response.status_code == 200
    assert response.json()["total"] == 2
    encoded = response.text.lower()
    for sensitive_name in (
        "storage_key",
        "storage_path",
        "password_hash",
        "jwt",
        "access_token",
    ):
        assert sensitive_name not in encoded
    assert response.json()["items"][0]["id"] == photo.id
    memory_item = next(
        item for item in response.json()["items"] if item["type"] == "memory"
    )
    assert memory_item["id"] == memory.id
    assert set(memory_item) == {
        "type",
        "id",
        "timeline_date",
        "visibility",
        "title",
        "description",
        "memory_date",
        "created_by",
        "created_at",
        "updated_at",
    }
    photo_item = next(
        item for item in response.json()["items"] if item["type"] == "photo"
    )
    assert set(photo_item) == {
        "type",
        "id",
        "timeline_date",
        "visibility",
        "original_filename",
        "caption",
        "uploaded_by",
        "created_at",
    }


def test_timeline_validates_pagination_bounds(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, _, settings = timeline_context
    token = _token(owner, settings)

    assert _request("/timeline?limit=0", token).status_code == 422
    assert _request("/timeline?limit=101", token).status_code == 422
    assert _request("/timeline?offset=-1", token).status_code == 422


def test_timeline_queries_only_accessible_records(
    timeline_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = timeline_context
    when = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    _create_memory(db, owner, "Owner", created_at=when)
    _create_memory(db, other_user, "Hidden", created_at=when)

    response = _request("/timeline", _token(owner, settings))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Owner"
    assert db.scalar(select(Memory.id).where(Memory.title == "Hidden")) is not None

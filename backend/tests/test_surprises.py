import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.db.base import Base
from app.db.models import LoveNote, Memory, Photo, User
from app.db.session import get_db
from app.main import app

TEST_SECRET = "daily-surprise-test-secret-with-enough-entropy"


@pytest.fixture
def surprise_context() -> Iterator[tuple[Session, User, User, Settings]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    owner = User(
        account_slot=1,
        username="surprise-owner",
        password_hash=hash_password("owner-password-for-tests"),
        display_name="Surprise Owner",
    )
    other_user = User(
        account_slot=2,
        username="surprise-other",
        password_hash=hash_password("other-password-for-tests"),
        display_name="Surprise Other",
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


def _request(
    token: str | None = None,
    **kwargs: Any,
) -> Response:
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    async def send() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.get(
                "/surprises/today",
                headers=headers,
                **kwargs,
            )

    return asyncio.run(send())


def _token(user: User, settings: Settings) -> str:
    return create_access_token(user.id, settings)


def _create_resources(
    db: Session,
    owner: User,
) -> tuple[Memory, Photo, LoveNote]:
    memory = Memory(
        title="A memory",
        description="A memory preview",
        created_by=owner.id,
    )
    photo = Photo(
        original_filename="date-night.jpg",
        storage_key=f"private/{uuid4().hex}.jpg",
        caption="A photo caption",
        uploaded_by=owner.id,
    )
    note = LoveNote(
        title="A note",
        content="A love note preview",
        created_by=owner.id,
    )
    db.add_all([memory, photo, note])
    db.commit()
    db.refresh(memory)
    db.refresh(photo)
    db.refresh(note)
    return memory, photo, note


def test_today_surprise_requires_authentication(
    surprise_context: tuple[Session, User, User, Settings],
) -> None:
    response = _request()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_today_surprise_returns_eligible_resource_and_safe_schema(
    surprise_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = surprise_context
    memory, photo, note = _create_resources(db, owner)

    response = _request(_token(owner, settings))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"display_date", "surprise"}
    assert body["display_date"] == datetime.now(UTC).date().isoformat()
    surprise = body["surprise"]
    assert set(surprise) == {
        "type",
        "resource_id",
        "title",
        "preview",
        "created_at",
    }
    assert (surprise["type"], surprise["resource_id"]) in {
        ("memory", memory.id),
        ("photo", photo.id),
        ("love_note", note.id),
    }
    assert "private/" not in response.text
    assert photo.storage_key not in response.text
    assert "password_hash" not in response.text
    assert "jwt" not in response.text.lower()


def test_today_surprise_is_empty_when_no_accessible_content(
    surprise_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, _, other_user, settings = surprise_context
    db.add(
        Memory(
            title="Another user's private memory",
            created_by=other_user.id,
        )
    )
    db.commit()
    monkeypatch.setattr(
        "app.routers.surprises._utc_today",
        lambda: date(2026, 10, 31),
    )

    response = _request(_token(surprise_context[1], settings))

    assert response.status_code == 200
    assert response.json() == {
        "display_date": "2026-10-31",
        "surprise": None,
    }
    assert "Another user's private memory" not in response.text


def test_today_surprise_is_deterministic_for_user_and_date(
    surprise_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, _, settings = surprise_context
    _create_resources(db, owner)
    monkeypatch.setattr(
        "app.routers.surprises._utc_today",
        lambda: date(2026, 10, 31),
    )
    token = _token(owner, settings)

    first = _request(token).json()
    second = _request(token).json()

    assert first == second


def test_today_surprise_preview_is_limited_to_280_characters(
    surprise_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = surprise_context
    memory = Memory(
        title="Long description",
        description="x" * 1000,
        created_by=owner.id,
    )
    db.add(memory)
    db.commit()

    response = _request(_token(owner, settings))
    preview = response.json()["surprise"]["preview"]

    assert response.status_code == 200
    assert preview == ("x" * 280) + "..."


def test_today_surprise_selection_can_change_between_dates(
    surprise_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, _, settings = surprise_context
    _create_resources(db, owner)
    token = _token(owner, settings)
    selected = set()

    for day in range(1, 32):
        monkeypatch.setattr(
            "app.routers.surprises._utc_today",
            lambda day=day: date(2026, 10, day),
        )
        response = _request(token)
        assert response.status_code == 200
        item = response.json()["surprise"]
        selected.add((item["type"], item["resource_id"]))

    assert len(selected) > 1


def test_today_surprise_excludes_other_users_private_resources(
    surprise_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = surprise_context
    private_memory = Memory(
        title="Private from caller",
        created_by=other_user.id,
    )
    db.add(private_memory)
    db.commit()

    response = _request(_token(owner, settings))

    assert response.status_code == 200
    assert response.json()["surprise"] is None
    assert "Private from caller" not in response.text


def test_today_surprise_can_select_shared_resources(
    surprise_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = surprise_context
    shared_note = LoveNote(
        title="Shared note",
        content="A shared message",
        visibility="shared",
        created_by=other_user.id,
    )
    db.add(
        Memory(
            title="Private note owner memory",
            created_by=other_user.id,
        )
    )
    db.add(shared_note)
    db.commit()
    db.refresh(shared_note)

    response = _request(_token(owner, settings))

    assert response.status_code == 200
    assert response.json()["surprise"]["type"] == "love_note"
    assert response.json()["surprise"]["resource_id"] == shared_note.id
    assert response.json()["surprise"]["preview"] == "A shared message"


def test_today_surprise_reads_only_current_resources(
    surprise_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = surprise_context
    memory, _, _ = _create_resources(db, owner)
    db.delete(memory)
    db.commit()

    response = _request(_token(owner, settings))

    assert response.status_code == 200
    assert response.json()["surprise"] is not None
    assert response.json()["surprise"]["type"] in {"photo", "love_note"}

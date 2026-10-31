import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.db.base import Base
from app.db.models import LoveNote, User
from app.db.session import get_db
from app.main import app

TEST_SECRET = "love-note-test-secret-with-enough-entropy"


@pytest.fixture
def love_note_context() -> Iterator[tuple[Session, User, User, Settings]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    owner = User(
        username="love-note-owner",
        password_hash=hash_password("owner-password-for-tests"),
        display_name="Love Note Owner",
    )
    other_user = User(
        username="love-note-reader",
        password_hash=hash_password("reader-password-for-tests"),
        display_name="Love Note Reader",
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

    from app.core.config import get_settings

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    yield db, owner, other_user, settings
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _request(
    method: str,
    path: str,
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
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(send())


def _token(user: User, settings: Settings) -> str:
    return create_access_token(user.id, settings)


def _create_note(
    db: Session,
    owner: User,
    content: str,
    visibility: str = "private",
) -> LoveNote:
    note = LoveNote(
        title="A note",
        content=content,
        created_by=owner.id,
        visibility=visibility,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/love-notes"),
        ("GET", "/love-notes"),
        ("GET", "/love-notes/1"),
        ("PATCH", "/love-notes/1"),
        ("DELETE", "/love-notes/1"),
    ],
)
def test_love_note_routes_require_authentication(
    love_note_context: tuple[Session, User, User, Settings],
    method: str,
    path: str,
) -> None:
    db, *_ = love_note_context

    response = _request(method, path, json={"content": "Unauthenticated"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db.scalar(select(func.count()).select_from(LoveNote)) == 0


@pytest.mark.parametrize("token_kind", ["malformed", "expired"])
def test_love_note_routes_reject_invalid_or_expired_tokens(
    love_note_context: tuple[Session, User, User, Settings],
    token_kind: str,
) -> None:
    _, owner, _, settings = love_note_context
    if token_kind == "malformed":
        token = "not-a-valid-token"
    else:
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(owner.id),
                "iat": now - timedelta(minutes=2),
                "exp": now - timedelta(minutes=1),
                "jti": "expired-love-note-token",
            },
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

    response = _request("GET", "/love-notes", token=token)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/love-notes"),
        ("GET", "/love-notes"),
        ("GET", "/love-notes/1"),
        ("PATCH", "/love-notes/1"),
        ("DELETE", "/love-notes/1"),
    ],
)
def test_love_note_routes_reject_inactive_users(
    love_note_context: tuple[Session, User, User, Settings],
    method: str,
    path: str,
) -> None:
    db, owner, _, settings = love_note_context
    owner.is_active = False
    db.commit()

    response = _request(
        method,
        path,
        token=_token(owner, settings),
        json={"content": "Inactive account"},
    )

    assert response.status_code == 401
    assert db.scalar(select(func.count()).select_from(LoveNote)) == 0


def test_create_assigns_authenticated_owner_and_defaults_private(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = love_note_context

    response = _request(
        "POST",
        "/love-notes",
        token=_token(owner, settings),
        json={"title": "  A little reminder  ", "content": "  I love you.  "},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "A little reminder"
    assert response.json()["content"] == "I love you."
    assert response.json()["created_by"] == owner.id
    assert response.json()["visibility"] == "private"
    assert db.scalar(select(func.count()).select_from(LoveNote)) == 1


def test_client_cannot_spoof_created_by(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = love_note_context

    response = _request(
        "POST",
        "/love-notes",
        token=_token(owner, settings),
        json={"content": "Spoof attempt", "created_by": other_user.id},
    )

    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(LoveNote)) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": ""},
        {"content": "   "},
        {"title": "   ", "content": "Valid"},
        {"title": "x" * 201, "content": "Valid"},
        {"content": "x" * 10001},
        {"content": "Valid", "visibility": "public"},
        {"content": "Valid", "uploaded_by": 123},
    ],
)
def test_create_rejects_invalid_or_unexpected_fields(
    love_note_context: tuple[Session, User, User, Settings],
    payload: dict[str, object],
) -> None:
    _, owner, _, settings = love_note_context

    response = _request(
        "POST",
        "/love-notes",
        token=_token(owner, settings),
        json=payload,
    )

    assert response.status_code == 422


def test_owner_can_read_private_note_and_others_cannot(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = love_note_context
    note = _create_note(db, owner, "Private note")

    owner_response = _request(
        "GET",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
    )
    other_response = _request(
        "GET",
        f"/love-notes/{note.id}",
        token=_token(other_user, settings),
    )

    assert owner_response.status_code == 200
    assert owner_response.json()["id"] == note.id
    assert other_response.status_code == 404
    assert other_response.json() == {"detail": "Resource not found"}


def test_other_user_can_read_shared_note_but_cannot_update_or_delete(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = love_note_context
    note = _create_note(db, owner, "Shared note", visibility="shared")
    other_token = _token(other_user, settings)

    read_response = _request(
        "GET",
        f"/love-notes/{note.id}",
        token=other_token,
    )
    patch_response = _request(
        "PATCH",
        f"/love-notes/{note.id}",
        token=other_token,
        json={"content": "Hijacked"},
    )
    delete_response = _request(
        "DELETE",
        f"/love-notes/{note.id}",
        token=other_token,
    )

    assert read_response.status_code == 200
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert db.scalar(select(LoveNote.content).where(LoveNote.id == note.id)) == (
        "Shared note"
    )


def test_owner_can_update_note_and_change_visibility(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = love_note_context
    note = _create_note(db, owner, "Original note")

    response = _request(
        "PATCH",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
        json={"title": "Updated title", "content": "Updated content"},
    )
    share_response = _request(
        "PATCH",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
        json={"visibility": "shared"},
    )
    private_response = _request(
        "PATCH",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
        json={"visibility": "private"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["content"] == "Updated content"
    assert share_response.status_code == 200
    assert share_response.json()["visibility"] == "shared"
    assert private_response.status_code == 200
    assert private_response.json()["visibility"] == "private"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"content": ""},
        {"content": "   "},
        {"content": None},
        {"visibility": None},
        {"visibility": "public"},
        {"created_by": 999},
    ],
)
def test_patch_rejects_empty_invalid_or_spoofed_fields(
    love_note_context: tuple[Session, User, User, Settings],
    payload: dict[str, object],
) -> None:
    db, owner, _, settings = love_note_context
    note = _create_note(db, owner, "Original content")

    response = _request(
        "PATCH",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
        json=payload,
    )

    assert response.status_code == 422
    assert db.scalar(select(LoveNote.content).where(LoveNote.id == note.id)) == (
        "Original content"
    )


def test_owner_can_clear_optional_title_and_delete_note(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = love_note_context
    note = _create_note(db, owner, "Note to remove")

    update_response = _request(
        "PATCH",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
        json={"title": None},
    )
    delete_response = _request(
        "DELETE",
        f"/love-notes/{note.id}",
        token=_token(owner, settings),
    )

    assert update_response.status_code == 200
    assert update_response.json()["title"] is None
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert db.get(LoveNote, note.id) is None


def test_missing_and_inaccessible_ids_use_same_generic_response(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = love_note_context
    note = _create_note(db, owner, "Private note")
    other_token = _token(other_user, settings)

    inaccessible = _request(
        "GET",
        f"/love-notes/{note.id}",
        token=other_token,
    )
    missing = _request("GET", "/love-notes/999999", token=other_token)

    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json() == {
        "detail": "Resource not found"
    }


def test_list_returns_owner_and_shared_only_with_deterministic_pagination(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = love_note_context
    _create_note(db, owner, "Owner note one")
    _create_note(db, owner, "Owner note two")
    _create_note(db, other_user, "Shared note", visibility="shared")
    _create_note(db, other_user, "Private other note")
    token = _token(owner, settings)

    first_page = _request("GET", "/love-notes?limit=2&offset=0", token=token)
    second_page = _request("GET", "/love-notes?limit=2&offset=2", token=token)
    all_notes = _request("GET", "/love-notes?limit=10", token=token)

    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["limit"] == 2
    assert first_page.json()["offset"] == 0
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1
    ids = [
        item["id"]
        for page in (first_page, second_page)
        for item in page.json()["items"]
    ]
    assert ids == sorted(ids, reverse=True)
    assert {item["content"] for item in all_notes.json()["items"]} == {
        "Owner note one",
        "Owner note two",
        "Shared note",
    }


def test_list_validates_pagination_bounds(
    love_note_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, _, settings = love_note_context
    token = _token(owner, settings)

    assert _request("GET", "/love-notes?limit=0", token=token).status_code == 422
    assert _request("GET", "/love-notes?limit=101", token=token).status_code == 422
    assert _request("GET", "/love-notes?offset=-1", token=token).status_code == 422


@pytest.mark.parametrize("operation", ["create", "update"])
def test_database_write_failures_are_generic_and_rolled_back(
    love_note_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    db, owner, _, settings = love_note_context
    note = _create_note(db, owner, "Original content") if operation == "update" else None

    def fail_commit() -> None:
        raise OperationalError(
            "INSERT INTO love_notes",
            {},
            Exception("private database password and SQL details"),
        )

    monkeypatch.setattr(db, "commit", fail_commit)
    if operation == "create":
        response = _request(
            "POST",
            "/love-notes",
            token=_token(owner, settings),
            json={"content": "Failed write"},
        )
    else:
        assert note is not None
        response = _request(
            "PATCH",
            f"/love-notes/{note.id}",
            token=_token(owner, settings),
            json={"content": "Failed update"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Database operation unavailable"}
    assert "password" not in response.text.lower()
    assert "INSERT" not in response.text
    if operation == "create":
        assert db.scalar(select(func.count()).select_from(LoveNote)) == 0
    else:
        assert note is not None
        assert db.scalar(
            select(LoveNote.content).where(LoveNote.id == note.id)
        ) == "Original content"

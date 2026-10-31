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
from app.db.models import Memory, User
from app.db.session import get_db
from app.main import app

TEST_SECRET = "memory-api-test-secret-with-enough-entropy"


@pytest.fixture
def memory_context() -> Iterator[tuple[Session, User, User, Settings]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    owner = User(
        account_slot=1,
        username="memory-owner",
        password_hash=hash_password("owner-password-for-tests"),
        display_name="Memory Owner",
    )
    other_user = User(
        account_slot=2,
        username="memory-reader",
        password_hash=hash_password("reader-password-for-tests"),
        display_name="Memory Reader",
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
    from app.core.config import get_settings

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


def _create_memory(
    db: Session,
    owner: User,
    title: str,
    visibility: str = "private",
) -> Memory:
    memory = Memory(
        title=title,
        created_by=owner.id,
        visibility=visibility,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/memories"),
        ("GET", "/memories"),
        ("GET", "/memories/1"),
        ("PATCH", "/memories/1"),
        ("DELETE", "/memories/1"),
    ],
)
def test_memory_routes_require_authentication(
    memory_context: tuple[Session, User, User, Settings],
    method: str,
    path: str,
) -> None:
    db, *_ = memory_context
    response = _request(method, path, json={"title": "Unauthenticated"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db.scalar(select(func.count()).select_from(Memory)) == 0


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/memories"),
        ("GET", "/memories"),
        ("GET", "/memories/1"),
        ("PATCH", "/memories/1"),
        ("DELETE", "/memories/1"),
    ],
)
def test_memory_routes_reject_inactive_users(
    memory_context: tuple[Session, User, User, Settings],
    method: str,
    path: str,
) -> None:
    db, owner, _, settings = memory_context
    owner.is_active = False
    db.commit()

    response = _request(
        method,
        path,
        token=_token(owner, settings),
        json={"title": "Inactive account"},
    )

    assert response.status_code == 401
    assert db.scalar(select(func.count()).select_from(Memory)) == 0


@pytest.mark.parametrize("token_kind", ["malformed", "expired"])
def test_memory_routes_reject_invalid_or_expired_tokens(
    memory_context: tuple[Session, User, User, Settings],
    token_kind: str,
) -> None:
    _, owner, _, settings = memory_context
    if token_kind == "malformed":
        token = "not-a-valid-token"
    else:
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(owner.id),
                "iat": now - timedelta(minutes=2),
                "exp": now - timedelta(minutes=1),
                "jti": "expired-memory-token",
            },
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

    response = _request("GET", "/memories", token=token)

    assert response.status_code == 401


def test_create_assigns_authenticated_owner_and_defaults_private(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = memory_context
    response = _request(
        "POST",
        "/memories",
        token=_token(owner, settings),
        json={
            "title": "  A special day  ",
            "description": "A memory",
            "memory_date": "2026-10-31",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "A special day"
    assert data["created_by"] == owner.id
    assert data["visibility"] == "private"
    assert data["memory_date"] == "2026-10-31"
    assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_client_cannot_spoof_created_by(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = memory_context
    response = _request(
        "POST",
        "/memories",
        token=_token(owner, settings),
        json={"title": "Spoof attempt", "created_by": other_user.id},
    )

    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(Memory)) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   "},
        {"title": ""},
        {"title": "Valid", "visibility": "public"},
        {"title": "Valid", "description": "x" * 5001},
        {"title": "Valid", "memory_date": "not-a-date"},
        {"title": "Valid", "created_by": 123},
    ],
)
def test_create_rejects_invalid_or_unexpected_fields(
    memory_context: tuple[Session, User, User, Settings],
    payload: dict[str, object],
) -> None:
    _, owner, _, settings = memory_context
    response = _request(
        "POST",
        "/memories",
        token=_token(owner, settings),
        json=payload,
    )

    assert response.status_code == 422


def test_owner_can_read_private_memory_and_others_cannot(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = memory_context
    memory = _create_memory(db, owner, "Private memory")

    owner_response = _request(
        "GET",
        f"/memories/{memory.id}",
        token=_token(owner, settings),
    )
    other_response = _request(
        "GET",
        f"/memories/{memory.id}",
        token=_token(other_user, settings),
    )

    assert owner_response.status_code == 200
    assert owner_response.json()["id"] == memory.id
    assert other_response.status_code == 404
    assert other_response.json() == {"detail": "Resource not found"}


def test_other_user_can_read_shared_memory_but_cannot_update_or_delete(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = memory_context
    memory = _create_memory(db, owner, "Shared memory", visibility="shared")
    other_token = _token(other_user, settings)

    read_response = _request(
        "GET",
        f"/memories/{memory.id}",
        token=other_token,
    )
    patch_response = _request(
        "PATCH",
        f"/memories/{memory.id}",
        token=other_token,
        json={"title": "Hijacked"},
    )
    delete_response = _request(
        "DELETE",
        f"/memories/{memory.id}",
        token=other_token,
    )

    assert read_response.status_code == 200
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert db.get(Memory, memory.id).title == "Shared memory"


def test_owner_can_update_visibility_and_clear_optional_fields(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = memory_context
    memory = _create_memory(db, owner, "Private memory")

    response = _request(
        "PATCH",
        f"/memories/{memory.id}",
        token=_token(owner, settings),
        json={"visibility": "shared", "description": "Shared note"},
    )
    cleared = _request(
        "PATCH",
        f"/memories/{memory.id}",
        token=_token(owner, settings),
        json={"description": None, "memory_date": None},
    )

    assert response.status_code == 200
    assert response.json()["visibility"] == "shared"
    assert response.json()["description"] == "Shared note"
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": None},
        {"visibility": None},
        {"visibility": "public"},
        {"created_by": 999},
    ],
)
def test_patch_rejects_empty_invalid_or_spoofed_fields(
    memory_context: tuple[Session, User, User, Settings],
    payload: dict[str, object],
) -> None:
    db, owner, _, settings = memory_context
    memory = _create_memory(db, owner, "Original")

    response = _request(
        "PATCH",
        f"/memories/{memory.id}",
        token=_token(owner, settings),
        json=payload,
    )

    assert response.status_code == 422
    db.refresh(memory)
    assert memory.title == "Original"
    assert memory.created_by == owner.id


def test_owner_can_delete_only_their_memory(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = memory_context
    memory = _create_memory(db, owner, "To delete")

    response = _request(
        "DELETE",
        f"/memories/{memory.id}",
        token=_token(owner, settings),
    )

    assert response.status_code == 204
    assert response.content == b""
    assert db.get(Memory, memory.id) is None


def test_missing_and_inaccessible_ids_use_same_generic_response(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = memory_context
    memory = _create_memory(db, owner, "Private")
    other_token = _token(other_user, settings)

    inaccessible = _request("GET", f"/memories/{memory.id}", token=other_token)
    missing = _request("GET", "/memories/999999", token=other_token)

    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json() == {"detail": "Resource not found"}


def test_list_returns_owner_and_shared_only_with_deterministic_pagination(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = memory_context
    _create_memory(db, owner, "Owner One")
    _create_memory(db, owner, "Owner Two")
    _create_memory(db, other_user, "Shared One", visibility="shared")
    _create_memory(db, other_user, "Private Other")
    token = _token(owner, settings)

    first_page = _request("GET", "/memories?limit=2&offset=0", token=token)
    second_page = _request("GET", "/memories?limit=2&offset=2", token=token)
    all_items = _request("GET", "/memories?limit=10", token=token)

    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["limit"] == 2
    assert first_page.json()["offset"] == 0
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1
    combined_ids = [
        item["id"]
        for page in (first_page, second_page)
        for item in page.json()["items"]
    ]
    assert combined_ids == sorted(combined_ids, reverse=True)
    assert {item["title"] for item in all_items.json()["items"]} == {
        "Owner One",
        "Owner Two",
        "Shared One",
    }


def test_list_validates_pagination_bounds(
    memory_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, _, settings = memory_context
    token = _token(owner, settings)

    assert _request("GET", "/memories?limit=0", token=token).status_code == 422
    assert _request("GET", "/memories?limit=101", token=token).status_code == 422
    assert _request("GET", "/memories?offset=-1", token=token).status_code == 422


def test_database_write_failure_rolls_back_and_hides_internal_error(
    memory_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db, owner, _, settings = memory_context

    def fail_commit() -> None:
        raise OperationalError(
            "INSERT INTO memories",
            {},
            Exception("private database password and SQL details"),
        )

    monkeypatch.setattr(db, "commit", fail_commit)
    response = _request(
        "POST",
        "/memories",
        token=_token(owner, settings),
        json={"title": "Failed write"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Database operation unavailable"}
    assert "password" not in response.text.lower()
    assert "INSERT" not in response.text
    assert "OperationalError" in caplog.text
    assert "memory.create" in caplog.text
    assert "private database password and SQL details" not in caplog.text
    assert "INSERT INTO memories" not in caplog.text
    assert db.scalar(select(func.count()).select_from(Memory)) == 0

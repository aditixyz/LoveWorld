import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.passwords import hash_password, verify_password
from app.db.base import Base
from app.db.models import User
from app.db.session import get_db
from app.main import app


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_environment="test",
        jwt_secret="test-auth-signing-secret-that-is-long-enough",
    )


def _request(method: str, path: str, **kwargs: object) -> Response:
    async def send() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


@pytest.fixture
def auth_context() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine, autoflush=False)
    db = test_session_factory()
    settings = _test_settings()

    def override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    yield db
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _add_user(
    db: Session,
    username: str = "private-user",
    password: str = "a-secure-test-password",
    active: bool = True,
) -> User:
    user = User(
        username=username,
        display_name="Test User",
        password_hash=hash_password(password),
        is_active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_and_current_user_return_only_safe_fields(
    auth_context: Session,
) -> None:
    user = _add_user(auth_context)
    login_response = _request(
        "POST",
        "/auth/login",
        json={"username": user.username, "password": "a-secure-test-password"},
    )

    assert login_response.status_code == 200
    token_data = login_response.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["access_token"]
    assert "password" not in token_data

    me_response = _request(
        "GET",
        "/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "is_active": True,
        "created_at": user.created_at.isoformat(),
    }
    assert "password_hash" not in me_response.json()


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("private-user", "incorrect-password"),
        ("unknown-user", "a-secure-test-password"),
    ],
)
def test_login_failure_is_generic_and_does_not_create_users(
    auth_context: Session,
    username: str,
    password: str,
) -> None:
    _add_user(auth_context)
    before_count = auth_context.scalar(select(func.count()).select_from(User))

    response = _request(
        "POST",
        "/auth/login",
        json={"username": username, "password": password},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
    assert response.headers["www-authenticate"] == "Bearer"
    assert auth_context.scalar(select(func.count()).select_from(User)) == before_count


def test_login_rejects_inactive_user(auth_context: Session) -> None:
    _add_user(auth_context, active=False)

    response = _request(
        "POST",
        "/auth/login",
        json={"username": "private-user", "password": "a-secure-test-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer malformed-token", "Basic abc"],
)
def test_current_user_rejects_missing_or_invalid_bearer(
    auth_context: Session,
    authorization: str | None,
) -> None:
    assert auth_context.scalar(select(func.count()).select_from(User)) == 0
    headers = {"Authorization": authorization} if authorization else {}

    response = _request("GET", "/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_rejects_inactive_or_deleted_accounts(
    auth_context: Session,
) -> None:
    user = _add_user(auth_context)
    login_response = _request(
        "POST",
        "/auth/login",
        json={"username": user.username, "password": "a-secure-test-password"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user.is_active = False
    auth_context.commit()
    inactive_response = _request("GET", "/auth/me", headers=headers)
    assert inactive_response.status_code == 401

    auth_context.delete(user)
    auth_context.commit()
    deleted_response = _request("GET", "/auth/me", headers=headers)
    assert deleted_response.status_code == 401


def test_current_user_rejects_nonexistent_token_subject(
    auth_context: Session,
) -> None:
    assert auth_context.scalar(select(func.count()).select_from(User)) == 0
    settings = _test_settings()
    token = jwt.encode(
        {
            "sub": "2147483647",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "jti": "nonexistent-user",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = _request(
        "GET",
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_current_user_rejects_expired_token(auth_context: Session) -> None:
    assert auth_context.scalar(select(func.count()).select_from(User)) == 0
    settings = _test_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "jti": "expired-user-token",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = _request(
        "GET",
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_provisioned_user_stores_only_password_hash(
    auth_context: Session,
) -> None:
    from app.services.users import create_user

    user = create_user(
        auth_context,
        "  First.User ",
        " First User ",
        "a-unique-provisioning-password",
    )
    auth_context.commit()

    assert user.username == "first.user"
    assert user.display_name == "First User"
    assert user.password_hash != "a-unique-provisioning-password"
    assert verify_password("a-unique-provisioning-password", user.password_hash)
    assert auth_context.scalar(select(func.count()).select_from(User)) == 1

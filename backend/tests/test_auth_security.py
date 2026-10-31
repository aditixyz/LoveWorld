from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import extract_parameters
from argon2.low_level import Type
from jwt.exceptions import InvalidTokenError
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token, decode_access_token


def _settings(secret: str = "test-signing-secret-that-is-long-enough") -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret=SecretStr(secret),
        app_environment="test",
    )


def test_password_hash_uses_argon2id_and_verifies_password() -> None:
    password_hash = hash_password("a-long-test-password")

    assert extract_parameters(password_hash).type is Type.ID
    assert verify_password("a-long-test-password", password_hash)
    assert not verify_password("a-different-password", password_hash)


def test_malformed_password_hash_is_rejected_safely() -> None:
    assert not verify_password("some-password", "not-a-valid-argon2-hash")


def test_access_token_contains_required_claims_and_decodes() -> None:
    settings = _settings()
    token = create_access_token(42, settings)
    claims = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
    )

    assert claims["sub"] == "42"
    assert claims["iat"]
    assert claims["exp"]
    assert claims["jti"]
    assert decode_access_token(token, settings) == 42


@pytest.mark.parametrize(
    "token",
    [
        "malformed",
        "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIn0.",
    ],
)
def test_malformed_or_unsigned_tokens_are_rejected(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, _settings())


def test_expired_access_token_is_rejected() -> None:
    settings = _settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "jti": "expired-token",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_invalid_subject_is_rejected() -> None:
    settings = _settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "9" * 5000,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": "invalid-subject",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_tampered_and_wrong_signature_tokens_are_rejected() -> None:
    settings = _settings()
    token = create_access_token(1, settings)
    header, payload, signature = token.split(".")
    tampered_token = f"{header}.{payload[:-1]}{'A' if payload[-1] != 'A' else 'B'}.{signature}"

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered_token, settings)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, _settings("a-different-signing-secret-long-enough"))


def test_production_requires_a_non_placeholder_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_environment="production")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_environment="production",
            jwt_secret=SecretStr("replace-with-a-random-local-secret"),
        )

    settings = Settings(
        _env_file=None,
        app_environment="production",
        jwt_secret=SecretStr("p" * 48),
    )
    assert settings.app_environment == "production"

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings, get_settings


def create_access_token(
    subject: int,
    settings: Settings | None = None,
) -> str:
    active_settings = settings or get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=active_settings.access_token_expire_minutes),
        "jti": str(uuid4()),
    }
    return jwt.encode(
        claims,
        active_settings.jwt_secret.get_secret_value(),
        algorithm=active_settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> int:
    active_settings = settings or get_settings()
    claims = jwt.decode(
        token,
        active_settings.jwt_secret.get_secret_value(),
        algorithms=[active_settings.jwt_algorithm],
        options={"require": ["sub", "iat", "exp", "jti"]},
    )
    subject = claims.get("sub")
    if (
        not isinstance(subject, str)
        or not subject.isdecimal()
        or len(subject) > 10
    ):
        raise InvalidTokenError("Invalid token subject")
    user_id = int(subject)
    if not 1 <= user_id <= 2_147_483_647:
        raise InvalidTokenError("Invalid token subject")
    if not isinstance(claims.get("jti"), str) or not claims["jti"]:
        raise InvalidTokenError("Invalid token identifier")
    return user_id

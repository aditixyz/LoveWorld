import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import LoginRateLimit


def _key_hash(username: str, settings: Settings) -> str:
    return hmac.new(
        settings.jwt_secret.get_secret_value().encode(),
        username.encode(),
        hashlib.sha256,
    ).hexdigest()


def _upsert_statement(
    db: Session,
    key_hash: str,
    now: datetime,
    window: timedelta,
):
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        insert = postgresql_insert
    elif dialect_name == "sqlite":
        insert = sqlite_insert
    else:
        raise RuntimeError("Login rate limiting requires PostgreSQL or SQLite.")

    stale_window = LoginRateLimit.window_started_at <= now - window
    statement = insert(LoginRateLimit).values(
        key_hash=key_hash,
        window_started_at=now,
        attempts=1,
    )
    return statement.on_conflict_do_update(
        index_elements=[LoginRateLimit.key_hash],
        set_={
            "window_started_at": case(
                (stale_window, now),
                else_=LoginRateLimit.window_started_at,
            ),
            "attempts": case(
                (stale_window, 1),
                else_=LoginRateLimit.attempts + 1,
            ),
        },
    ).returning(LoginRateLimit.attempts)


def consume_login_attempt(
    db: Session,
    username: str,
    settings: Settings,
) -> int:
    now = datetime.now(UTC)
    window = timedelta(seconds=settings.login_rate_limit_window_seconds)
    key_hash = _key_hash(username, settings)

    db.execute(
        delete(LoginRateLimit).where(
            LoginRateLimit.window_started_at <= now - window
        )
    )
    attempts = db.scalar(_upsert_statement(db, key_hash, now, window))
    db.commit()
    return attempts or 0


def clear_login_attempts(db: Session, username: str, settings: Settings) -> None:
    db.execute(
        delete(LoginRateLimit).where(
            LoginRateLimit.key_hash == _key_hash(username, settings)
        )
    )
    db.commit()

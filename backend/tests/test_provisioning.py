from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.passwords import verify_password
from app.db.base import Base
from app.db.models import User
from app.services.users import create_user


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_provisioning_hashes_password_before_persistence(db_session: Session) -> None:
    user = create_user(
        db_session,
        "first-user",
        "First User",
        "a-unique-secure-password",
    )
    db_session.commit()

    stored_user = db_session.scalar(select(User).where(User.username == "first-user"))
    assert stored_user is user
    assert stored_user.password_hash != "a-unique-secure-password"
    assert verify_password("a-unique-secure-password", stored_user.password_hash)


def test_provisioning_rejects_duplicate_username_case_insensitively(
    db_session: Session,
) -> None:
    create_user(db_session, "first-user", "First User", "a-unique-secure-password")
    db_session.commit()

    with pytest.raises(ValueError, match="already exists"):
        create_user(db_session, "FIRST-USER", "Duplicate", "another-secure-password")

    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_provisioning_refuses_more_than_two_users(db_session: Session) -> None:
    create_user(db_session, "first-user", "First User", "a-unique-secure-password")
    create_user(db_session, "second-user", "Second User", "another-secure-password")
    db_session.commit()

    with pytest.raises(ValueError, match="two-user account limit"):
        create_user(db_session, "third-user", "Third User", "third-secure-password")

    assert db_session.scalar(select(func.count()).select_from(User)) == 2


def test_provisioning_enforces_password_length(db_session: Session) -> None:
    with pytest.raises(ValueError, match="12 and 128"):
        create_user(db_session, "first-user", "First User", "too-short")

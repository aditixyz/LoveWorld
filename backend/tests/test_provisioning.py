from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.passwords import verify_password
from app.db.base import Base
from app.db.models import User
from app.services import users as user_service
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


def test_first_and_second_users_claim_distinct_account_slots(
    db_session: Session,
) -> None:
    first = create_user(
        db_session,
        "first-user",
        "First User",
        "a-unique-secure-password",
    )
    second = create_user(
        db_session,
        "second-user",
        "Second User",
        "another-secure-password",
    )
    db_session.commit()

    assert {first.account_slot, second.account_slot} == {1, 2}
    assert db_session.scalar(select(func.count()).select_from(User)) == 2


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


def test_provisioning_preserves_existing_users_and_credentials(
    db_session: Session,
) -> None:
    existing = User(
        account_slot=2,
        username="existing-user",
        display_name="Existing User",
        password_hash="existing-password-hash",
    )
    db_session.add(existing)
    db_session.commit()
    original_id = existing.id

    added = create_user(
        db_session,
        "new-user",
        "New User",
        "a-new-secure-password",
    )
    db_session.commit()
    db_session.expire_all()

    preserved = db_session.get(User, original_id)
    assert preserved is not None
    assert preserved.username == "existing-user"
    assert preserved.display_name == "Existing User"
    assert preserved.password_hash == "existing-password-hash"
    assert preserved.account_slot == 2
    assert added.account_slot == 1


def test_database_constraints_reject_invalid_or_duplicate_account_slots(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            User(
                account_slot=1,
                username="slot-one",
                display_name="Slot One",
                password_hash="hash-one",
            ),
            User(
                account_slot=2,
                username="slot-two",
                display_name="Slot Two",
                password_hash="hash-two",
            ),
        ]
    )
    db_session.commit()
    db_session.add(
        User(
            account_slot=3,
            username="slot-three",
            display_name="Slot Three",
            password_hash="hash-three",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.scalar(select(func.count()).select_from(User)) == 2
    db_session.add(
        User(
            account_slot=1,
            username="duplicate-slot",
            display_name="Duplicate Slot",
            password_hash="duplicate-slot-hash",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_concurrent_provisioning_never_creates_a_third_user(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "concurrent-provisioning.sqlite"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    barrier = Barrier(3)
    monkeypatch.setattr(
        user_service,
        "hash_password",
        lambda password: (barrier.wait(timeout=10), "test-password-hash")[1],
    )

    def provision(index: int) -> str:
        with Session(engine) as db:
            try:
                create_user(
                    db,
                    f"concurrent-user-{index}",
                    f"Concurrent User {index}",
                    "a-concurrent-secure-password",
                )
                db.commit()
                return "created"
            except ValueError:
                db.rollback()
                return "rejected"

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            outcomes = list(executor.map(provision, range(3)))

        with Session(engine) as db:
            account_count = db.scalar(select(func.count()).select_from(User))
        assert outcomes.count("created") == 2
        assert outcomes.count("rejected") == 1
        assert account_count == 2
    finally:
        engine.dispose()

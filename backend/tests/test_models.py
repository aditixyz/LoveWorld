import pytest
from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import DailySurprise, LoginRateLimit, LoveNote, Memory, Photo, User


def test_all_initial_models_are_registered_in_metadata() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "login_rate_limits",
        "memories",
        "love_notes",
        "photos",
        "daily_surprises",
    }


def test_user_username_is_unique_and_indexed() -> None:
    assert any(
        index.name == "ix_users_username" and index.unique is True
        for index in User.__table__.indexes
    )


def test_user_account_slots_constrain_the_account_count() -> None:
    assert any(
        constraint.name == "ck_users_account_slot"
        and isinstance(constraint, CheckConstraint)
        for constraint in User.__table__.constraints
    )
    assert any(
        constraint.name == "uq_users_account_slot"
        and isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("account_slot",)
        for constraint in User.__table__.constraints
    )


def test_login_rate_limit_model_has_expiry_index_and_positive_attempts() -> None:
    assert LoginRateLimit.__table__.c.key_hash.primary_key
    assert any(
        constraint.name == "ck_login_rate_limits_attempts"
        for constraint in LoginRateLimit.__table__.constraints
    )
    assert any(
        index.name == "ix_login_rate_limits_window_started_at"
        for index in LoginRateLimit.__table__.indexes
    )


def test_photo_storage_key_is_unique() -> None:
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("storage_key",)
        for constraint in Photo.__table__.constraints
    )


def test_content_models_reference_users() -> None:
    assert Memory.__table__.c.created_by.foreign_keys
    assert LoveNote.__table__.c.created_by.foreign_keys
    assert Photo.__table__.c.uploaded_by.foreign_keys
    assert all(
        foreign_key.target_fullname == "users.id"
        for table_name in ("memories", "love_notes", "photos")
        for column in Base.metadata.tables[table_name].columns
        for foreign_key in column.foreign_keys
    )


def test_scheduled_timestamps_are_timezone_aware() -> None:
    assert isinstance(DailySurprise.__table__.c.scheduled_for.type, DateTime)
    assert DailySurprise.__table__.c.scheduled_for.type.timezone is True
    assert DailySurprise.__table__.c.delivered_at.type.timezone is True


def test_owned_resources_default_to_private_and_constrain_visibility() -> None:
    for model in (Memory, LoveNote, Photo):
        assert model.__table__.c.visibility.default.arg == "private"
        assert model.__table__.c.visibility.server_default.arg == "private"
        assert any(
            constraint.name == f"ck_{model.__tablename__}_visibility"
            for constraint in model.__table__.constraints
        )


@pytest.mark.parametrize("model", [Memory, LoveNote, Photo])
def test_owned_resource_rejects_unknown_visibility(model) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    if model is Memory:
        resource = model(title="Test", created_by=1, visibility="public")
    elif model is LoveNote:
        resource = model(content="Test", created_by=1, visibility="public")
    else:
        resource = model(
            original_filename="test.jpg",
            storage_key="test.jpg",
            uploaded_by=1,
            visibility="public",
        )

    with Session(engine) as db:
        db.add(resource)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    engine.dispose()

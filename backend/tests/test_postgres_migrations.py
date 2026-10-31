import os
import secrets
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from app.db.base import Base
from app.db import models  # noqa: F401

_DATABASE_URL_ENV = "LOVEWORLD_TEST_DATABASE_URL"
_DATABASE_URL = os.environ.get(_DATABASE_URL_ENV)


@pytest.mark.skipif(
    not _DATABASE_URL,
    reason=f"Set {_DATABASE_URL_ENV} to a dedicated PostgreSQL test database.",
)
def test_postgresql_migrations_build_model_equivalent_schema() -> None:
    assert _DATABASE_URL is not None
    url = make_url(_DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        pytest.fail(f"{_DATABASE_URL_ENV} must use PostgreSQL.")
    if not url.database or not (
        url.database == "loveworld_test"
        or url.database.startswith("loveworld_test_")
    ):
        pytest.fail(
            f"{_DATABASE_URL_ENV} database name must be loveworld_test "
            "or start with loveworld_test_."
        )

    schema = f"lw_migration_test_{secrets.token_hex(8)}"
    engine = create_engine(url)
    schema_created = False
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            schema_created = True

        with engine.connect() as connection:
            connection.exec_driver_sql(f'SET search_path TO "{schema}"')
            connection.commit()
            alembic_config = Config(
                str(Path(__file__).resolve().parents[1] / "alembic.ini")
            )
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")

            inspector = inspect(connection)
            assert set(inspector.get_table_names()) == set(Base.metadata.tables)

            user_checks = {
                constraint["name"]
                for constraint in inspector.get_check_constraints("users")
            }
            user_unique_constraints = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("users")
            }
            assert "ck_users_account_slot" in user_checks
            assert "uq_users_account_slot" in user_unique_constraints

            rate_limit_columns = {
                column["name"]
                for column in inspector.get_columns("login_rate_limits")
            }
            assert rate_limit_columns == {
                "key_hash",
                "window_started_at",
                "attempts",
            }
            rate_limit_checks = {
                constraint["name"]
                for constraint in inspector.get_check_constraints("login_rate_limits")
            }
            assert "ck_login_rate_limits_attempts" in rate_limit_checks

            migration_context = MigrationContext.configure(connection)
            assert compare_metadata(migration_context, Base.metadata) == []
    except Exception:
        pytest.fail(
            "PostgreSQL migration verification failed. Detailed database "
            "exceptions are suppressed to avoid exposing connection details."
        )
    finally:
        if schema_created:
            try:
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
                    )
            except Exception:
                pytest.fail(
                    "Could not remove the temporary migration-test schema from "
                    "the dedicated PostgreSQL test database."
                )
        engine.dispose()

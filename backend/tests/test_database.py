from unittest.mock import MagicMock, Mock

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import connectivity, session


def test_database_session_closes_when_dependency_finishes(monkeypatch) -> None:
    database_session = Mock()
    monkeypatch.setattr(session, "SessionLocal", lambda: database_session)

    dependency = session.get_db()
    assert next(dependency) is database_session

    dependency.close()

    database_session.close.assert_called_once_with()


def test_connectivity_check_executes_select_one(monkeypatch) -> None:
    database_connection = MagicMock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = database_connection
    database_engine = Mock()
    database_engine.connect.return_value = connection_context
    monkeypatch.setattr(connectivity, "engine", database_engine)

    assert connectivity.check_database_connection() is True
    database_connection.execute.assert_called_once()
    assert str(database_connection.execute.call_args.args[0]) == str(text("SELECT 1"))


def test_connectivity_check_handles_connection_failure_safely(
    monkeypatch,
) -> None:
    database_engine = Mock()
    database_engine.connect.side_effect = OperationalError(
        "connect",
        {},
        Exception("sensitive connection details"),
    )
    monkeypatch.setattr(connectivity, "engine", database_engine)

    assert connectivity.check_database_connection() is False

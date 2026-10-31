import asyncio

from httpx import ASGITransport, AsyncClient, Response

from app.db import connectivity
from app.main import app


async def _get(path: str) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_health_returns_ok() -> None:
    response = asyncio.run(_get("/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_returns_ok_when_database_is_reachable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(connectivity, "check_database_connection", lambda: True)
    response = asyncio.run(_get("/health/db"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_hides_connection_errors(monkeypatch) -> None:
    monkeypatch.setattr(connectivity, "check_database_connection", lambda: False)
    response = asyncio.run(_get("/health/db"))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "password" not in response.text.lower()


def test_health_does_not_depend_on_database(monkeypatch) -> None:
    def fail_if_checked() -> bool:
        raise AssertionError("The API health check must not query the database.")

    monkeypatch.setattr(connectivity, "check_database_connection", fail_if_checked)
    response = asyncio.run(_get("/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

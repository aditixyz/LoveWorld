from fastapi import APIRouter, Response, status

from app.db import connectivity

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def database_health_check(response: Response) -> dict[str, str]:
    if not connectivity.check_database_connection():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}

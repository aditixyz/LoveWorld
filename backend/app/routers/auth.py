import logging
import secrets
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.db.errors import log_database_error
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.login_rate_limit import (
    clear_login_attempts,
    consume_login_attempt,
)
from app.services.users import normalize_username

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    username = normalize_username(credentials.username)
    try:
        attempts = consume_login_attempt(db, username, settings)
    except SQLAlchemyError as error:
        log_database_error(logger, "auth.login_rate_limit", error)
        try:
            db.rollback()
        except SQLAlchemyError as rollback_error:
            log_database_error(
                logger,
                "auth.login_rate_limit.rollback",
                rollback_error,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        ) from None
    if attempts > settings.login_rate_limit_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(settings.login_rate_limit_window_seconds)},
        )

    try:
        user = db.scalar(select(User).where(User.username == username))
    except SQLAlchemyError as error:
        log_database_error(logger, "auth.login_user_lookup", error)
        try:
            db.rollback()
        except SQLAlchemyError as rollback_error:
            log_database_error(
                logger,
                "auth.login_user_lookup.rollback",
                rollback_error,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        ) from None
    password = credentials.password.get_secret_value()
    password_hash = user.password_hash if user is not None else _dummy_password_hash()
    password_is_valid = verify_password(password, password_hash)

    if user is None or not user.is_active or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        clear_login_attempts(db, username, settings)
    except SQLAlchemyError as error:
        log_database_error(logger, "auth.login_rate_limit_reset", error)
        try:
            db.rollback()
        except SQLAlchemyError as rollback_error:
            log_database_error(
                logger,
                "auth.login_rate_limit_reset.rollback",
                rollback_error,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        ) from None

    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=UserResponse)
def read_current_user(
    user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(user)

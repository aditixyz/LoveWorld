import secrets
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.users import normalize_username

router = APIRouter(prefix="/auth", tags=["authentication"])


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
    user = db.scalar(select(User).where(User.username == username))
    password = credentials.password.get_secret_value()
    password_hash = user.password_hash if user is not None else _dummy_password_hash()
    password_is_valid = verify_password(password, password_hash)

    if user is None or not user.is_active or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=UserResponse)
def read_current_user(
    user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(user)

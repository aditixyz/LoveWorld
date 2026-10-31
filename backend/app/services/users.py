from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.db.models import User

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
MAX_USER_COUNT = 2


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def create_user(
    db: Session,
    username: str,
    display_name: str,
    password: str,
) -> User:
    normalized_username = normalize_username(username)
    normalized_display_name = display_name.strip()
    if not 1 <= len(normalized_username) <= 50:
        raise ValueError("Username must contain between 1 and 50 characters.")
    if not 1 <= len(normalized_display_name) <= 100:
        raise ValueError("Display name must contain between 1 and 100 characters.")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must contain between {MIN_PASSWORD_LENGTH} and "
            f"{MAX_PASSWORD_LENGTH} characters."
        )
    if db.scalar(select(User.id).where(User.username == normalized_username)):
        raise ValueError("That username already exists.")
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    if user_count >= MAX_USER_COUNT:
        raise ValueError("The two-user account limit has been reached.")

    user = User(
        username=normalized_username,
        display_name=normalized_display_name,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    return user

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.db.models import User

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
MAX_USER_COUNT = 2


def _integrity_constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name:
        return constraint_name

    message = str(error.orig)
    if "users.account_slot" in message:
        return "uq_users_account_slot"
    if "users.username" in message:
        return "ix_users_username"
    return None


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
    password_hash = hash_password(password)
    for account_slot in range(1, MAX_USER_COUNT + 1):
        user = User(
            account_slot=account_slot,
            username=normalized_username,
            display_name=normalized_display_name,
            password_hash=password_hash,
        )
        try:
            with db.begin_nested():
                db.add(user)
                db.flush()
        except IntegrityError as error:
            constraint_name = _integrity_constraint_name(error)
            if constraint_name == "ix_users_username":
                raise ValueError("That username already exists.") from None
            if constraint_name == "uq_users_account_slot":
                continue
            raise
        return user

    raise ValueError("The two-user account limit has been reached.")

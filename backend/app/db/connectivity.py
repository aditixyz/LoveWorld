from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


def check_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True

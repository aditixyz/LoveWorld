import logging

from sqlalchemy.exc import SQLAlchemyError


def log_database_error(
    logger: logging.Logger,
    operation: str,
    error: SQLAlchemyError,
) -> None:
    logger.error(
        "Database operation failed (operation=%s, exception_type=%s)",
        operation,
        type(error).__name__,
    )

"""SQLAlchemy models for LoveWorld's initial database schema."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

metadata = Base.metadata


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_username", "username", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        default=True,
        server_default="true",
        nullable=False,
    )


class Memory(TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'shared')",
            name="ck_memories_visibility",
        ),
        Index("ix_memories_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(10),
        default="private",
        server_default="private",
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    @property
    def owner_id(self) -> int:
        return self.created_by

    @owner_id.setter
    def owner_id(self, user_id: int) -> None:
        self.created_by = user_id


class LoveNote(TimestampMixin, Base):
    __tablename__ = "love_notes"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'shared')",
            name="ck_love_notes_visibility",
        ),
        Index("ix_love_notes_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(10),
        default="private",
        server_default="private",
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    @property
    def owner_id(self) -> int:
        return self.created_by

    @owner_id.setter
    def owner_id(self, user_id: int) -> None:
        self.created_by = user_id


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'shared')",
            name="ck_photos_visibility",
        ),
        UniqueConstraint("storage_key", name="uq_photos_storage_key"),
        Index("ix_photos_uploaded_by", "uploaded_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(10),
        default="private",
        server_default="private",
        nullable=False,
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    @property
    def owner_id(self) -> int:
        return self.uploaded_by

    @owner_id.setter
    def owner_id(self, user_id: int) -> None:
        self.uploaded_by = user_id


class DailySurprise(Base):
    __tablename__ = "daily_surprises"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered', 'cancelled')",
            name="ck_daily_surprises_status",
        ),
        Index("ix_daily_surprises_scheduled_for", "scheduled_for"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

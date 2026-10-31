from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://localhost/loveworld"
    app_environment: Literal["development", "test", "production"] = "development"
    photo_storage_dir: Path = Path("var/photo-storage")
    photo_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        le=100 * 1024 * 1024,
    )
    jwt_secret: SecretStr = SecretStr(
        "local-development-only-secret-not-for-production"
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    login_rate_limit_attempts: int = Field(default=5, gt=0, le=100)
    login_rate_limit_window_seconds: int = Field(default=900, gt=0, le=86400)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        if self.app_environment == "production":
            secret = self.jwt_secret.get_secret_value()
            if (
                "jwt_secret" not in self.model_fields_set
                or len(secret) < 32
                or "development" in secret.lower()
                or "placeholder" in secret.lower()
                or "change-me" in secret.lower()
                or "replace-" in secret.lower()
                or "local-secret" in secret.lower()
            ):
                raise ValueError(
                    "Production requires a configured JWT_SECRET with at least "
                    "32 characters that is not a development placeholder."
                )
        return self

    @property
    def database_url_is_configured(self) -> bool:
        return "database_url" in self.model_fields_set


@lru_cache
def get_settings() -> Settings:
    return Settings()

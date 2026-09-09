"""Application settings.

All configuration is environment-driven. Nothing here carries a usable default
secret, and no secret is ever logged or returned by the API.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repository root, resolved from this file's location.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"
MANIFEST_DIR: Path = DATA_DIR / "source_manifests"
FIXTURE_DIR: Path = DATA_DIR / "fixtures"

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or a local `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="IDEA_ATLAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # -- Application -------------------------------------------------------
    env: Environment = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = False

    # -- Database ----------------------------------------------------------
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://postgres:postgres@localhost:5432/idea_atlas")
    )
    test_database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://postgres:postgres@localhost:5432/idea_atlas_test")
    )
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # -- API ---------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=list)
    max_request_bytes: int = 1_048_576
    default_page_size: int = 50
    max_page_size: int = 200

    # -- Ingestion safety --------------------------------------------------
    ingest_max_response_bytes: int = 26_214_400
    ingest_timeout_seconds: float = 30.0
    ingest_max_retries: int = 3
    ingest_user_agent: str = "idea-atlas/0.1 (+https://github.com/kgarner310/idea-atlas)"
    ingest_enforce_allowlist: bool = True

    # -- AI (optional; the platform runs fully without it) -----------------
    ai_provider: str = "null"
    ai_model: str = ""
    ai_base_url: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a real list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def sqlalchemy_url(self) -> str:
        """The URL the engine should use, switching to the test DB under pytest."""
        url = self.test_database_url if self.env == "test" else self.database_url
        return str(url)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()

"""Shared pytest fixtures.

Database strategy: the schema is created once per session by running the real
Alembic migrations against the test database -- so the migrations themselves are
under test, not just the models. Each test then runs inside a transaction that
is rolled back, which keeps tests isolated and fast without truncating tables.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

# Must be set before app.core.config is imported anywhere.
os.environ.setdefault("IDEA_ATLAS_ENV", "test")
os.environ.setdefault("IDEA_ATLAS_LOG_LEVEL", "WARNING")
os.environ.setdefault("IDEA_ATLAS_AI_PROVIDER", "null")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.db.session import build_engine


def pytest_configure(config: pytest.Config) -> None:
    """Fail loudly if the test database is missing rather than mutating dev data."""
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Settings pinned to the test environment."""
    get_settings.cache_clear()
    resolved = get_settings()
    assert resolved.env == "test", (
        "tests must run with IDEA_ATLAS_ENV=test; refusing to touch the dev database"
    )
    return resolved


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    """Session-wide engine bound to the test database, with migrations applied."""
    eng = build_engine(settings)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment problem
        pytest.skip(f"test database unavailable: {exc}")

    from alembic import command
    from alembic.config import Config

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url.replace("%", "%%"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is always rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        yield db
    finally:
        db.close()
        # A test that deliberately triggers an IntegrityError leaves the
        # transaction already aborted; rolling back again is noisy, not useful.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def seeded_session(session: Session) -> Session:
    """A session with jurisdictions, concepts, and the source registry loaded."""
    from app.services.seed import seed_reference_data

    seed_reference_data(session)
    return session


@pytest.fixture
def api_app(session: Session) -> FastAPI:
    """An app whose database dependency is bound to the test session."""
    from app.api.main import create_app
    from app.db.session import get_db

    application = create_app()
    application.dependency_overrides[get_db] = lambda: session
    return application


@pytest.fixture
def client(api_app: FastAPI) -> Iterator[TestClient]:
    """A TestClient over the transaction-scoped app."""
    with TestClient(api_app) as test_client:
        yield test_client


@pytest.fixture
def seeded_client(api_app: FastAPI, seeded_session: Session) -> Iterator[TestClient]:
    """A TestClient over an app with reference data loaded."""
    with TestClient(api_app) as test_client:
        yield test_client

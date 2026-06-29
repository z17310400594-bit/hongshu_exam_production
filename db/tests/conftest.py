"""Database test fixtures — use isolated test database, never dev data."""

from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings

TEST_DB_NAME = "knowledge_platform_v2_test"


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Build a test-database URL by swapping the DB name from the dev settings."""
    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path=TEST_DB_NAME)
    return urlunparse(parsed)


@pytest.fixture(scope="session")
def engine(test_db_url: str) -> Generator[Engine, None, None]:
    """Create the test database, yield an engine, drop the test database on teardown."""
    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME} OWNER {settings.db_user}"))
    admin_engine.dispose()

    engine = create_engine(test_db_url, pool_size=1)
    yield engine
    engine.dispose()

    # Cleanup
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin_engine.dispose()


@pytest.fixture(scope="function")
def connection(engine: Engine):
    """Provide a connection that rolls back after each test."""
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


@pytest.fixture(scope="session")
def alembic_cfg(test_db_url: str) -> AlembicConfig:
    """Alembic configuration pointing to the isolated test database."""
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    return cfg

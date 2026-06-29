"""Database test fixtures."""

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings


@pytest.fixture(scope="session")
def engine() -> Engine:
    """Create a test database engine."""
    return create_engine(settings.database_url, pool_size=1)


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
def alembic_cfg() -> AlembicConfig:
    """Alembic configuration object for programmatic migration tests."""
    cfg = AlembicConfig("alembic.ini")
    # Prevent prompting for env.py; run in online mode
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg

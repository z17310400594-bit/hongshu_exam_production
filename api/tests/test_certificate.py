"""WP03 certificate service tests — lookup, alias, old-id mapping."""

import pytest
from sqlalchemy import create_engine, text

from api.config import settings
from api.services.certificate import (
    list_certificates,
    lookup_by_code,
    lookup_by_normalized_alias,
)
from db.tests.fixtures_wp03 import seed_fixtures


@pytest.fixture(scope="module")
def engine():
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path="knowledge_platform_v2_test")
    test_url = urlunparse(parsed)

    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
        conn.execute(text(f"CREATE DATABASE knowledge_platform_v2_test OWNER {settings.db_user}"))
    admin_engine.dispose()

    eng = create_engine(test_url)

    from alembic import command
    from alembic.config import Config as AlembicConfig
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(cfg, "head")

    seed_fixtures(eng)

    yield eng
    eng.dispose()


# ── exact code lookup ───────────────────────────────────────────

def test_lookup_by_code_exact(engine):
    cert = lookup_by_code(engine, "c_constructor_1")
    assert cert is not None
    assert cert["name"] == "First-Class Constructor"


def test_lookup_by_code_missing_returns_none(engine):
    assert lookup_by_code(engine, "nonexistent") is None


# ── alias lookup ────────────────────────────────────────────────

def test_lookup_by_normalized_alias(engine):
    cert = lookup_by_normalized_alias(engine, "cls1_constructor")
    assert cert is not None
    assert cert["code"] == "c_constructor_1"


def test_alias_unknown_returns_none(engine):
    assert lookup_by_normalized_alias(engine, "unknown_alias") is None


def test_list_returns_all_certs(engine):
    certs = list_certificates(engine)
    assert len(certs) >= 5

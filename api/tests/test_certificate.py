"""WP03 certificate service tests — lookup, alias, old-id mapping."""

import pytest
from sqlalchemy import create_engine, text

from api.config import settings
from api.services.certificate import (
    build_old_cert_mapping,
    list_certificates,
    lookup_by_alias,
    lookup_by_code,
    lookup_by_name,
    lookup_by_normalized_alias,
    normalize_alias,
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

    # Cleanup: drop test database
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
    admin_engine.dispose()


# ── alias normalization ──────────────────────────────────────────

def test_normalize_alias_lowercases_and_strips():
    assert normalize_alias("  一建  ") == "一建"
    assert normalize_alias("CLS1_CONSTRUCTOR") == "cls1_constructor"


# ── exact code lookup ───────────────────────────────────────────

def test_lookup_by_code_exact(engine):
    cert = lookup_by_code(engine, "c_constructor_1")
    assert cert is not None
    assert cert["name"] == "First-Class Constructor"


def test_lookup_by_code_missing_returns_none(engine):
    assert lookup_by_code(engine, "nonexistent") is None


# ── exact name lookup ────────────────────────────────────────────

def test_lookup_by_name_exact(engine):
    cert = lookup_by_name(engine, "First-Class Constructor")
    assert cert is not None
    assert cert["code"] == "c_constructor_1"


def test_lookup_by_name_missing_returns_none(engine):
    assert lookup_by_name(engine, "No Such Certificate") is None


# ── raw alias lookup ─────────────────────────────────────────────

def test_lookup_by_alias_raw(engine):
    """Raw alias '一建' is normalized and resolved via certificate_alias."""
    cert = lookup_by_alias(engine, "一建")
    assert cert is not None
    assert cert["code"] == "c_constructor_1"


def test_lookup_by_alias_case_insensitive(engine):
    cert = lookup_by_alias(engine, "CLS1_CONSTRUCTOR")
    assert cert is not None
    assert cert["code"] == "c_constructor_1"


# ── normalized alias lookup ──────────────────────────────────────

def test_lookup_by_normalized_alias(engine):
    cert = lookup_by_normalized_alias(engine, "cls1_constructor")
    assert cert is not None
    assert cert["code"] == "c_constructor_1"


def test_alias_unknown_returns_none(engine):
    assert lookup_by_normalized_alias(engine, "unknown_alias") is None


# ── old cert ID mapping ──────────────────────────────────────────

def test_old_cert_mapping_finds_mapped(engine):
    mapping = build_old_cert_mapping(engine)
    entry = mapping.get("cls1_constructor")
    assert entry["status"] == "mapped"
    assert entry["v2_code"] == "c_constructor_1"


def test_old_cert_mapping_unknown_is_needs_review(engine):
    mapping = build_old_cert_mapping(engine)
    entry = mapping.get("cls_nonexistent")
    assert entry["status"] == "needs_review"


def test_old_cert_mapping_all_returns_list(engine):
    mapping = build_old_cert_mapping(engine)
    entries = mapping.all()
    assert isinstance(entries, list)
    assert len(entries) >= 4  # one mapped entry per fixture cert


def test_old_cert_mapping_rejects_bad_status():
    from api.services.certificate import OldCertMapping
    m = OldCertMapping()
    with pytest.raises(AssertionError):
        m.add("x", "invalid_status")


def test_list_returns_all_certs(engine):
    certs = list_certificates(engine)
    assert len(certs) >= 5

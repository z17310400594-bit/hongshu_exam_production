"""WP02 authorization tests — ACL matrix, 403, leak prevention."""

import pytest
from sqlalchemy import create_engine, text

from api.auth import AuthorizationError, check_collection_access
from api.config import settings
from db.tests.fixtures_wp02 import seed_fixtures


@pytest.fixture(scope="module")
def engine():
    """Sync engine pointed at the test database with WP02 fixtures seeded."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path="knowledge_platform_v2_test")
    test_url = urlunparse(parsed)

    # Create test database
    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
        conn.execute(text("CREATE DATABASE knowledge_platform_v2_test OWNER v2_user"))
    admin_engine.dispose()

    eng = create_engine(test_url)

    # Apply all migrations
    from alembic import command
    from alembic.config import Config as AlembicConfig
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(cfg, "head")

    seed_fixtures(eng)

    yield eng
    eng.dispose()


# ── authorization matrix ────────────────────────────────────────

def test_teaching_materials_can_read_internal_collection(engine):
    check_collection_access(engine, "org", "org_teaching_materials", "coll_internal")


def test_teaching_materials_can_read_public_collection(engine):
    check_collection_access(engine, "org", "org_teaching_materials", "coll_public")


def test_operations_cannot_read_restricted_collection(engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(engine, "org", "org_operations", "coll_restricted")
    assert exc.value.status_code == 403


def test_operations_cannot_read_internal_collection(engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(engine, "org", "org_operations", "coll_internal")
    assert exc.value.status_code == 403


def test_unknown_org_denied(engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(engine, "org", "org_nonexistent", "coll_public")
    assert exc.value.status_code == 403


def test_unknown_collection_denied(engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(engine, "org", "org_teaching_materials", "coll_nonexistent")
    assert exc.value.status_code == 403


# ── leak prevention ─────────────────────────────────────────────

def test_403_detail_does_not_leak_collection_name(engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(engine, "org", "org_operations", "coll_restricted")
    detail = exc.value.detail.lower()
    assert "restricted" not in detail
    assert "answer" not in detail
    assert "collection" not in detail
    assert "coll_" not in detail


def test_403_detail_does_not_leak_internal_ids(engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(engine, "org", "org_operations", "coll_internal")
    detail = exc.value.detail.lower()
    for forbidden in ["id", "key", "code", "confidentiality"]:
        assert forbidden not in detail, f"leaked '{forbidden}' in: {detail}"

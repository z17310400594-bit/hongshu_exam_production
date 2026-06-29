"""WP02 authorization tests — function-level + HTTP-level, leak prevention."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from api.auth import AuthorizationError, check_collection_access
from api.config import settings
from db.tests.fixtures_wp02 import seed_fixtures


@pytest.fixture(scope="module")
def sync_engine():
    """Sync engine pointed at the test database with WP02 fixtures seeded."""
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


@pytest.fixture
def client(sync_engine):
    """Return an async httpx client against the FastAPI app, with the test sync engine."""
    import api.main
    original = api.main.sync_engine
    api.main.sync_engine = sync_engine

    transport = ASGITransport(app=api.main.app)
    client = AsyncClient(transport=transport, base_url="http://test")

    yield client

    api.main.sync_engine = original


# ── function-level authorization matrix ───────────────────────

def test_teaching_materials_can_read_internal(sync_engine):
    check_collection_access(sync_engine, "org", "org_teaching_materials", "coll_internal")


def test_teaching_materials_can_read_public(sync_engine):
    check_collection_access(sync_engine, "org", "org_teaching_materials", "coll_public")


def test_operations_cannot_read_restricted(sync_engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(sync_engine, "org", "org_operations", "coll_restricted")
    assert exc.value.status_code == 403


def test_operations_cannot_read_internal(sync_engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(sync_engine, "org", "org_operations", "coll_internal")
    assert exc.value.status_code == 403


def test_unknown_org_denied(sync_engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(sync_engine, "org", "org_nonexistent", "coll_public")
    assert exc.value.status_code == 403


def test_unknown_collection_denied(sync_engine):
    with pytest.raises(AuthorizationError) as exc:
        check_collection_access(sync_engine, "org", "org_teaching_materials", "coll_nonexistent")
    assert exc.value.status_code == 403


# ── HTTP-level protected route ─────────────────────────────────

@pytest.mark.asyncio
async def test_http_allowed_returns_200(client: AsyncClient):
    resp = await client.get("/collections/coll_internal", headers={"X-Org-Code": "org_teaching_materials"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["collection"] == "coll_internal"


@pytest.mark.asyncio
async def test_http_denied_returns_403(client: AsyncClient):
    resp = await client.get("/collections/coll_restricted", headers={"X-Org-Code": "org_operations"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_http_missing_header_returns_401(client: AsyncClient):
    resp = await client.get("/collections/coll_public")
    assert resp.status_code == 401


# ── HTTP leak prevention (response body) ───────────────────────

@pytest.mark.asyncio
async def test_403_response_does_not_leak_collection_info(client: AsyncClient):
    resp = await client.get("/collections/coll_restricted", headers={"X-Org-Code": "org_operations"})
    assert resp.status_code == 403
    body = resp.json()
    detail = body.get("detail", "").lower()
    for forbidden in ["restricted", "answer", "collection", "coll_", "id", "confidentiality"]:
        assert forbidden not in detail, f"leaked '{forbidden}' in response: {detail}"


@pytest.mark.asyncio
async def test_403_does_not_log_collection_name(client: AsyncClient, caplog):
    """Authorization failures must not log collection names or internal data."""
    with caplog.at_level(logging.WARNING):
        await client.get("/collections/coll_restricted", headers={"X-Org-Code": "org_operations"})
    for record in caplog.records:
        msg = record.getMessage().lower()
        for forbidden in ["restricted", "answer", "coll_"]:
            assert forbidden not in msg, f"logged '{forbidden}' in: {msg}"

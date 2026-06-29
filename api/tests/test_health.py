"""Health endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    """Return an async httpx client against the FastAPI app."""
    from api.main import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_live_returns_ok(client: AsyncClient):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_returns_connected_when_db_reachable(client: AsyncClient):
    """With the event-loop fix, the async engine should connect to the running dev database."""
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


@pytest.mark.asyncio
async def test_ready_returns_503_when_db_unreachable(client: AsyncClient, monkeypatch):
    """When the async engine raises an exception, readiness returns 503."""
    import api.main

    async def bad_session_factory(_engine):
        raise OSError("Connection refused")

    monkeypatch.setattr(api.main, "AsyncSession", bad_session_factory)

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["database"] == "disconnected"

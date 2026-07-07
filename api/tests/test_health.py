"""Health endpoint tests."""

from unittest.mock import MagicMock

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
    """The sync engine connects without event-loop issues."""
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


@pytest.mark.asyncio
async def test_ready_returns_503_when_db_unreachable(client: AsyncClient, monkeypatch):
    """When the sync engine raises an exception, readiness returns 503."""
    import api.main

    mock_engine = MagicMock()
    mock_engine.__enter__ = MagicMock(side_effect=OSError("Connection refused"))
    monkeypatch.setattr(api.main.sync_engine, "connect", MagicMock(return_value=mock_engine))

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["database"] == "disconnected"

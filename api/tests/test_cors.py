"""CORS tests for local and LAN frontend development origins."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    from api.main import app

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:10086",
        "http://127.0.0.1:10086",
        "http://192.168.1.223:10086",
    ],
)
async def test_frontend_dev_origins_can_preflight_v2_api(client: AsyncClient, origin: str):
    response = await client.options(
        "/api/v2/certificates?limit=50",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-org-code,x-request-id,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin

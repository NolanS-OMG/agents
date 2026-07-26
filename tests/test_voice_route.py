import pytest
from httpx import ASGITransport, AsyncClient

from src.app.main import app


@pytest.mark.anyio
async def test_incoming_call_returns_twiml() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/incoming-call")

    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    body = resp.text
    assert "<Response>" in body
    assert "<Say" in body
    assert "<Connect>" in body
    assert "<Stream" in body
    assert "ws://test/ws/media-stream" in body

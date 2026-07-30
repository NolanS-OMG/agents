import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from src.app.db.models import ApiKey, Event, Tenant
from src.app.main import app

API_KEY = "sk_test_us_usage123"


async def _setup_db() -> None:
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()
    tenant = await Tenant.create(id="usage_test", name="Usage Test")
    await ApiKey.create(
        tenant=tenant,
        key_hash=hashlib.sha256(API_KEY.encode()).hexdigest(),
        key_prefix="sk_test_us_",
    )


async def _teardown_db() -> None:
    await Tortoise.close_connections()


@pytest.mark.anyio
async def test_usage_empty() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/usage",
                params={"from": "2026-07-01", "to": "2026-07-31"},
                headers={"X-API-Key": API_KEY},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "usage_test"
        assert data["totals"]["llm_calls"] == 0
        assert data["totals"]["total_cost_usd"] == 0.0
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_usage_with_events() -> None:
    await _setup_db()
    try:
        await Event.create(
            tenant_id="usage_test", event_type="llm_call", provider="openrouter",
            model="llama-3.3-70b", input_tokens=500, output_tokens=100,
            latency_ms=800, cost_usd=0.001,
        )
        await Event.create(
            tenant_id="usage_test", event_type="stt", provider="groq",
            audio_duration_s=5.2, latency_ms=300,
        )
        await Event.create(
            tenant_id="usage_test", event_type="tts", provider="edge_tts",
            characters=150, latency_ms=200,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/usage",
                params={"from": "2026-07-01", "to": "2026-12-31"},
                headers={"X-API-Key": API_KEY},
            )
        assert resp.status_code == 200
        totals = resp.json()["totals"]
        assert totals["llm_calls"] == 1
        assert totals["tokens_in"] == 500
        assert totals["tokens_out"] == 100
        assert totals["stt_calls"] == 1
        assert totals["stt_seconds"] == pytest.approx(5.2, abs=0.01)
        assert totals["tts_calls"] == 1
        assert totals["tts_characters"] == 150
        assert totals["total_cost_usd"] == pytest.approx(0.001, abs=0.0001)
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_usage_requires_auth() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/usage",
            params={"from": "2026-07-01", "to": "2026-07-31"},
        )
    assert resp.status_code == 401

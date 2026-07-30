import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from src.app.db.models import ApiKey, Tenant
from src.app.main import app


async def _setup_db() -> None:
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()


async def _teardown_db() -> None:
    await Tortoise.close_connections()


async def _create_test_tenant_and_key() -> str:
    tenant = await Tenant.create(id="test_tenant", name="Test Tenant")
    raw_key = "sk_test_te_abc123def456xyz"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    await ApiKey.create(
        tenant=tenant,
        key_hash=key_hash,
        key_prefix="sk_test_te_",
        scopes=["converse", "knowledge"],
    )
    return raw_key


@pytest.mark.anyio
async def test_excluded_path_no_auth_required() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/incoming-call")
    # Should pass auth (not 401) — route is excluded
    assert resp.status_code != 401


@pytest.mark.anyio
async def test_missing_api_key_returns_401() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/converse", json={"message": "hola"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "API key required"


@pytest.mark.anyio
async def test_invalid_api_key_returns_401() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/converse",
                json={"message": "hola"},
                headers={"X-API-Key": "sk_invalid_key_that_doesnt_exist"},
            )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key"
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_valid_api_key_passes_auth() -> None:
    await _setup_db()
    try:
        raw_key = await _create_test_tenant_and_key()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/converse",
                json={"message": "hola"},
                headers={"X-API-Key": raw_key},
            )
        # Should NOT be 401 — auth passed. May be 404 (route doesn't exist yet) or other error.
        assert resp.status_code != 401
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_inactive_key_returns_401() -> None:
    await _setup_db()
    try:
        tenant = await Tenant.create(id="inactive_t", name="Inactive")
        raw_key = "sk_inacti_disabled_key_xyz"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        await ApiKey.create(
            tenant=tenant,
            key_hash=key_hash,
            key_prefix="sk_inacti_",
            active=False,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/converse",
                json={"message": "hola"},
                headers={"X-API-Key": raw_key},
            )
        assert resp.status_code == 401
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_webhook_excluded_from_auth() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook/whatsapp/some_tenant",
            json={"entry": []},
        )
    # Should not be 401 — webhook is excluded from auth
    assert resp.status_code != 401

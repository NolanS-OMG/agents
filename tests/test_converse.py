import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from src.app.db.models import ApiKey, KnowledgeDocument, Tenant, TenantPrompt
from src.app.main import app

API_KEY = "sk_test_cv_converse123"


async def _setup_db() -> None:
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()
    tenant = await Tenant.create(id="cv_test", name="Converse Test")
    await ApiKey.create(
        tenant=tenant,
        key_hash=hashlib.sha256(API_KEY.encode()).hexdigest(),
        key_prefix="sk_test_cv_",
    )
    await KnowledgeDocument.create(
        tenant_id="cv_test", slug="negocio/info-general", doc_type="negocio",
        title="Info General", body="Restaurante de prueba. Horario: 4pm-12am.",
    )
    await TenantPrompt.create(
        tenant_id="cv_test", estilo="chat",
        system_prompt="Eres un asistente amable de un restaurante.",
    )


async def _teardown_db() -> None:
    await Tortoise.close_connections()


@pytest.mark.anyio
async def test_converse_text_missing_fields_returns_400() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/converse",
                data={"conversant_id": "user1"},
                headers={"X-API-Key": API_KEY},
            )
        assert resp.status_code == 400
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_converse_no_auth_returns_401() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/converse",
            data={"conversant_id": "user1", "message": "hola"},
        )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_converse_invalid_response_format_returns_400() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/converse",
                data={
                    "conversant_id": "user1",
                    "message": "hola",
                    "response_format": "invalid",
                },
                headers={"X-API-Key": API_KEY},
            )
        assert resp.status_code == 400
    finally:
        await _teardown_db()

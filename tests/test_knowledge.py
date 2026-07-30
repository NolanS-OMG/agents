import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from src.app.db.models import ApiKey, KnowledgeDocument, Tenant, TenantPrompt
from src.app.main import app

API_KEY = "sk_test_kb_abc123xyz"


async def _setup_db() -> None:
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()
    tenant = await Tenant.create(id="kb_test", name="KB Test")
    await ApiKey.create(
        tenant=tenant,
        key_hash=hashlib.sha256(API_KEY.encode()).hexdigest(),
        key_prefix="sk_test_kb_",
    )


async def _teardown_db() -> None:
    await Tortoise.close_connections()


@pytest.mark.anyio
async def test_create_and_list_document() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/knowledge",
                json={
                    "slug": "menu/tacos",
                    "doc_type": "menu",
                    "title": "Tacos",
                    "body": "# Tacos\n\n| Taco | Precio |\n|---|---|\n| Pastor | $25 |",
                },
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["slug"] == "menu/tacos"
            assert data["doc_type"] == "menu"

            resp = await client.get(
                "/api/v1/knowledge",
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 200
            docs = resp.json()
            assert len(docs) == 1
            assert docs[0]["slug"] == "menu/tacos"
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_get_document_by_slug() -> None:
    await _setup_db()
    try:
        await KnowledgeDocument.create(
            tenant_id="kb_test", slug="menu/pizzas", doc_type="menu",
            title="Pizzas", body="# Pizzas",
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/knowledge/menu/pizzas",
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 200
            assert resp.json()["title"] == "Pizzas"
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_update_document() -> None:
    await _setup_db()
    try:
        await KnowledgeDocument.create(
            tenant_id="kb_test", slug="negocio/info", doc_type="negocio",
            title="Info", body="Horario: 4pm-12am",
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/v1/knowledge/negocio/info",
                json={"body": "Horario: 3pm-1am"},
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 200
            assert resp.json()["body"] == "Horario: 3pm-1am"
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_delete_document_soft() -> None:
    await _setup_db()
    try:
        await KnowledgeDocument.create(
            tenant_id="kb_test", slug="menu/old", doc_type="menu",
            title="Old", body="...",
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                "/api/v1/knowledge/menu/old",
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 204

            doc = await KnowledgeDocument.get(tenant_id="kb_test", slug="menu/old")
            assert doc.status == "archived"
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_create_and_list_prompt() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/prompts",
                json={
                    "estilo": "chat",
                    "system_prompt": "Eres un asistente amable.",
                    "tono": "Mexicano",
                },
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 201
            assert resp.json()["estilo"] == "chat"

            resp = await client.get(
                "/api/v1/prompts",
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 200
            assert len(resp.json()) == 1
    finally:
        await _teardown_db()


@pytest.mark.anyio
async def test_document_not_found_returns_404() -> None:
    await _setup_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/knowledge/nonexistent/doc",
                headers={"X-API-Key": API_KEY},
            )
            assert resp.status_code == 404
    finally:
        await _teardown_db()

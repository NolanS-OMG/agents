import pytest
from tortoise import Tortoise

from src.app.db.models import ApiKey, KnowledgeDocument, Tenant, TenantPrompt

DB_CONFIG = {
    "db_url": "sqlite://:memory:",
    "modules": {"models": ["src.app.db.models"]},
}


async def _setup() -> None:
    await Tortoise.init(**DB_CONFIG)
    await Tortoise.generate_schemas()


async def _teardown() -> None:
    await Tortoise.close_connections()


@pytest.mark.anyio
async def test_create_tenant() -> None:
    await _setup()
    try:
        tenant = await Tenant.create(id="santa_lena", name="Santa Leña")
        assert tenant.id == "santa_lena"
        assert tenant.name == "Santa Leña"
        assert tenant.active is True
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_create_api_key_linked_to_tenant() -> None:
    await _setup()
    try:
        tenant = await Tenant.create(id="t1", name="Tenant 1")
        key = await ApiKey.create(tenant=tenant, key_hash="abc123", key_prefix="sk_t1_")
        assert key.tenant_id == "t1"

        keys = await ApiKey.filter(tenant=tenant)
        assert len(keys) == 1
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_knowledge_document_unique_slug_per_tenant() -> None:
    from tortoise.exceptions import IntegrityError

    await _setup()
    try:
        tenant = await Tenant.create(id="t2", name="T2")
        await KnowledgeDocument.create(
            tenant=tenant, slug="menu/hamburguesas", doc_type="menu",
            title="Hamburguesas", body="# Hamburguesas",
        )
        with pytest.raises(IntegrityError):
            await KnowledgeDocument.create(
                tenant=tenant, slug="menu/hamburguesas", doc_type="menu",
                title="Dup", body="# Dup",
            )
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_tenant_prompt_unique_estilo_per_tenant() -> None:
    from tortoise.exceptions import IntegrityError

    await _setup()
    try:
        tenant = await Tenant.create(id="t3", name="T3")
        await TenantPrompt.create(
            tenant=tenant, estilo="chat", system_prompt="Eres amable.",
        )
        with pytest.raises(IntegrityError):
            await TenantPrompt.create(
                tenant=tenant, estilo="chat", system_prompt="Dup.",
            )
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_same_slug_different_tenant_allowed() -> None:
    await _setup()
    try:
        t1 = await Tenant.create(id="t4", name="T4")
        t2 = await Tenant.create(id="t5", name="T5")
        await KnowledgeDocument.create(
            tenant=t1, slug="menu/pizzas", doc_type="menu", title="P1", body="...",
        )
        doc2 = await KnowledgeDocument.create(
            tenant=t2, slug="menu/pizzas", doc_type="menu", title="P2", body="...",
        )
        assert doc2.tenant_id == "t5"
    finally:
        await _teardown()

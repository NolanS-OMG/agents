import hashlib
import json

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from src.app.db.models import ApiKey, Tenant
from src.app.main import app
from src.app.services.metrics import MetricsCollector
from tests.conftest import make_llm_response

TEST_KEY = "sk_test_chat_key_12345"


async def _setup() -> None:
    app.state.metrics = MetricsCollector()
    app.state.redis = None
    app.state.http_client = AsyncClient()
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()
    tenant = await Tenant.create(id="test_tenant", name="Test")
    key_hash = hashlib.sha256(TEST_KEY.encode()).hexdigest()
    await ApiKey.create(
        tenant=tenant,
        key_hash=key_hash,
        key_prefix="sk_test_ch_",
        scopes=["converse", "knowledge", "conversations"],
    )


async def _teardown() -> None:
    await Tortoise.close_connections()
    await app.state.http_client.aclose()


@pytest.mark.anyio
async def test_chat_endpoint_returns_response(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    await _setup()
    try:
        httpx_mock.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            method="POST",
            json=make_llm_response(content="Hola, ¿cómo puedo ayudarte?").json(),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "test-session-1", "message": "Hola"},
                headers={"X-API-Key": TEST_KEY},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-1"
        assert "Hola" in data["response"] or "ayudar" in data["response"]
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_chat_endpoint_with_tool_call(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    await _setup()
    try:
        httpx_mock.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            method="POST",
            json=make_llm_response(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "consultar_informacion_negocio",
                            "arguments": json.dumps({"consulta": "horarios"}),
                        },
                    }
                ],
            ).json(),
        )
        httpx_mock.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            method="POST",
            json=make_llm_response(content="El horario es de 9 a 18h.").json(),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "test-session-2", "message": "¿Cuál es el horario?"},
                headers={"X-API-Key": TEST_KEY},
            )

        assert response.status_code == 200
        assert "horario" in response.json()["response"].lower() or "18" in response.json()["response"]
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_chat_endpoint_validates_empty_message() -> None:
    await _setup()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "test-session", "message": ""},
                headers={"X-API-Key": TEST_KEY},
            )
        assert response.status_code == 422
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_chat_endpoint_validates_empty_session_id() -> None:
    await _setup()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "", "message": "Hola"},
                headers={"X-API-Key": TEST_KEY},
            )
        assert response.status_code == 422
    finally:
        await _teardown()


@pytest.mark.anyio
async def test_chat_requires_auth() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={"session_id": "x", "message": "Hola"},
        )
    assert response.status_code == 401

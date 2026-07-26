import json

import pytest
from httpx import AsyncClient

from tests.conftest import make_sse_response


@pytest.mark.anyio
async def test_chat_endpoint_returns_response(client: AsyncClient, httpx_mock) -> None:  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        method="POST",
        content=make_sse_response(content="Hola, ¿cómo puedo ayudarte?").text.encode(),
    )

    response = await client.post("/api/v1/chat", json={
        "session_id": "test-session-1",
        "message": "Hola",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session-1"
    assert "Hola" in data["response"] or "ayudar" in data["response"]


@pytest.mark.anyio
async def test_chat_endpoint_with_tool_call(client: AsyncClient, httpx_mock) -> None:  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        method="POST",
        content=make_sse_response(
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "consultar_informacion_negocio",
                    "arguments": json.dumps({"consulta": "horarios"}),
                },
            }],
        ).text.encode(),
    )
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        method="POST",
        content=make_sse_response(content="El horario es de 9 a 18h.").text.encode(),
    )

    response = await client.post("/api/v1/chat", json={
        "session_id": "test-session-2",
        "message": "¿Cuál es el horario?",
    })

    assert response.status_code == 200
    assert "horario" in response.json()["response"].lower() or "18" in response.json()["response"]


@pytest.mark.anyio
async def test_chat_endpoint_validates_empty_message(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat", json={
        "session_id": "test-session",
        "message": "",
    })

    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_endpoint_validates_empty_session_id(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat", json={
        "session_id": "",
        "message": "Hola",
    })

    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_preserves_session_history(client: AsyncClient, httpx_mock) -> None:  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        method="POST",
        content=make_sse_response(content="Primera respuesta").text.encode(),
    )
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        method="POST",
        content=make_sse_response(content="Segunda respuesta").text.encode(),
    )

    await client.post("/api/v1/chat", json={
        "session_id": "persistent-session",
        "message": "Primer mensaje",
    })
    await client.post("/api/v1/chat", json={
        "session_id": "persistent-session",
        "message": "Segundo mensaje",
    })

    second_request = httpx_mock.get_requests()[-1]
    body = json.loads(second_request.content)
    messages_content = [m["content"] for m in body["messages"]]
    assert any("Primer mensaje" in c for c in messages_content)

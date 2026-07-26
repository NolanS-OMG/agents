import json
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from src.app.main import app
from src.app.services.analytics import AnalyticsStore
from src.app.services.metrics import MetricsCollector


@pytest.fixture
async def redis() -> FakeRedis:  # type: ignore[misc]
    return FakeRedis()


@pytest.fixture
async def client(redis: FakeRedis) -> AsyncClient:  # type: ignore[misc]
    app.state.redis = redis
    app.state.http_client = AsyncClient()
    app.state.metrics = MetricsCollector()
    app.state.analytics = AnalyticsStore(Path(tempfile.mktemp(suffix=".db")))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]
    await app.state.http_client.aclose()


def make_sse_response(
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    model: str = "test-model",
    usage: dict[str, Any] | None = None,
) -> httpx.Response:
    chunks: list[str] = []
    gen_id = "gen-test-123"

    if content:
        chunk = {
            "id": gen_id,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
        }
        chunks.append(f"data: {json.dumps(chunk)}\n\n")

    if tool_calls:
        for tc in tool_calls:
            chunk = {
                "id": gen_id,
                "model": model,
                "choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": 0, "id": tc["id"], "type": "function",
                     "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                ]}, "finish_reason": None}],
            }
            chunks.append(f"data: {json.dumps(chunk)}\n\n")

    finish = "tool_calls" if tool_calls else "stop"
    final_chunk = {
        "id": gen_id,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
        "usage": usage or {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }
    chunks.append(f"data: {json.dumps(final_chunk)}\n\n")
    chunks.append("data: [DONE]\n\n")

    return httpx.Response(200, text="".join(chunks))

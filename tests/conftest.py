import hashlib
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

TEST_API_KEY = "test-key-12345"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()


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


def make_llm_response(
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    model: str = "test-model",
    usage: dict[str, Any] | None = None,
) -> httpx.Response:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = "tool_calls" if tool_calls else "stop"
    data = {
        "id": "gen-test-123",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }
    return httpx.Response(200, json=data)


make_sse_response = make_llm_response

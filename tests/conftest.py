import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from src.app.main import app


@pytest.fixture
async def redis() -> FakeRedis:  # type: ignore[misc]
    return FakeRedis()


@pytest.fixture
async def client(redis: FakeRedis) -> AsyncClient:  # type: ignore[misc]
    app.state.redis = redis
    app.state.http_client = AsyncClient()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]
    await app.state.http_client.aclose()

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis

from src.app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.redis = Redis.from_url(str(settings.redis_url))
    app.state.http_client = AsyncClient(timeout=settings.llm_timeout)

    yield

    await app.state.http_client.aclose()
    await app.state.redis.aclose()

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis

from src.app.core.config import settings
from src.app.services.analytics import AnalyticsStore
from src.app.services.metrics import MetricsCollector

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.http_client = AsyncClient(timeout=settings.llm_timeout)
    app.state.metrics = MetricsCollector()
    app.state.analytics = AnalyticsStore()

    try:
        redis = Redis.from_url(str(settings.redis_url))
        await redis.ping()
        app.state.redis = redis
        logger.info("Redis conectado")
    except Exception:
        app.state.redis = None
        logger.warning("Redis no disponible, funcionando sin historial")

    yield

    await app.state.http_client.aclose()
    if app.state.redis:
        await app.state.redis.aclose()

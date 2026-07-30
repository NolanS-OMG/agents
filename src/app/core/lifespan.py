import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from tortoise import Tortoise

from src.app.core.config import settings
from src.app.db import TORTOISE_ORM
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

    try:
        await Tortoise.init(config=TORTOISE_ORM)
        await Tortoise.generate_schemas()
        logger.info("PostgreSQL conectado")
    except Exception as e:
        logger.warning(f"PostgreSQL no disponible: {e}")

    app.state.voice_pipeline = None
    if settings.voice_enabled:
        try:
            from src.app.services.synthesizer import Synthesizer
            from src.app.services.transcriber import Transcriber
            from src.app.services.voice_pipeline import VoicePipeline

            transcriber = Transcriber(
                model_size=settings.whisper_model,
                device=settings.whisper_device,
            )
            synthesizer = Synthesizer(voice=settings.tts_voice)
            app.state.voice_pipeline = VoicePipeline(
                transcriber=transcriber,
                synthesizer=synthesizer,
            )
            logger.info(
                f"Voice pipeline inicializado ({settings.whisper_model} on {settings.whisper_device})"
            )
        except Exception as e:
            logger.warning(f"Voice pipeline no disponible: {e}")

    yield

    await Tortoise.close_connections()
    await app.state.http_client.aclose()
    if app.state.redis:
        await app.state.redis.aclose()

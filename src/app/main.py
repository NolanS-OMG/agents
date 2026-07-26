import logging

from fastapi import FastAPI

from src.app.api.routes import chat, health, webhook
from src.app.core.config import settings
from src.app.core.lifespan import lifespan

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(webhook.router)

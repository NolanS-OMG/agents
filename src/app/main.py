from fastapi import FastAPI

from src.app.api.routes import chat, health, webhook
from src.app.core.config import settings
from src.app.core.lifespan import lifespan
from src.app.core.logging_config import setup_logging
from src.app.middleware.correlation import CorrelationMiddleware

setup_logging(debug=settings.debug)

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.add_middleware(CorrelationMiddleware)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(webhook.router)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.routes import (
    analytics,
    chat,
    converse,
    health,
    knowledge,
    prompts,
    sse,
    usage,
    voice,
    webhook,
    websocket,
)
from src.app.core.config import settings
from src.app.core.lifespan import lifespan
from src.app.core.logging_config import setup_logging
from src.app.middleware.auth import AuthMiddleware
from src.app.middleware.correlation import CorrelationMiddleware

setup_logging(debug=settings.debug)

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://nolanashcraft.netlify.app",
        "https://nolanashcraft.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.add_middleware(AuthMiddleware)
app.add_middleware(CorrelationMiddleware)

app.include_router(health.router)
app.include_router(websocket.router)
app.include_router(sse.router)
app.include_router(chat.router)
app.include_router(converse.router)
app.include_router(knowledge.router)
app.include_router(prompts.router)
app.include_router(usage.router)
app.include_router(webhook.router)
app.include_router(voice.router)
app.include_router(analytics.router)

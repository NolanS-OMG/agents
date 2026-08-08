import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.app.api.routes import (
    analytics,
    chat,
    converse,
    health,
    knowledge,
    prompts,
    sse,
    usage,
    webhook,
    webhook_twilio_wa,
    websocket,
)
from src.app.core.config import settings
from src.app.core.lifespan import lifespan
from src.app.core.logging_config import setup_logging
from src.app.middleware.auth import AuthMiddleware
from src.app.middleware.correlation import CorrelationMiddleware

logger = logging.getLogger(__name__)

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
app.include_router(webhook_twilio_wa.router)

app.include_router(analytics.router)

if settings.voice_enabled:
    try:
        from src.app.api.routes import voice
        app.include_router(voice.router)
    except ImportError:
        logger.warning("Voice dependencies not available, voice routes disabled")

# Serve audio files (greetings, fillers) as static for Twilio <Play>
_audio_dir = Path(__file__).resolve().parent.parent.parent / "audio"
if _audio_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_audio_dir)), name="static")

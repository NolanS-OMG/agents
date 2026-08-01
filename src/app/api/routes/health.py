from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from src.app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health_check(request: Request) -> dict[str, str]:
    redis = request.app.state.redis
    status = "healthy"

    if redis:
        try:
            await redis.ping()
        except Exception:
            status = "degraded"
    else:
        status = "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    snapshot: dict[str, Any] = request.app.state.metrics.snapshot()
    return snapshot


@router.get("/analytics")
async def analytics(request: Request) -> dict[str, Any]:
    store = getattr(request.app.state, "analytics", None)
    if not store:
        return {"error": "Analytics not available"}
    summary: dict[str, Any] = await store.get_summary()
    return summary

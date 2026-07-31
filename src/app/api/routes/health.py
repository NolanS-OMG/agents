from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    redis = request.app.state.redis
    redis_status = "disconnected"
    if redis:
        try:
            await redis.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "error"
    return {"status": "ok", "redis": redis_status}


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

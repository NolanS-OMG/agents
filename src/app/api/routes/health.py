from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    redis = request.app.state.redis
    if redis:
        await redis.ping()
    return {"status": "ok"}


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    snapshot: dict[str, Any] = request.app.state.metrics.snapshot()
    return snapshot

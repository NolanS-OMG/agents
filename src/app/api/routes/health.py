from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    redis = request.app.state.redis
    await redis.ping()
    return {"status": "ok"}

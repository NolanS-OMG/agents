import time

from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis,
    sender_id: str,
    max_msgs: int = 10,
    window_secs: int = 60,
    tenant_id: str = "",
) -> bool:
    prefix = f"ratelimit:{tenant_id}:" if tenant_id else "ratelimit:"
    key = f"{prefix}{sender_id}"
    now = time.time()
    cutoff = now - window_secs

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window_secs)
    results = await pipe.execute()

    count: int = results[2]
    return count <= max_msgs


async def check_tenant_rate_limit(
    redis: Redis,
    tenant_id: str,
    max_msgs: int = 100,
    window_secs: int = 60,
) -> bool:
    return await check_rate_limit(redis, tenant_id, max_msgs, window_secs, tenant_id="global")


async def check_session_rate_limit(redis: Redis, session_id: str) -> tuple[bool, int]:
    """Check rate limit for a chat session.

    Returns (is_allowed, retry_after_seconds)
    Limits: 1000 msgs/hour, 100 msgs/minute
    """
    hour_key = f"rate:session:{session_id}:hour"
    hour_count = await redis.incr(hour_key)

    if hour_count == 1:
        await redis.expire(hour_key, 3600)

    if hour_count > 1000:
        ttl = await redis.ttl(hour_key)
        return False, max(ttl, 0)

    min_key = f"rate:session:{session_id}:minute"
    min_count = await redis.incr(min_key)

    if min_count == 1:
        await redis.expire(min_key, 60)

    if min_count > 100:
        ttl = await redis.ttl(min_key)
        return False, max(ttl, 0)

    return True, 0

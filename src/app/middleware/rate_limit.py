import time

from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis,
    sender_id: str,
    max_msgs: int = 10,
    window_secs: int = 60,
) -> bool:
    key = f"ratelimit:{sender_id}"
    now = time.time()
    cutoff = now - window_secs

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff)
    pipe.zcard(key)
    results = await pipe.execute()

    count: int = results[1]
    if count >= max_msgs:
        return False

    await redis.zadd(key, {str(now): now})
    await redis.expire(key, window_secs)
    return True

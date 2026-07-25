from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis

from src.app.services.llm.base import LLMMessage

SESSION_TTL = 3600
MAX_HISTORY_MESSAGES = 20


class SessionManager:
    def __init__(self, redis: Any) -> None:
        self._redis: Redis = redis

    async def get_history(self, session_id: str) -> list[LLMMessage]:
        key = f"session:{session_id}:history"
        raw = await self._redis.get(key)
        if not raw:
            return []
        messages_data: list[dict[str, str]] = json.loads(raw)
        return [LLMMessage(**m) for m in messages_data]

    async def save_history(self, session_id: str, messages: list[LLMMessage]) -> None:
        key = f"session:{session_id}:history"
        trimmed = messages[-MAX_HISTORY_MESSAGES:]
        data = json.dumps([m.model_dump() for m in trimmed])
        await self._redis.set(key, data, ex=SESSION_TTL)

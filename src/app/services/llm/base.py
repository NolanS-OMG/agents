from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict[str, Any] = {}
    tool_calls: list[dict[str, Any]] = []
    generation_id: str = ""
    finish_reason: str = ""
    cost_usd: float = 0.0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    retry_count: int = 0
    tokens_per_second: float = 0.0
    ttft_ms: int = 0


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
    ) -> LLMResponse: ...

import asyncio
from typing import Any

from httpx import AsyncClient, HTTPStatusError

from src.app.services.llm.base import LLMMessage, LLMProvider, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        http_client: AsyncClient,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 3,
    ) -> None:
        self._client = http_client
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_retries = max_retries

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/agente-ia",
            "X-Title": "Agente IA",
        }

        for attempt in range(self._max_retries):
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 429:
                wait = 2 ** attempt + 1
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]["message"]
            return LLMResponse(
                content=choice.get("content", ""),
                model=data.get("model", self._model),
                usage=data.get("usage", {}),
                tool_calls=choice.get("tool_calls", []),
            )

        raise HTTPStatusError(
            "Rate limited after retries",
            request=response.request,
            response=response,
        )

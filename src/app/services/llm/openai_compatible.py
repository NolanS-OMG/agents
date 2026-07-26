import asyncio
import json
import time
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
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/agente-ia",
            "X-Title": "Agente IA",
        }

        retry_count = 0
        for attempt in range(self._max_retries):
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 429:
                retry_count += 1
                wait = 2 ** attempt + 1
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            return self._parse_stream_response(response, retry_count)

        raise HTTPStatusError(
            "Rate limited after retries",
            request=response.request,
            response=response,
        )

    def _parse_stream_response(self, response: Any, retry_count: int) -> LLMResponse:
        content_parts: list[str] = []
        tool_calls_data: dict[int, dict[str, Any]] = {}
        generation_id = ""
        finish_reason = ""
        model = self._model
        usage: dict[str, Any] = {}
        ttft_ms = 0
        start_time = time.time()
        first_token_received = False

        for line in response.text.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if not generation_id:
                generation_id = chunk.get("id", "")
            if not model or model == self._model:
                model = chunk.get("model", self._model)

            if "usage" in chunk:
                usage = chunk["usage"]

            choices = chunk.get("choices", [])
            if not choices:
                continue

            choice = choices[0]
            delta = choice.get("delta", {})

            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

            delta_content = delta.get("content")
            if delta_content:
                if not first_token_received:
                    ttft_ms = int((time.time() - start_time) * 1000)
                    first_token_received = True
                content_parts.append(delta_content)

            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if "id" in tc and tc["id"]:
                        tool_calls_data[idx]["id"] = tc["id"]
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        tool_calls_data[idx]["function"]["name"] = fn["name"]
                    if fn.get("arguments"):
                        tool_calls_data[idx]["function"]["arguments"] += fn["arguments"]

        generation_time = time.time() - start_time
        content = "".join(content_parts)
        tool_calls = list(tool_calls_data.values()) if tool_calls_data else []

        completion_tokens = usage.get("completion_tokens", 0)
        tokens_per_second = (
            completion_tokens / generation_time if generation_time > 0 and completion_tokens else 0.0
        )

        cost_usd = usage.get("cost", 0.0)
        if not cost_usd:
            cost_details = usage.get("cost_details", {})
            cost_usd = cost_details.get("upstream_inference_cost", 0.0) or 0.0

        prompt_details = usage.get("prompt_tokens_details", {})
        cached_tokens = prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0

        completion_details = usage.get("completion_tokens_details", {})
        reasoning_tokens = (
            completion_details.get("reasoning_tokens", 0)
            if isinstance(completion_details, dict) else 0
        )

        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            tool_calls=tool_calls,
            generation_id=generation_id,
            finish_reason=finish_reason,
            cost_usd=cost_usd,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            retry_count=retry_count,
            tokens_per_second=round(tokens_per_second, 1),
            ttft_ms=ttft_ms,
        )

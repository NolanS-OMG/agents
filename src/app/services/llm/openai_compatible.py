import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator

from httpx import AsyncClient, HTTPStatusError

from src.app.services.llm.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


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
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if "openrouter" in self._base_url:
            headers["HTTP-Referer"] = "https://github.com/agente-ia"
            headers["X-Title"] = "Agente IA"

        retry_count = 0
        logger.info(f"LLM request to {self._base_url} with model {self._model}")
        logger.info(f"Tools: {len(tools) if tools else 0} tools provided")
        logger.info(f"Messages: {len(messages)} messages")

        for attempt in range(self._max_retries):
            t0 = time.time()
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            latency_ms = int((time.time() - t0) * 1000)

            if response.status_code == 429:
                retry_count += 1
                wait = 2**attempt + 1
                await asyncio.sleep(wait)
                continue

            if response.status_code >= 400:
                logger.error(f"LLM API error {response.status_code}: {response.text}")
                logger.error(f"Payload was: {json.dumps(payload, indent=2)}")

            response.raise_for_status()
            result = self._parse_response(response, retry_count, latency_ms)
            logger.info(f"LLM response: finish_reason={result.finish_reason}, tool_calls={len(result.tool_calls)}")
            return result

        raise HTTPStatusError(
            "Rate limited after retries",
            request=response.request,
            response=response,
        )

    def _parse_response(self, response: Any, retry_count: int, latency_ms: int) -> LLMResponse:
        data = response.json()

        generation_id = data.get("id", "")
        model = data.get("model", self._model)
        usage: dict[str, Any] = data.get("usage", {})

        choices = data.get("choices", [])
        content = ""
        tool_calls: list[dict[str, Any]] = []
        finish_reason = ""

        if choices:
            choice = choices[0]
            finish_reason = choice.get("finish_reason", "")
            message = choice.get("message", {})
            content = message.get("content", "") or ""
            tool_calls = message.get("tool_calls", []) or []

        completion_tokens = usage.get("completion_tokens", 0)
        tokens_per_second = (
            completion_tokens / (latency_ms / 1000) if latency_ms > 0 and completion_tokens else 0.0
        )

        cost_usd = usage.get("cost", 0.0)
        if not cost_usd:
            cost_details = usage.get("cost_details", {})
            cost_usd = cost_details.get("upstream_inference_cost", 0.0) or 0.0

        prompt_details = usage.get("prompt_tokens_details", {})
        cached_tokens = (
            prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0
        )

        completion_details = usage.get("completion_tokens_details", {})
        reasoning_tokens = (
            completion_details.get("reasoning_tokens", 0)
            if isinstance(completion_details, dict)
            else 0
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
            ttft_ms=latency_ms,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream LLM response chunks in real-time"""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if "openrouter" in self._base_url:
            headers["HTTP-Referer"] = "https://github.com/agente-ia"
            headers["X-Title"] = "Agente IA"

        logger.info(f"LLM stream request to {self._base_url} with model {self._model}")

        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        ) as response:
            response.raise_for_status()

            accumulated_content = ""
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                if line == "data: [DONE]":
                    break

                try:
                    chunk_data = json.loads(line[6:])
                    choices = chunk_data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason")

                    # Content chunk
                    if "content" in delta and delta["content"]:
                        content = delta["content"]
                        accumulated_content += content
                        yield {
                            "type": "content",
                            "content": content,
                        }

                    # Tool calls
                    if "tool_calls" in delta and delta["tool_calls"]:
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.get("id", ""),
                                    "type": tc.get("type", "function"),
                                    "function": {"name": "", "arguments": ""},
                                }

                            if "function" in tc:
                                func = tc["function"]
                                if "name" in func:
                                    accumulated_tool_calls[idx]["function"]["name"] = func["name"]
                                if "arguments" in func:
                                    accumulated_tool_calls[idx]["function"]["arguments"] += func[
                                        "arguments"
                                    ]

                    # Finish
                    if finish_reason:
                        tool_calls_list = list(accumulated_tool_calls.values())
                        yield {
                            "type": "done",
                            "finish_reason": finish_reason,
                            "content": accumulated_content,
                            "tool_calls": tool_calls_list,
                        }

                except json.JSONDecodeError:
                    continue

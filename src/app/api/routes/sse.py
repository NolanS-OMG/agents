import hashlib
import json
import logging
from collections.abc import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from src.app.channels.base import Channel
from src.app.core.config import settings
from src.app.db.models import ApiKey
from src.app.middleware.rate_limit import check_session_rate_limit
from src.app.services.llm.base import LLMMessage
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant_loader import load_tenant_async
from src.app.tools.registry import get_tools_for_tenant

router = APIRouter(prefix="/api/v1", tags=["sse"])
logger = logging.getLogger(__name__)


class SSEChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4096)
    session_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"
    )
    language: str = Field(default="en", pattern=r"^(en|es)$")
    channel: str = Field(default="web", pattern=r"^(web|whatsapp|call)$")

    @field_validator("session_id", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: str | None) -> str | None:
        if v == "" or v is None:
            return None
        return v


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: Request, body: SSEChatMessage) -> StreamingResponse:
    """SSE streaming endpoint. Returns text/event-stream with tool-calling loop."""

    api_key = request.headers.get("x-api-key", "")
    if not api_key:
        return StreamingResponse(
            iter([sse_event("error", {"message": "API key required"})]),
            media_type="text/event-stream",
            status_code=401,
        )

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    record = await ApiKey.get_or_none(key_hash=key_hash, active=True).select_related("tenant")

    if not record or not record.tenant.active:
        return StreamingResponse(
            iter([sse_event("error", {"message": "Invalid API key"})]),
            media_type="text/event-stream",
            status_code=401,
        )

    tenant_id = record.tenant.id
    redis = getattr(request.app.state, "redis", None)
    session_id = body.session_id or str(uuid4())

    if redis:
        allowed, retry_after = await check_session_rate_limit(redis, session_id)
        if not allowed:
            return StreamingResponse(
                iter([sse_event("error", {
                    "message": "Rate limit exceeded",
                    "retry_after_seconds": retry_after,
                })]),
                media_type="text/event-stream",
                status_code=429,
            )

    tenant = await load_tenant_async(tenant_id, redis)
    http_client = request.app.state.http_client
    llm = await get_llm_provider(http_client, tenant_id=tenant_id)
    channel = Channel(body.channel)
    tools_objs = get_tools_for_tenant(tenant, channel=channel)
    tools = [t.schema() for t in tools_objs] if tools_objs else None

    tenant_prompt = tenant.get_prompt(settings.estilo)
    doc_list = "\n".join([
        f"  - {getattr(doc, 'slug', '')}: {getattr(doc, 'title', '')} — {desc}"
        for doc in tenant.docs
        if (desc := getattr(doc, "description", ""))
    ])
    if doc_list:
        tenant_prompt += (
            "\n\nDOCUMENTOS DISPONIBLES "
            "(usa buscar_base_conocimiento_extensa con slug):\n" + doc_list
        )

    if body.language == "es":
        tenant_prompt += "\n\nIMPORTANTE: Responde SIEMPRE en español."
    else:
        tenant_prompt += "\n\nIMPORTANT: Always respond in English."

    history: list[LLMMessage] = []
    if redis:
        session_mgr = SessionManager(redis, llm=llm, tenant_id=tenant_id)
        history = await session_mgr.get_history(session_id)

    history.append(LLMMessage(role="user", content=body.message))

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal history

        yield sse_event("session", {"session_id": session_id})

        accumulated_content = ""
        max_tool_rounds = 5

        for _round in range(max_tool_rounds + 1):
            current_messages = [LLMMessage(role="system", content=tenant_prompt)] + history

            tool_calls_data: list[dict] = []
            round_content = ""
            finish_reason = ""

            async for chunk in llm.stream(current_messages, tools=tools):
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    content = chunk.get("content", "")
                    round_content += content
                    accumulated_content += content
                    yield sse_event("content", {"text": content})

                elif chunk_type == "done":
                    finish_reason = chunk.get("finish_reason", "")
                    tool_calls_data = chunk.get("tool_calls", [])

            if not tool_calls_data or finish_reason != "tool_calls":
                break

            if round_content:
                history.append(LLMMessage(role="assistant", content=round_content))

            for tc in tool_calls_data:
                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]

                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {}

                tool_obj = next((t for t in tools_objs if t.name == tool_name), None)
                if not tool_obj:
                    continue

                result = await tool_obj.execute(**tool_args)

                if (
                    hasattr(result, "data")
                    and isinstance(result.data, dict)
                    and result.data.get("status") == "dispatched"
                ):
                    yield sse_event("tool_call", {
                        "tool": result.data["frontend_tool"],
                        "args": result.data.get("args", {}),
                    })
                    tool_result_content = json.dumps({
                        "status": "ok",
                        "message": "Action dispatched to frontend.",
                    })
                else:
                    tool_result_content = (
                        json.dumps(result.data) if hasattr(result, "data") else ""
                    )

                history.append(LLMMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[tc],
                ))
                history.append(LLMMessage(
                    role="tool",
                    name=tool_name,
                    content=tool_result_content,
                    tool_call_id=tc.get("id", ""),
                ))

        if accumulated_content:
            history.append(LLMMessage(role="assistant", content=accumulated_content))

        if redis:
            session_mgr = SessionManager(redis, llm=llm, tenant_id=tenant_id)
            await session_mgr.save_history(
                session_id, history, model_used=llm._model
            )

        yield sse_event("done", {"session_id": session_id})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

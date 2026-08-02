from uuid import uuid4

from fastapi import APIRouter, Cookie, HTTPException, Path, Request, Response
from pydantic import BaseModel, Field, field_validator

from src.app.api.deps import CurrentTenant
from src.app.channels.base import Channel
from src.app.core.config import settings
from src.app.middleware.rate_limit import check_session_rate_limit
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant_loader import load_tenant_async
from src.app.tools.registry import get_tools_for_tenant

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatMessage(BaseModel):
    session_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"
    )
    message: str = Field(min_length=1, max_length=4096)
    channel: str = Field(default="web", pattern=r"^(web|whatsapp|call)$")
    language: str = Field(default="en", pattern=r"^(en|es)$")

    @field_validator("session_id", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: str | None) -> str | None:
        if v == "":
            return None
        return v


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_used: str | None = None


@router.post("/chat/debug")
async def chat_debug(request: Request) -> dict:
    """Debug endpoint para ver el payload exacto recibido"""
    raw_body = await request.body()
    try:
        json_body = await request.json()
    except Exception as e:
        json_body = f"Error parsing JSON: {e}"

    return {
        "raw_body": raw_body.decode("utf-8"),
        "parsed_json": json_body,
        "headers": dict(request.headers),
        "method": request.method,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    response: Response,
    body: ChatMessage,
    tenant_ctx: CurrentTenant,
    session_id_cookie: str | None = Cookie(default=None, alias="session_id"),
) -> ChatResponse:
    http_client = request.app.state.http_client
    redis = getattr(request.app.state, "redis", None)

    session_id = body.session_id or session_id_cookie or str(uuid4())
    is_new_session = not (body.session_id or session_id_cookie)

    if redis:
        allowed, retry_after = await check_session_rate_limit(redis, session_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please wait a moment.",
                    "retry_after_seconds": retry_after,
                },
            )

    if is_new_session:
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            max_age=31536000,
        )

    tenant = await load_tenant_async(tenant_ctx.tenant_id, redis)
    llm = await get_llm_provider(http_client, tenant_id=tenant_ctx.tenant_id)
    channel = Channel(body.channel)
    tools = get_tools_for_tenant(tenant, channel=channel)

    tenant_prompt = tenant.get_prompt(settings.estilo)
    doc_list = "\n".join(
        [
            f"  - {doc.slug}: {doc.title} — {doc.description}"
            for doc in tenant.docs
            if doc.description
        ]
    )
    if doc_list:
        tenant_prompt += f"\n\nDOCUMENTOS DISPONIBLES (usa buscar_base_conocimiento_extensa con slug):\n{doc_list}"

    if body.language == "es":
        tenant_prompt += "\n\nIMPORTANTE: Responde SIEMPRE en español."
    else:
        tenant_prompt += "\n\nIMPORTANT: Always respond in English."

    agent = AgentRouter(llm=llm, tools=tools, tenant_prompt=tenant_prompt)

    metadata = {
        "ip_address": request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.headers.get("x-real-ip", "")
        or request.client.host
        if request.client
        else None,
        "user_agent": request.headers.get("user-agent"),
        "referrer": request.headers.get("referer"),
        "language": request.headers.get("accept-language", "").split(",")[0],
    }

    history = []
    if redis:
        session = SessionManager(redis, llm=llm, tenant_id=tenant_ctx.tenant_id)
        history = await session.get_history(session_id)

    result = await agent.run(user_message=body.message, history=history)

    if redis:
        relevant_messages = [
            m
            for m in result.messages
            if m.role == "user" or (m.role == "assistant" and m.content)
        ]
        session = SessionManager(redis, llm=llm, tenant_id=tenant_ctx.tenant_id)
        await session.save_history(
            session_id, relevant_messages, model_used=llm._model, metadata=metadata
        )

    return ChatResponse(
        session_id=session_id,
        response=result.response,
        tool_used=result.tool_used,
    )


@router.get("/chat/welcome")
async def get_welcome_message(tenant_ctx: CurrentTenant) -> dict:
    if tenant_ctx.tenant_id == "portfolio":
        return {
            "message": "👋 Hi! I'm Nolan's AI assistant. I can help you learn about his experience with AI systems, projects, tech stack, and more. What would you like to know?",
            "suggestions": [
                "Tell me about his AI experience",
                "What projects has he built?",
                "Show me his tech stack",
                "How can I contact him?",
            ],
        }

    return {
        "message": "👋 Hello! How can I help you today?",
        "suggestions": [],
    }


@router.get("/chat/session/{session_id}/history")
async def get_session_history(
    request: Request,
    tenant_ctx: CurrentTenant,
    session_id: str = Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"),
) -> dict:
    redis = request.app.state.redis
    if not redis:
        return {"session_id": session_id, "messages": []}

    llm = await get_llm_provider(request.app.state.http_client, tenant_id=tenant_ctx.tenant_id)
    session = SessionManager(redis, llm=llm, tenant_id=tenant_ctx.tenant_id)
    history = await session.get_history(session_id)

    messages = []
    for msg in history:
        if msg.role in ("user", "assistant") and msg.content:
            messages.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    return {
        "session_id": session_id,
        "messages": messages,
    }


@router.delete("/chat/session/{session_id}")
async def delete_session(
    request: Request,
    tenant_ctx: CurrentTenant,
    session_id: str = Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"),
) -> Response:
    redis = request.app.state.redis
    if redis:
        await redis.delete(
            f"session:{session_id}:history",
            f"session:{session_id}:summary",
            f"session:{session_id}:needs_human",
        )
    return Response(status_code=204)


@router.post("/sessions/{session_id}/release")
async def release_session(
    request: Request,
    session_id: str = Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"),
) -> Response:
    redis = request.app.state.redis
    if redis:
        session = SessionManager(redis)
        await session.release_human(session_id)
    return Response(content="OK", status_code=200)

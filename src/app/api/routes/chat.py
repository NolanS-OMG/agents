from uuid import uuid4

from fastapi import APIRouter, Cookie, Path, Request, Response
from pydantic import BaseModel, Field

from src.app.api.deps import CurrentTenant
from src.app.core.config import settings
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
    channel: str = Field(default="api")
    language: str = Field(default="en", pattern=r"^(en|es)$")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_used: str | None = None


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
    tools = get_tools_for_tenant(tenant)

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

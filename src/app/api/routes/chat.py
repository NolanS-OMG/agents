from fastapi import APIRouter, Path, Request, Response
from pydantic import BaseModel, Field

from src.app.core.config import settings
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant import load_tenant
from src.app.tools.registry import get_tools_for_tenant

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$")
    message: str = Field(min_length=1, max_length=4096)
    channel: str = Field(default="api")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_used: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatMessage) -> ChatResponse:
    http_client = request.app.state.http_client
    redis = request.app.state.redis

    tenant = load_tenant(settings.tenant_id)
    llm = get_llm_provider(http_client)
    tools = get_tools_for_tenant(tenant)
    agent = AgentRouter(llm=llm, tools=tools, tenant_prompt=tenant.get_prompt(settings.estilo))

    history = []
    if redis:
        session = SessionManager(redis, llm=llm)
        history = await session.get_history(body.session_id)

    result = await agent.run(user_message=body.message, history=history)

    if redis:
        relevant_messages = [
            m for m in result.messages
            if m.role in ("user", "assistant") and m.content
        ]
        session = SessionManager(redis, llm=llm)
        await session.save_history(body.session_id, relevant_messages)

    return ChatResponse(
        session_id=body.session_id,
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

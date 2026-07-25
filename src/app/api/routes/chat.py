from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.app.services.agent_router import AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.tools.buscar_conocimiento import BuscarConocimiento
from src.app.tools.consultar_info_negocio import ConsultarInfoNegocio
from src.app.tools.ejecutar_accion import EjecutarAccion

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    channel: str = Field(default="api")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_used: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatMessage) -> ChatResponse:
    http_client = request.app.state.http_client
    redis = request.app.state.redis

    llm = get_llm_provider(http_client)
    tools = [EjecutarAccion(), ConsultarInfoNegocio(), BuscarConocimiento()]
    agent = AgentRouter(llm=llm, tools=tools)

    session = SessionManager(redis)
    history = await session.get_history(body.session_id)

    result = await agent.run(user_message=body.message, history=history)

    relevant_messages = [
        m for m in result.messages
        if m.role in ("user", "assistant") and m.content
    ]
    await session.save_history(body.session_id, relevant_messages)

    return ChatResponse(
        session_id=body.session_id,
        response=result.response,
        tool_used=result.tool_used,
    )

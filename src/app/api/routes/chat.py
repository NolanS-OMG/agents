from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

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
    return ChatResponse(
        session_id=body.session_id,
        response="Agente en construcción. Mensaje recibido.",
        tool_used=None,
    )

import hashlib
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from src.app.core.config import settings
from src.app.db.models import ApiKey
from src.app.middleware.rate_limit import check_session_rate_limit
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.base import LLMMessage
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant_loader import load_tenant_async

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


class WSChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4096)
    session_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_\-]+$")
    language: str = Field(default="en", pattern=r"^(en|es)$")


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint para chat con streaming en tiempo real.

    Query params:
    - api_key: API key del tenant

    Mensajes del cliente:
    {
        "message": "user message",
        "session_id": "optional-session-id",
        "language": "en"
    }

    Mensajes al cliente:
    - {"type": "connected", "session_id": "..."}
    - {"type": "content", "content": "chunk..."}
    - {"type": "tool_call", "name": "tool_name", "args": {...}}
    - {"type": "tool_result", "content": "..."}
    - {"type": "done", "session_id": "..."}
    - {"type": "error", "message": "..."}
    """
    await websocket.accept()

    session_id: str | None = None
    tenant_id: str | None = None
    redis = None

    try:
        # Auth via query param
        query_params = dict(websocket.query_params)
        api_key = query_params.get("api_key", "")

        if not api_key:
            await websocket.send_json({"type": "error", "message": "API key required"})
            await websocket.close(code=1008)
            return

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        record = await ApiKey.get_or_none(key_hash=key_hash, active=True).select_related("tenant")

        if not record or not record.tenant.active:
            await websocket.send_json({"type": "error", "message": "Invalid API key"})
            await websocket.close(code=1008)
            return

        tenant_id = record.tenant.id
        redis = websocket.app.state.redis if hasattr(websocket.app.state, "redis") else None

        # Load tenant config
        tenant = await load_tenant_async(tenant_id, redis)
        http_client = websocket.app.state.http_client
        llm = await get_llm_provider(http_client, tenant_id=tenant_id)

        # Generate session_id if needed
        session_id = str(uuid4())
        await websocket.send_json({"type": "connected", "session_id": session_id})

        # Message loop
        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
                msg = WSChatMessage(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid message format: {str(e)}"
                })
                continue

            # Use provided session_id or keep current
            if msg.session_id:
                session_id = msg.session_id

            # Rate limiting
            if redis:
                allowed, retry_after = await check_session_rate_limit(redis, session_id)
                if not allowed:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded",
                        "retry_after_seconds": retry_after,
                    })
                    continue

            # Build prompt
            tenant_prompt = tenant.get_prompt(settings.estilo)
            doc_list = "\n".join([
                f"  - {doc.slug}: {doc.title} — {doc.description}"
                for doc in tenant.docs
                if doc.description
            ])
            if doc_list:
                tenant_prompt += f"\n\nDOCUMENTOS DISPONIBLES (usa buscar_base_conocimiento_extensa con slug):\n{doc_list}"

            if msg.language == "es":
                tenant_prompt += "\n\nIMPORTANTE: Responde SIEMPRE en español."
            else:
                tenant_prompt += "\n\nIMPORTANT: Always respond in English."

            # Load history
            history: list[LLMMessage] = []
            if redis:
                session_mgr = SessionManager(redis, llm=llm, tenant_id=tenant_id)
                history = await session_mgr.get_history(session_id)

            # Add user message to history
            history.append(LLMMessage(role="user", content=msg.message))

            # Build messages for LLM
            messages = [LLMMessage(role="system", content=tenant_prompt)] + history

            # Get tools
            from src.app.tools.registry import get_tools_for_tenant
            tools_objs = get_tools_for_tenant(tenant)
            tools = [t.schema() for t in tools_objs] if tools_objs else None

            # Stream response
            accumulated_content = ""
            tool_calls_data = []
            finish_reason = ""

            async for chunk in llm.stream(messages, tools=tools):
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    content = chunk.get("content", "")
                    accumulated_content += content
                    await websocket.send_json({
                        "type": "content",
                        "content": content,
                    })

                elif chunk_type == "done":
                    finish_reason = chunk.get("finish_reason", "")
                    tool_calls_data = chunk.get("tool_calls", [])

                    # Handle tool calls if present
                    if tool_calls_data and finish_reason == "tool_calls":
                        for tc in tool_calls_data:
                            tool_name = tc["function"]["name"]
                            tool_args_str = tc["function"]["arguments"]

                            try:
                                tool_args = json.loads(tool_args_str)
                            except json.JSONDecodeError:
                                tool_args = {}

                            await websocket.send_json({
                                "type": "tool_call",
                                "name": tool_name,
                                "args": tool_args,
                            })

                            # Execute tool
                            tool_obj = next((t for t in tools_objs if t.__class__.__name__ == tool_name), None)
                            if tool_obj:
                                result = await tool_obj.execute(**tool_args)
                                tool_result_content = json.dumps(result.data) if result.data else ""

                                await websocket.send_json({
                                    "type": "tool_result",
                                    "name": tool_name,
                                    "content": tool_result_content,
                                })

                                # Add tool call to history
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

                                # Continue streaming with tool result
                                messages_with_tool = [LLMMessage(role="system", content=tenant_prompt)] + history

                                async for tool_chunk in llm.stream(messages_with_tool, tools=None):
                                    if tool_chunk.get("type") == "content":
                                        content = tool_chunk.get("content", "")
                                        accumulated_content += content
                                        await websocket.send_json({
                                            "type": "content",
                                            "content": content,
                                        })
                                    elif tool_chunk.get("type") == "done":
                                        break

                    # Add assistant message to history
                    if accumulated_content:
                        history.append(LLMMessage(role="assistant", content=accumulated_content))

                    # Save to session
                    if redis:
                        session_mgr = SessionManager(redis, llm=llm, tenant_id=tenant_id)
                        await session_mgr.save_history(
                            session_id,
                            history,
                            model_used=llm._model,
                        )

                    # Send done
                    await websocket.send_json({
                        "type": "done",
                        "session_id": session_id,
                    })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except:
            pass

    finally:
        try:
            await websocket.close()
        except:
            pass

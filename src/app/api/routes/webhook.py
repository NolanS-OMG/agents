import logging
import time

from fastapi import APIRouter, Query, Request, Response

from src.app.channels.base import OutgoingMessage
from src.app.channels.whatsapp import WhatsAppAdapter
from src.app.core.config import settings
from src.app.middleware.rate_limit import check_rate_limit
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant import load_tenant
from src.app.tools.registry import get_tools_for_tenant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])


@router.get("/webhook/whatsapp")
async def verify_webhook(
    response: Response,
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> Response:
    payload = await request.json()
    http_client = request.app.state.http_client
    redis = request.app.state.redis

    adapter = WhatsAppAdapter(
        access_token=settings.whatsapp_access_token,
        phone_number_id=settings.whatsapp_phone_number_id,
        http_client=http_client,
    )

    incoming = adapter.parse_incoming(payload)
    if not incoming:
        return Response(content="OK", status_code=200)

    logger.warning(f"[WA] Mensaje de {incoming.sender_id}: {incoming.message}")
    metrics = request.app.state.metrics
    metrics.increment("messages_received")

    if redis:
        allowed = await check_rate_limit(
            redis, incoming.sender_id,
            max_msgs=settings.rate_limit_messages,
            window_secs=settings.rate_limit_window,
        )
        if not allowed:
            logger.warning(f"[WA] Rate limit excedido para {incoming.sender_id}")
            await adapter.send_reply(OutgoingMessage(
                channel="whatsapp",
                recipient_id=incoming.sender_id,
                message="Estás enviando muchos mensajes, espera un momento por favor.",
            ))
            return Response(content="OK", status_code=200)

        session = SessionManager(redis, llm=None)
        if await session.is_needs_human(incoming.sender_id):
            await adapter.send_reply(OutgoingMessage(
                channel="whatsapp",
                recipient_id=incoming.sender_id,
                message="Tu conversación está siendo atendida por un agente humano. Te responderá pronto.",
            ))
            return Response(content="OK", status_code=200)

    tenant = load_tenant(settings.tenant_id)
    llm = get_llm_provider(http_client)
    tools = get_tools_for_tenant(tenant)
    agent = AgentRouter(llm=llm, tools=tools, tenant_prompt=tenant.get_prompt(settings.estilo))

    history = []
    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            history = await session.get_history(incoming.sender_id)
        except Exception:
            logger.warning("[WA] Redis no disponible, sin historial")

    t0 = time.time()
    try:
        result = await agent.run(user_message=incoming.message, history=history)
    except Exception as e:
        logger.error(f"[WA] Error en agente: {e}")
        metrics.increment("errors")
        await adapter.send_reply(OutgoingMessage(
            channel="whatsapp",
            recipient_id=incoming.sender_id,
            message="Disculpa, tuve un problema técnico. ¿Puedes intentar de nuevo?",
        ))
        return Response(content="OK", status_code=200)

    latency_ms = int((time.time() - t0) * 1000)
    tokens_in = result.usage.get("prompt_tokens", 0)
    tokens_out = result.usage.get("completion_tokens", 0)

    metrics.observe_latency("llm", latency_ms / 1000)
    metrics.increment("llm_calls")
    metrics.increment("tokens_input", tokens_in)
    metrics.increment("tokens_output", tokens_out)
    if result.tool_used:
        metrics.increment(f"tool_calls:{result.tool_used}")

    logger.warning(f"[WA] Respuesta del agente: {result.response[:100]}")

    analytics = request.app.state.analytics
    analytics.log_message(
        conversation_id=incoming.sender_id,
        role="user",
        content=incoming.message,
        tenant_id=settings.tenant_id,
        channel="whatsapp",
    )
    analytics.log_message(
        conversation_id=incoming.sender_id,
        role="assistant",
        content=result.response,
        tool_used=result.tool_used,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        response_latency_ms=latency_ms,
        model_used=settings.llm_model,
        tenant_id=settings.tenant_id,
        channel="whatsapp",
    )

    user_msgs = [m.content for m in result.messages if m.role == "user" and m.content]
    bot_msgs = [m.content for m in result.messages if m.role == "assistant" and m.content]
    tools_used = [result.tool_used] if result.tool_used else []
    analytics.update_conversation(
        conversation_id=incoming.sender_id,
        user_messages=user_msgs,
        bot_messages=bot_msgs,
        tools_called=tools_used,
        total_tokens_in=tokens_in,
        total_tokens_out=tokens_out,
        latencies_ms=[latency_ms],
        escalation=result.needs_human,
        tenant_id=settings.tenant_id,
        channel="whatsapp",
    )

    if result.needs_human and redis:
        session = SessionManager(redis, llm=llm)
        await session.mark_needs_human(incoming.sender_id)

    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            relevant_messages = [
                m for m in result.messages
                if m.role in ("user", "assistant") and m.content
            ]
            await session.save_history(
                incoming.sender_id,
                relevant_messages,
                compression_threshold=settings.history_compression_threshold,
                keep_recent=settings.history_keep_recent,
            )
        except Exception:
            logger.warning("[WA] Redis no disponible, no se guardó historial")

    await adapter.send_reply(OutgoingMessage(
        channel="whatsapp",
        recipient_id=incoming.sender_id,
        message=result.response,
    ))

    metrics.increment("messages_sent")
    logger.info(f"[WA] Respuesta enviada a {incoming.sender_id}")
    return Response(content="OK", status_code=200)

import asyncio
import logging
import time

from fastapi import APIRouter, Query, Request, Response

from src.app.channels.base import IncomingMessage, OutgoingMessage
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

MAX_CONTEXT_WINDOW = 128_000
DEDUP_TTL = 300


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

    # Deduplicación: si ya procesamos este message_id, ignorar
    if redis and incoming.message_id:
        dedup_key = f"dedup:{incoming.message_id}"
        already_seen = await redis.set(dedup_key, "1", ex=DEDUP_TTL, nx=True)
        if not already_seen:
            logger.info(f"[WA] Mensaje duplicado ignorado: {incoming.message_id}")
            return Response(content="OK", status_code=200)

    metrics = request.app.state.metrics
    metrics.increment("messages_received")

    # Rate limit y needs_human son rápidos — se ejecutan antes de retornar 200
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

    # Procesamiento pesado (LLM) en background — retornamos 200 a Meta inmediatamente
    asyncio.create_task(_process_message(request, incoming, adapter))
    return Response(content="OK", status_code=200)


async def _process_message(
    request: Request,
    incoming: IncomingMessage,
    adapter: WhatsAppAdapter,
) -> None:
    webhook_start = time.time()
    http_client = request.app.state.http_client
    redis = request.app.state.redis
    metrics = request.app.state.metrics
    analytics = request.app.state.analytics

    logger.info(f"[WA] Procesando mensaje de {incoming.sender_id}: {incoming.message[:50]}")

    tenant = load_tenant(settings.tenant_id)
    llm = get_llm_provider(http_client)
    tools = get_tools_for_tenant(tenant)
    agent = AgentRouter(
        llm=llm, tools=tools,
        tenant_prompt=tenant.get_prompt(settings.estilo),
        sender_id=incoming.sender_id,
    )

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
        return

    latency_ms = int((time.time() - t0) * 1000)
    tokens_in = result.usage.get("prompt_tokens", 0)
    tokens_out = result.usage.get("completion_tokens", 0)
    context_pct = (result.context_tokens / MAX_CONTEXT_WINDOW * 100) if result.context_tokens else 0

    metrics.observe_latency("llm", latency_ms / 1000)
    metrics.increment("llm_calls", result.total_llm_calls)
    metrics.increment("tokens_input", tokens_in)
    metrics.increment("tokens_output", tokens_out)
    if result.tool_used:
        metrics.increment(f"tool_calls:{result.tool_used}")

    logger.info(f"[WA] Respuesta ({latency_ms}ms, ttft={result.ttft_ms}ms, "
                f"tps={result.tokens_per_second}, cost=${result.cost_usd:.5f}): "
                f"{result.response[:80]}")

    analytics.log_message(
        conversation_id=incoming.sender_id,
        role="user",
        content=incoming.message,
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

    send_success, send_ms = await adapter.send_reply(OutgoingMessage(
        channel="whatsapp",
        recipient_id=incoming.sender_id,
        message=result.response,
    ))

    if not send_success:
        metrics.increment("whatsapp_send_failures")
    metrics.observe_latency("whatsapp_send", send_ms / 1000)

    webhook_total_ms = int((time.time() - webhook_start) * 1000)

    analytics.log_message(
        conversation_id=incoming.sender_id,
        role="assistant",
        content=result.response,
        tool_used=result.tool_used,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        response_latency_ms=latency_ms,
        model_used=result.model_actual,
        tenant_id=settings.tenant_id,
        channel="whatsapp",
        cost_usd=result.cost_usd,
        cached_tokens=result.usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        if isinstance(result.usage.get("prompt_tokens_details"), dict) else 0,
        reasoning_tokens=result.usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        if isinstance(result.usage.get("completion_tokens_details"), dict) else 0,
        finish_reason=result.finish_reason,
        generation_id=result.generation_id,
        retry_count=result.retry_count,
        tool_execution_ms=result.tool_execution_ms,
        webhook_total_ms=webhook_total_ms,
        tokens_per_second=result.tokens_per_second,
        context_window_used_pct=round(context_pct, 1),
        ttft_ms=result.ttft_ms,
    )

    action_type = None
    if result.tool_used == "ejecutar_accion":
        action_type = "pedido"

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
        cost_usd=result.cost_usd,
        model_actual=result.model_actual,
        tokens_per_second=result.tokens_per_second,
        action_type=action_type,
    )

    metrics.increment("messages_sent")
    metrics.observe_latency("webhook_total", webhook_total_ms / 1000)
    logger.info(f"[WA] Completo en {webhook_total_ms}ms")

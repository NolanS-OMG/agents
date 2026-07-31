import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from src.app.channels.base import IncomingMessage, OutgoingMessage
from src.app.channels.whatsapp import WhatsAppAdapter
from src.app.core.config import settings
from src.app.db.models import TenantCredentials
from src.app.middleware.rate_limit import check_rate_limit
from src.app.services.credential_vault import CredentialVault
from src.app.services.message_processor import process_and_reply, transcribe_audio
from src.app.services.session import SessionManager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])

_background_tasks: set[asyncio.Task[Any]] = set()

MAX_CONTEXT_WINDOW = 128_000
DEDUP_TTL = 300


def _bg(coro: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _get_tenant_whatsapp_creds(tenant_id: str) -> tuple[str, str, str]:
    creds = await TenantCredentials.get_or_none(tenant_id=tenant_id)
    if not creds or not creds.whatsapp_access_token_enc:
        raise HTTPException(404, "Tenant WhatsApp not configured")
    vault = CredentialVault()
    token = vault.decrypt(creds.whatsapp_access_token_enc)
    return token, creds.whatsapp_phone_number_id, creds.whatsapp_verify_token


@router.get("/webhook/whatsapp/{tenant_id}")
async def verify_webhook_tenant(
    tenant_id: str,
    response: Response,
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> Response:
    try:
        _, _, verify_token = await _get_tenant_whatsapp_creds(tenant_id)
    except Exception:
        return Response(content="Forbidden", status_code=403)
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


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


@router.post("/webhook/whatsapp/{tenant_id}")
async def whatsapp_webhook_tenant(request: Request, tenant_id: str) -> Response:
    payload = await request.json()
    http_client = request.app.state.http_client
    redis = request.app.state.redis

    try:
        access_token, phone_number_id, _ = await _get_tenant_whatsapp_creds(tenant_id)
    except HTTPException:
        logger.warning(f"[WA:{tenant_id}] WhatsApp not configured, ignoring")
        return Response(content="OK", status_code=200)
    except Exception as e:
        logger.error(f"[WA:{tenant_id}] Error loading credentials: {e}")
        return Response(content="OK", status_code=200)

    adapter = WhatsAppAdapter(
        access_token=access_token,
        phone_number_id=phone_number_id,
        http_client=http_client,
    )

    incoming = adapter.parse_incoming(payload)
    if not incoming:
        return Response(content="OK", status_code=200)

    if redis and incoming.message_id:
        dedup_key = f"dedup:{tenant_id}:{incoming.message_id}"
        is_new = await redis.set(dedup_key, "1", ex=DEDUP_TTL, nx=True)
        if not is_new:
            return Response(content="OK", status_code=200)

    metrics = request.app.state.metrics
    metrics.increment("messages_received")

    if redis:
        allowed = await check_rate_limit(
            redis,
            incoming.sender_id,
            max_msgs=settings.rate_limit_messages,
            window_secs=settings.rate_limit_window,
            tenant_id=tenant_id,
        )
        if not allowed:
            await adapter.send_reply(
                OutgoingMessage(
                    channel="whatsapp",
                    recipient_id=incoming.sender_id,
                    message="Estás enviando muchos mensajes, espera un momento por favor.",
                )
            )
            return Response(content="OK", status_code=200)

        session = SessionManager(redis, llm=None)
        if await session.is_needs_human(f"{tenant_id}:{incoming.sender_id}"):
            await adapter.send_reply(
                OutgoingMessage(
                    channel="whatsapp",
                    recipient_id=incoming.sender_id,
                    message="Tu conversación está siendo atendida por un agente humano.",
                )
            )
            return Response(content="OK", status_code=200)

    _bg(_process_message_tenant(request, incoming, adapter, tenant_id))
    return Response(content="OK", status_code=200)


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

    if redis and incoming.message_id:
        dedup_key = f"dedup:{incoming.message_id}"
        is_new = await redis.set(dedup_key, "1", ex=DEDUP_TTL, nx=True)
        if not is_new:
            logger.info(f"[WA] Mensaje duplicado ignorado: {incoming.message_id}")
            return Response(content="OK", status_code=200)

    metrics = request.app.state.metrics
    metrics.increment("messages_received")

    if redis:
        allowed = await check_rate_limit(
            redis,
            incoming.sender_id,
            max_msgs=settings.rate_limit_messages,
            window_secs=settings.rate_limit_window,
        )
        if not allowed:
            logger.warning(f"[WA] Rate limit excedido para {incoming.sender_id}")
            await adapter.send_reply(
                OutgoingMessage(
                    channel="whatsapp",
                    recipient_id=incoming.sender_id,
                    message="Estás enviando muchos mensajes, espera un momento por favor.",
                )
            )
            return Response(content="OK", status_code=200)

        session = SessionManager(redis, llm=None)
        if await session.is_needs_human(incoming.sender_id):
            await adapter.send_reply(
                OutgoingMessage(
                    channel="whatsapp",
                    recipient_id=incoming.sender_id,
                    message="Tu conversación está siendo atendida por un agente humano. Te responderá pronto.",
                )
            )
            return Response(content="OK", status_code=200)

    _bg(_process_message(request, incoming, adapter))
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

    user_text = incoming.message
    input_type = "text"
    if incoming.is_audio:
        voice_pipeline = getattr(request.app.state, "voice_pipeline", None)
        text = await transcribe_audio(incoming, adapter, voice_pipeline)
        if text is None:
            return
        user_text = text
        input_type = "audio"

    logger.info(f"[WA] Procesando mensaje de {incoming.sender_id}: {user_text[:50]}")

    t0 = time.time()
    result = await process_and_reply(
        tenant_id=settings.tenant_id,
        incoming=incoming,
        adapter=adapter,
        http_client=http_client,
        redis=redis,
        user_text=user_text,
        estilo=settings.estilo,
    )
    if not result:
        metrics.increment("errors")
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

    webhook_total_ms = int((time.time() - webhook_start) * 1000)

    await analytics.log_message(
        conversation_id=incoming.sender_id,
        role="user",
        content=user_text,
        tenant_id=settings.tenant_id,
        channel="whatsapp",
        input_type=input_type,
    )

    await analytics.log_message(
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
        finish_reason=result.finish_reason,
        generation_id=result.generation_id,
        retry_count=result.retry_count,
        tool_execution_ms=result.tool_execution_ms,
        webhook_total_ms=webhook_total_ms,
        tokens_per_second=result.tokens_per_second,
        context_window_used_pct=round(context_pct, 1),
        ttft_ms=result.ttft_ms,
    )

    user_msgs = [m.content for m in result.messages if m.role == "user" and m.content]
    bot_msgs = [m.content for m in result.messages if m.role == "assistant" and m.content]
    tools_used = [result.tool_used] if result.tool_used else []
    await analytics.update_conversation(
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
        action_type="pedido" if result.tool_used == "ejecutar_accion" else None,
    )

    metrics.increment("messages_sent")
    metrics.observe_latency("webhook_total", webhook_total_ms / 1000)
    logger.info(f"[WA] Completo en {webhook_total_ms}ms")


async def _process_message_tenant(
    request: Request,
    incoming: IncomingMessage,
    adapter: WhatsAppAdapter,
    tenant_id: str,
) -> None:
    http_client = request.app.state.http_client
    redis = request.app.state.redis
    log_prefix = f"[WA:{tenant_id}]"

    user_text = incoming.message
    if incoming.is_audio:
        voice_pipeline = getattr(request.app.state, "voice_pipeline", None)
        text = await transcribe_audio(incoming, adapter, voice_pipeline, log_prefix)
        if text is None:
            return
        user_text = text

    await process_and_reply(
        tenant_id=tenant_id,
        incoming=incoming,
        adapter=adapter,
        http_client=http_client,
        redis=redis,
        user_text=user_text,
        log_prefix=log_prefix,
    )

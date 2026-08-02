from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from src.app.channels.base import Channel, IncomingMessage, OutgoingMessage
from src.app.services.agent_router import AgentResult, AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant_loader import load_tenant_async
from src.app.tools.registry import get_tools_for_tenant

if TYPE_CHECKING:
    from httpx import AsyncClient
    from redis.asyncio import Redis

    from src.app.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)


async def transcribe_audio(
    incoming: IncomingMessage,
    adapter: ChannelAdapter,
    voice_pipeline: Any,
    log_prefix: str = "[WA]",
) -> str | None:
    """Transcribe incoming audio. Returns text or None if failed (reply sent)."""
    if not voice_pipeline:
        logger.warning(f"{log_prefix} Audio recibido pero voice pipeline no disponible")
        await adapter.send_reply(
            OutgoingMessage(
                channel="whatsapp",
                recipient_id=incoming.sender_id,
                message="No puedo procesar audio en este momento. ¿Puedes escribir tu mensaje?",
            )
        )
        return None

    audio_bytes = await adapter.download_media(incoming.media_id)
    if not audio_bytes:
        logger.error(f"{log_prefix} No se pudo descargar media {incoming.media_id}")
        await adapter.send_reply(
            OutgoingMessage(
                channel="whatsapp",
                recipient_id=incoming.sender_id,
                message="No pude descargar tu audio. ¿Puedes intentar de nuevo?",
            )
        )
        return None

    user_text = await asyncio.to_thread(voice_pipeline.transcribe, audio_bytes)
    if not user_text.strip():
        await adapter.send_reply(
            OutgoingMessage(
                channel="whatsapp",
                recipient_id=incoming.sender_id,
                message="No pude entender el audio. ¿Puedes repetirlo o escribir tu mensaje?",
            )
        )
        return None

    return user_text


async def process_and_reply(
    tenant_id: str,
    incoming: IncomingMessage,
    adapter: ChannelAdapter,
    http_client: AsyncClient,
    redis: Redis | None,
    user_text: str,
    estilo: str = "chat",
    log_prefix: str = "[WA]",
) -> AgentResult | None:
    """Run agent loop and send reply. Returns AgentResult or None on error."""
    tenant = await load_tenant_async(tenant_id, redis)
    llm = await get_llm_provider(http_client, tenant_id=tenant_id)
    tools = get_tools_for_tenant(tenant, channel=Channel.WHATSAPP)
    agent = AgentRouter(
        llm=llm,
        tools=tools,
        tenant_prompt=tenant.get_prompt(estilo),
        sender_id=incoming.sender_id,
    )

    session_key = f"{tenant_id}:{incoming.sender_id}"
    history: list[Any] = []
    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            history = await session.get_history(session_key)
        except Exception:
            logger.warning(f"{log_prefix} Redis no disponible, sin historial")

    try:
        result = await agent.run(user_message=user_text, history=history)
    except Exception as e:
        logger.error(f"{log_prefix} Error en agente: {e}")
        await adapter.send_reply(
            OutgoingMessage(
                channel="whatsapp",
                recipient_id=incoming.sender_id,
                message="Disculpa, tuve un problema técnico. ¿Puedes intentar de nuevo?",
            )
        )
        return None

    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            relevant = [m for m in result.messages if m.role in ("user", "assistant") and m.content]
            await session.save_history(session_key, relevant)
            if result.needs_human:
                await session.mark_needs_human(session_key)
        except Exception:
            logger.warning(f"{log_prefix} No se guardó historial")

    await adapter.send_reply(
        OutgoingMessage(
            channel="whatsapp",
            recipient_id=incoming.sender_id,
            message=result.response,
        )
    )
    logger.info(f"{log_prefix} Respuesta enviada a {incoming.sender_id}")
    return result

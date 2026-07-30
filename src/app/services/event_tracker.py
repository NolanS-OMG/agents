import logging

from src.app.db.models import Event

logger = logging.getLogger(__name__)


async def track_llm_call(
    tenant_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: float,
    conversation_id: str | None = None,
    status: str = "success",
) -> None:
    try:
        await Event.create(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            event_type="llm_call",
            provider="openrouter",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            status=status,
        )
    except Exception as e:
        logger.warning(f"Failed to track llm_call for {tenant_id}: {e}")


async def track_stt(
    tenant_id: str,
    audio_duration_s: float,
    latency_ms: int,
    provider: str = "groq",
    conversation_id: str | None = None,
    status: str = "success",
) -> None:
    try:
        await Event.create(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            event_type="stt",
            provider=provider,
            audio_duration_s=audio_duration_s,
            latency_ms=latency_ms,
            status=status,
        )
    except Exception as e:
        logger.warning(f"Failed to track stt for {tenant_id}: {e}")


async def track_tts(
    tenant_id: str,
    characters: int,
    latency_ms: int,
    provider: str = "edge_tts",
    conversation_id: str | None = None,
    status: str = "success",
) -> None:
    try:
        await Event.create(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            event_type="tts",
            provider=provider,
            characters=characters,
            latency_ms=latency_ms,
            status=status,
        )
    except Exception as e:
        logger.warning(f"Failed to track tts for {tenant_id}: {e}")


async def track_whatsapp_message(
    tenant_id: str,
    status: str = "success",
    conversation_id: str | None = None,
) -> None:
    try:
        await Event.create(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            event_type="whatsapp_msg",
            provider="meta",
            status=status,
        )
    except Exception as e:
        logger.warning(f"Failed to track whatsapp_msg for {tenant_id}: {e}")

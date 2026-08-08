import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response

from src.app.channels.base import OutgoingMessage
from src.app.channels.twilio_whatsapp import TwilioWhatsAppAdapter, validate_twilio_signature
from src.app.core.config import settings
from src.app.db.models import TenantCredentials
from src.app.middleware.rate_limit import check_rate_limit
from src.app.services.agent_router import AgentRouter
from src.app.services.credential_vault import CredentialVault
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant_loader import load_tenant_async
from src.app.tools.registry import get_tools_for_tenant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook-twilio-wa"])

DEDUP_TTL = 300


async def _get_twilio_creds(tenant_id: str) -> tuple[str, str, str]:
    creds = await TenantCredentials.get_or_none(tenant_id=tenant_id)
    if not creds or not creds.twilio_auth_token_enc:
        raise HTTPException(404, "Tenant Twilio not configured")
    vault = CredentialVault()
    auth_token = vault.decrypt(creds.twilio_auth_token_enc)
    return creds.twilio_account_sid, auth_token, creds.twilio_phone_number


@router.post("/webhook/twilio-whatsapp/{tenant_id}")
async def twilio_whatsapp_webhook(request: Request, tenant_id: str) -> Response:
    form = await request.form()
    params: dict[str, str] = {k: str(v) for k, v in form.items()}

    try:
        account_sid, auth_token, from_number = await _get_twilio_creds(tenant_id)
    except HTTPException:
        logger.warning(f"[TwilioWA:{tenant_id}] Credentials not configured")
        return Response(content="OK", status_code=200)
    except Exception as e:
        logger.error(f"[TwilioWA:{tenant_id}] Error loading credentials: {e}")
        return Response(content="OK", status_code=200)

    signature = request.headers.get("X-Twilio-Signature", "")
    if signature:
        url = str(request.url)
        if not validate_twilio_signature(url, params, signature, auth_token):
            logger.warning(f"[TwilioWA:{tenant_id}] Invalid signature")
            return Response(content="Forbidden", status_code=403)

    http_client = request.app.state.http_client
    redis = getattr(request.app.state, "redis", None)

    adapter = TwilioWhatsAppAdapter(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
        http_client=http_client,
    )

    incoming = adapter.parse_incoming(params)
    if not incoming:
        return Response(content="OK", status_code=200)

    if redis and incoming.message_id:
        dedup_key = f"dedup:{tenant_id}:{incoming.message_id}"
        already_seen = await redis.set(dedup_key, "1", ex=DEDUP_TTL, nx=True)
        if not already_seen:
            return Response(content="OK", status_code=200)

    if redis:
        allowed = await check_rate_limit(
            redis, incoming.sender_id,
            max_msgs=settings.rate_limit_messages,
            window_secs=settings.rate_limit_window,
            tenant_id=tenant_id,
        )
        if not allowed:
            await adapter.send_reply(OutgoingMessage(
                channel="twilio_whatsapp",
                recipient_id=incoming.sender_id,
                message="Estás enviando muchos mensajes, espera un momento.",
            ))
            return Response(content="OK", status_code=200)

    asyncio.create_task(_process(request, incoming, adapter, tenant_id))
    return Response(content="OK", status_code=200)


async def _process(
    request: Request,
    incoming,
    adapter: TwilioWhatsAppAdapter,
    tenant_id: str,
) -> None:
    http_client = request.app.state.http_client
    redis = getattr(request.app.state, "redis", None)

    user_text = incoming.message

    if incoming.is_audio:
        audio_bytes = await adapter.download_media(incoming.media_id)
        if not audio_bytes:
            await adapter.send_reply(OutgoingMessage(
                channel="twilio_whatsapp",
                recipient_id=incoming.sender_id,
                message="No pude descargar tu audio.",
            ))
            return

        if settings.groq_api_key:
            from src.app.services.stt_cloud import GroqSTT
            stt = GroqSTT(http_client, settings.groq_api_key)
            user_text = await stt.transcribe(audio_bytes, "audio.ogg")
        else:
            voice_pipeline = getattr(request.app.state, "voice_pipeline", None)
            if voice_pipeline:
                user_text = voice_pipeline.transcribe(audio_bytes)
            else:
                await adapter.send_reply(OutgoingMessage(
                    channel="twilio_whatsapp",
                    recipient_id=incoming.sender_id,
                    message="No puedo procesar audio en este momento.",
                ))
                return

        if not user_text.strip():
            await adapter.send_reply(OutgoingMessage(
                channel="twilio_whatsapp",
                recipient_id=incoming.sender_id,
                message="No pude entender el audio.",
            ))
            return

    tenant = await load_tenant_async(tenant_id, redis)
    llm = get_llm_provider(http_client)
    tools = get_tools_for_tenant(tenant)
    agent = AgentRouter(
        llm=llm, tools=tools,
        tenant_prompt=tenant.get_prompt("chat"),
        sender_id=incoming.sender_id,
    )

    session_key = f"{tenant_id}:{incoming.sender_id}"
    history = []
    if redis:
        session = SessionManager(redis, llm=llm)
        history = await session.get_history(session_key)

    try:
        result = await agent.run(user_message=user_text, history=history)
    except Exception as e:
        logger.error(f"[TwilioWA:{tenant_id}] Agent error: {e}")
        await adapter.send_reply(OutgoingMessage(
            channel="twilio_whatsapp",
            recipient_id=incoming.sender_id,
            message="Disculpa, tuve un problema técnico.",
        ))
        return

    if redis:
        session = SessionManager(redis, llm=llm)
        relevant = [m for m in result.messages if m.role in ("user", "assistant") and m.content]
        await session.save_history(session_key, relevant)

    await adapter.send_reply(OutgoingMessage(
        channel="twilio_whatsapp",
        recipient_id=incoming.sender_id,
        message=result.response,
    ))
    logger.info(f"[TwilioWA:{tenant_id}] Respuesta enviada a {incoming.sender_id}")

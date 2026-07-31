import asyncio
import base64
import logging
import time
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

if TYPE_CHECKING:
    from httpx import AsyncClient

from src.app.api.deps import CurrentTenant
from src.app.core.config import settings
from src.app.services.agent_router import AgentRouter
from src.app.services.event_tracker import track_llm_call, track_stt, track_tts
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant_loader import load_tenant_async
from src.app.tools.registry import get_tools_for_tenant

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


def _bg(coro: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


router = APIRouter(prefix="/api/v1", tags=["converse"])

ALLOWED_AUDIO_TYPES = {"audio/ogg", "audio/mpeg", "audio/wav", "audio/mp4", "audio/webm"}


class ConverseResponse(BaseModel):
    conversant_id: str
    response: str
    audio_base64: str | None = None
    input_type: str
    transcription: str | None = None
    tool_used: str | None = None
    latency_ms: int = 0


@router.post("/converse", response_model=ConverseResponse)
async def converse(
    request: Request,
    tenant: CurrentTenant,
    conversant_id: str = Form(...),
    message: str | None = Form(None),
    response_format: str = Form("text"),
    estilo: str = Form("chat"),
    audio: UploadFile | None = None,
) -> ConverseResponse:
    start = time.time()

    if not message and not audio:
        raise HTTPException(400, "Either 'message' or 'audio' is required")

    if response_format not in ("text", "audio", "both"):
        raise HTTPException(400, "response_format must be 'text', 'audio', or 'both'")

    http_client = request.app.state.http_client
    redis = getattr(request.app.state, "redis", None)

    input_type = "text"
    text = message or ""
    transcription: str | None = None

    if audio:
        input_type = "audio"
        if audio.content_type and audio.content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(400, f"Unsupported audio type: {audio.content_type}")
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(400, "Audio file is empty")
        t_stt = time.time()
        text = await _transcribe(audio_bytes, audio.filename or "audio.ogg", http_client, request)
        stt_ms = int((time.time() - t_stt) * 1000)
        _bg(
            track_stt(
                tenant_id=tenant.tenant_id,
                audio_duration_s=len(audio_bytes) / 16000,
                latency_ms=stt_ms,
            )
        )
        if not text.strip():
            return ConverseResponse(
                conversant_id=conversant_id,
                response="No pude entender el audio. ¿Puedes repetir?",
                input_type="audio",
                transcription="",
                latency_ms=int((time.time() - start) * 1000),
            )
        transcription = text

    tenant_config = await load_tenant_async(tenant.tenant_id, redis)
    llm = get_llm_provider(http_client)
    tools = get_tools_for_tenant(tenant_config)
    agent = AgentRouter(llm=llm, tools=tools, tenant_prompt=tenant_config.get_prompt(estilo))

    session_key = f"{tenant.tenant_id}:{conversant_id}"
    history = []
    session = SessionManager(redis, llm=llm) if redis else None
    if session:
        history = await session.get_history(session_key)

    t_llm = time.time()
    result = await agent.run(user_message=text, history=history)
    llm_latency_ms = int((time.time() - t_llm) * 1000)

    _bg(
        track_llm_call(
            tenant_id=tenant.tenant_id,
            model=result.model_actual,
            input_tokens=result.usage.get("prompt_tokens", 0),
            output_tokens=result.usage.get("completion_tokens", 0),
            latency_ms=llm_latency_ms,
            cost_usd=result.cost_usd,
        )
    )

    if session:
        relevant = [m for m in result.messages if m.role in ("user", "assistant") and m.content]
        await session.save_history(session_key, relevant)

    audio_base64: str | None = None
    if response_format in ("audio", "both"):
        t_tts = time.time()
        audio_base64 = await _synthesize(result.response, request)
        tts_ms = int((time.time() - t_tts) * 1000)
        if audio_base64:
            _bg(
                track_tts(
                    tenant_id=tenant.tenant_id,
                    characters=len(result.response),
                    latency_ms=tts_ms,
                )
            )

    latency_ms = int((time.time() - start) * 1000)

    return ConverseResponse(
        conversant_id=conversant_id,
        response=result.response,
        audio_base64=audio_base64,
        input_type=input_type,
        transcription=transcription,
        tool_used=result.tool_used,
        latency_ms=latency_ms,
    )


async def _transcribe(
    audio_bytes: bytes, filename: str, http_client: "AsyncClient", request: Request
) -> str:
    if settings.groq_api_key:
        from src.app.services.stt_cloud import GroqSTT

        stt = GroqSTT(http_client, settings.groq_api_key)
        return await stt.transcribe(audio_bytes, filename)

    voice_pipeline = getattr(request.app.state, "voice_pipeline", None)
    if voice_pipeline:
        return await asyncio.to_thread(voice_pipeline.transcribe, audio_bytes)

    raise HTTPException(503, "No STT service available (set GROQ_API_KEY or enable voice)")


async def _synthesize(text: str, request: Request) -> str | None:
    voice_pipeline = getattr(request.app.state, "voice_pipeline", None)
    if voice_pipeline:
        mp3_bytes = await voice_pipeline.synthesize(text)
        if mp3_bytes:
            return base64.b64encode(mp3_bytes).decode("ascii")
        return None

    try:
        from src.app.services.synthesizer import Synthesizer

        synth = Synthesizer(voice=settings.tts_voice)
        mp3_bytes = await synth.synthesize(text)
        return base64.b64encode(mp3_bytes).decode("ascii")
    except Exception as e:
        logger.warning(f"TTS failed: {e}")
        return None

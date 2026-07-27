import asyncio
import audioop
import base64
import enum
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from src.app.core.config import settings
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.tenant import load_tenant
from src.app.services.vad import SileroVAD, TurnDetector
from src.app.tools.registry import get_tools_for_tenant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])

MULAW_SAMPLE_RATE = 8000
WHISPER_SAMPLE_RATE = 16000


class CallState(enum.Enum):
    LISTENING = "listening"
    SPEECH_DETECTED = "speech_detected"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@router.post("/incoming-call")
async def incoming_call(request: Request) -> Response:
    host = request.headers.get("host", "localhost")
    scheme = "wss" if request.url.scheme == "https" else "ws"
    stream_url = f"{scheme}://{host}/ws/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="es-MX">Hola, bienvenido. En qué puedo ayudarte?</Say>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.websocket("/ws/media-stream")
async def media_stream(ws: WebSocket) -> None:
    await ws.accept()
    voice_pipeline = getattr(ws.app.state, "voice_pipeline", None)
    if not voice_pipeline:
        logger.error("[Voice] Pipeline no disponible, cerrando WebSocket")
        await ws.close()
        return

    vad = SileroVAD(threshold=0.5, sample_rate=MULAW_SAMPLE_RATE)
    turn_detector = TurnDetector(
        vad=vad,
        end_of_turn_ms=settings.vad_silence_ms,
        min_speech_ms=150,
        prefix_padding_ms=300,
    )

    stream_sid = ""
    state = CallState.LISTENING
    call_start = time.time()

    logger.info("[Voice] WebSocket conectado")

    try:
        async for raw_msg in ws.iter_text():
            msg: dict[str, Any] = json.loads(raw_msg)
            event = msg.get("event")

            if event == "start":
                stream_sid = msg.get("start", {}).get("streamSid", "")
                logger.info(f"[Voice] Stream iniciado: {stream_sid}")

            elif event == "media":
                payload = msg.get("media", {}).get("payload", "")
                mulaw_chunk = base64.b64decode(payload)

                # Barge-in: si estamos hablando y detectamos voz, interrumpir
                if state == CallState.SPEAKING:
                    prob = vad.process_chunk(mulaw_chunk)
                    if prob is not None and prob >= 0.5:
                        logger.info("[Voice] Barge-in detectado")
                        await ws.send_text(json.dumps({
                            "event": "clear",
                            "streamSid": stream_sid,
                        }))
                        state = CallState.LISTENING
                        turn_detector._reset_turn()
                    continue

                # Alimentar al turn detector
                utterance_audio = turn_detector.feed(mulaw_chunk)
                if utterance_audio:
                    state = CallState.PROCESSING
                    logger.info(
                        f"[Voice] End-of-turn detectado "
                        f"({len(utterance_audio)} bytes, "
                        f"{len(utterance_audio) / MULAW_SAMPLE_RATE:.1f}s)"
                    )

                    response_audio = await _process_and_synthesize(
                        utterance_audio, voice_pipeline, ws
                    )

                    if response_audio:
                        state = CallState.SPEAKING
                        await _send_audio(ws, stream_sid, response_audio)
                        state = CallState.LISTENING
                    else:
                        state = CallState.LISTENING

            elif event == "mark":
                mark_name = msg.get("mark", {}).get("name", "")
                if mark_name == "response_end":
                    state = CallState.LISTENING

            elif event == "stop":
                duration_s = int(time.time() - call_start)
                logger.info(f"[Voice] Llamada terminada ({duration_s}s)")
                break

    except WebSocketDisconnect:
        logger.info("[Voice] WebSocket desconectado")
    except Exception as e:
        logger.error(f"[Voice] Error: {e}", exc_info=True)


async def _process_and_synthesize(
    mulaw_audio: bytes,
    voice_pipeline: Any,
    ws: WebSocket,
) -> bytes | None:
    """Convert mulaw to PCM, transcribe, run agent, synthesize response."""
    # mulaw 8kHz → PCM 16kHz for Whisper
    pcm_8k = audioop.ulaw2lin(mulaw_audio, 2)
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, MULAW_SAMPLE_RATE, WHISPER_SAMPLE_RATE, None)

    text = voice_pipeline.transcribe_pcm(pcm_16k)
    if not text.strip():
        logger.info("[Voice] Transcripción vacía, ignorando")
        return None

    logger.info(f"[Voice] Transcrito: {text[:80]}")

    http_client = ws.app.state.http_client
    tenant = load_tenant(settings.tenant_id)
    llm = get_llm_provider(http_client)
    tools = get_tools_for_tenant(tenant)
    agent = AgentRouter(
        llm=llm, tools=tools,
        tenant_prompt=tenant.get_prompt(settings.estilo),
    )

    redis = ws.app.state.redis
    history = []
    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            history = await session.get_history("voice_caller")
        except Exception:
            pass

    result = await agent.run(user_message=text, history=history)
    logger.info(f"[Voice] Respuesta LLM: {result.response[:80]}")

    # Synthesize and convert to mulaw
    tts_bytes = await voice_pipeline.synthesize(result.response)
    if not tts_bytes:
        return None

    return _mp3_to_mulaw(tts_bytes)


def _mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    """Convert MP3 to mulaw 8kHz using pydub (in-memory, no ffmpeg CLI)."""
    import io

    from pydub import AudioSegment

    audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
    audio = audio.set_frame_rate(MULAW_SAMPLE_RATE).set_channels(1).set_sample_width(2)
    pcm = audio.raw_data
    return audioop.lin2ulaw(pcm, 2)


async def _send_audio(ws: WebSocket, stream_sid: str, mulaw_data: bytes) -> None:
    """Send mulaw audio to Twilio in 20ms chunks."""
    chunk_size = 160  # 20ms at 8kHz
    for i in range(0, len(mulaw_data), chunk_size):
        chunk = mulaw_data[i : i + chunk_size]
        payload = base64.b64encode(chunk).decode("ascii")
        await ws.send_text(json.dumps({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload},
        }))
        await asyncio.sleep(0.018)

    await ws.send_text(json.dumps({
        "event": "mark",
        "streamSid": stream_sid,
        "mark": {"name": "response_end"},
    }))

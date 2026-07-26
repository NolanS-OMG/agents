import asyncio
import audioop
import base64
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
from src.app.tools.registry import get_tools_for_tenant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])

MULAW_SAMPLE_RATE = 8000
WHISPER_SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 500
CHUNK_DURATION_MS = 20


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

    stream_sid = ""
    audio_buffer = bytearray()
    silence_start: float | None = None

    logger.info("[Voice] WebSocket conectado")

    try:
        async for raw_msg in ws.iter_text():
            msg: dict[str, Any] = __import__("json").loads(raw_msg)
            event = msg.get("event")

            if event == "start":
                stream_sid = msg.get("start", {}).get("streamSid", "")
                logger.info(f"[Voice] Stream iniciado: {stream_sid}")

            elif event == "media":
                payload = msg.get("media", {}).get("payload", "")
                chunk = base64.b64decode(payload)
                audio_buffer.extend(chunk)

                if _is_silence(chunk):
                    if silence_start is None:
                        silence_start = time.time()
                    elif (time.time() - silence_start) * 1000 >= settings.vad_silence_ms:
                        if len(audio_buffer) > MULAW_SAMPLE_RATE:
                            response_audio = await _process_utterance(
                                audio_buffer, voice_pipeline, ws
                            )
                            if response_audio:
                                await _send_audio(ws, stream_sid, response_audio)
                            audio_buffer.clear()
                        silence_start = None
                else:
                    silence_start = None

            elif event == "stop":
                logger.info("[Voice] Stream detenido")
                break

    except WebSocketDisconnect:
        logger.info("[Voice] WebSocket desconectado")
    except Exception as e:
        logger.error(f"[Voice] Error: {e}")


async def _process_utterance(
    audio_buffer: bytearray,
    voice_pipeline: Any,
    ws: WebSocket,
) -> bytes | None:
    pcm_8k = audioop.ulaw2lin(bytes(audio_buffer), 2)
    pcm_16k = audioop.ratecv(pcm_8k, 2, 1, MULAW_SAMPLE_RATE, WHISPER_SAMPLE_RATE, None)[0]

    text = voice_pipeline.transcribe(pcm_16k)
    if not text.strip():
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
    logger.info(f"[Voice] Respuesta: {result.response[:80]}")

    audio_response = await voice_pipeline.synthesize(result.response)
    if not audio_response:
        return None

    return audio_response


async def _send_audio(ws: WebSocket, stream_sid: str, audio_bytes: bytes) -> None:
    import json
    import subprocess
    import tempfile
    from pathlib import Path

    # Convert MP3 (from Edge-TTS) to mulaw 8kHz for Twilio
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f_in:
        f_in.write(audio_bytes)
        mp3_path = f_in.name

    raw_path = mp3_path.replace(".mp3", ".raw")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "8000", "-ac", "1",
             "-f", "mulaw", raw_path],
            capture_output=True, check=True,
        )
        mulaw_data = Path(raw_path).read_bytes()
    finally:
        Path(mp3_path).unlink(missing_ok=True)
        Path(raw_path).unlink(missing_ok=True)

    # Send in chunks matching Twilio's expected frame size (20ms = 160 bytes at 8kHz)
    chunk_size = 160
    for i in range(0, len(mulaw_data), chunk_size):
        chunk = mulaw_data[i:i + chunk_size]
        payload = base64.b64encode(chunk).decode("ascii")
        await ws.send_text(json.dumps({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload},
        }))
        await asyncio.sleep(0.02)

    await ws.send_text(json.dumps({
        "event": "mark",
        "streamSid": stream_sid,
        "mark": {"name": "response_end"},
    }))


def _is_silence(chunk: bytes, threshold: int = 10) -> bool:
    if not chunk:
        return True
    avg_energy = sum(abs(b - 128) for b in chunk) / len(chunk)
    return avg_energy < threshold

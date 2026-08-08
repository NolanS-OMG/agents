import asyncio
import base64
import enum
import json
import logging
import random
import time
import warnings
from pathlib import Path
from typing import Any

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from src.app.channels.base import Channel
from src.app.core.config import settings
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.session import SessionManager
from src.app.services.stt_openrouter import OpenRouterSTT
from src.app.services.tenant_loader import load_tenant_async
from src.app.services.tts_openrouter import OpenRouterTTS
from src.app.tools.registry import get_tools_for_tenant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])

MULAW_SAMPLE_RATE = 8000
WHISPER_SAMPLE_RATE = 16000

AUDIO_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "audio"
FILLERS_DIR = AUDIO_DIR / "fillers"
GREETINGS_DIR = AUDIO_DIR / "greetings"
FAREWELL_SOUND = AUDIO_DIR / "farewell.mp3"
KEYBOARD_SOUND = AUDIO_DIR / "keyboard_sound.mp3"
KEYBOARD_BOOST_DB = 10

HANGUP_AFTER_FAREWELL = False

FAREWELL_TRIGGERS = {"adiós", "adios", "hasta luego", "bye", "chao", "nos vemos"}

_filler_mulaw: list[bytes] = []
_greeting_mulaw: list[tuple[str, bytes]] = []
_keyboard_mulaw: bytes = b""
_farewell_mulaw: bytes = b""
_used_fillers: list[int] = []


def _load_hold_audio() -> None:
    """Pre-load filler, greeting, farewell, and keyboard audio as mulaw."""
    global _filler_mulaw, _keyboard_mulaw, _greeting_mulaw, _farewell_mulaw

    try:
        from pydub import AudioSegment

        if FILLERS_DIR.exists():
            for f in sorted(FILLERS_DIR.glob("*.mp3")):
                audio = AudioSegment.from_mp3(str(f))
                audio = audio.set_frame_rate(MULAW_SAMPLE_RATE).set_channels(1).set_sample_width(2)
                _filler_mulaw.append(audioop.lin2ulaw(audio.raw_data, 2))

        if GREETINGS_DIR.exists():
            for f in sorted(GREETINGS_DIR.glob("*.mp3")):
                audio = AudioSegment.from_mp3(str(f))
                audio = audio.set_frame_rate(MULAW_SAMPLE_RATE).set_channels(1).set_sample_width(2)
                # Extract the greeting text from filename for history injection
                text = f.stem.replace("_", " ")
                _greeting_mulaw.append((text, audioop.lin2ulaw(audio.raw_data, 2)))

        if FAREWELL_SOUND.exists():
            audio = AudioSegment.from_mp3(str(FAREWELL_SOUND))
            audio = audio.set_frame_rate(MULAW_SAMPLE_RATE).set_channels(1).set_sample_width(2)
            _farewell_mulaw = audioop.lin2ulaw(audio.raw_data, 2)

        if KEYBOARD_SOUND.exists():
            audio = AudioSegment.from_mp3(str(KEYBOARD_SOUND))
            audio = audio + KEYBOARD_BOOST_DB
            audio = audio.set_frame_rate(MULAW_SAMPLE_RATE).set_channels(1).set_sample_width(2)
            _keyboard_mulaw = audioop.lin2ulaw(audio.raw_data, 2)
    except Exception as e:
        logger.warning(f"[Voice] Could not load hold audio: {e}")


def _get_hold_mulaw(duration_ms: int = 3000) -> bytes:
    """Get non-repeating filler + keyboard chunk as mulaw."""
    global _used_fillers
    parts = []

    if _filler_mulaw:
        # Avoid repeating recent fillers
        available = [i for i in range(len(_filler_mulaw)) if i not in _used_fillers]
        if not available:
            _used_fillers.clear()
            available = list(range(len(_filler_mulaw)))
        idx = random.choice(available)
        _used_fillers.append(idx)
        # Keep history to half the total fillers
        if len(_used_fillers) > len(_filler_mulaw) // 2:
            _used_fillers.pop(0)
        parts.append(_filler_mulaw[idx])

    if _keyboard_mulaw:
        chunk_samples = (duration_ms * MULAW_SAMPLE_RATE) // 1000
        max_start = len(_keyboard_mulaw) - chunk_samples
        if max_start > 0:
            start = random.randint(0, max_start)
            parts.append(_keyboard_mulaw[start:start + chunk_samples])

    return b"".join(parts)


# Greeting text mapped to filenames for history injection
GREETING_TEXTS = [
    "Hola, buenas tardes. ¿En qué le puedo ayudar?",
    "Hola, bienvenido a Santa Leña. ¿Qué le ofrecemos?",
    "Buenas, bienvenido. ¿En qué le ayudo?",
]


class CallState(enum.Enum):
    LISTENING = "listening"
    SPEECH_DETECTED = "speech_detected"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@router.post("/incoming-call/{tenant_id}")
async def incoming_call_tenant(request: Request, tenant_id: str) -> Response:
    host = request.headers.get("host", "localhost")
    scheme = "wss" if request.url.scheme == "https" else "ws"
    stream_url = f"{scheme}://{host}/ws/media-stream/{tenant_id}"

    # Use pre-recorded greeting audio instead of robotic <Say>
    greeting_url = f"{request.url.scheme}://{host}/static/greetings/bienvenida_1.mp3"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{greeting_url}</Play>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/incoming-call")
async def incoming_call(request: Request) -> Response:
    return await incoming_call_tenant(request, settings.tenant_id)


@router.websocket("/ws/media-stream/{tenant_id}")
async def media_stream_tenant(ws: WebSocket, tenant_id: str) -> None:
    await ws.accept()

    # Load hold audio on first connection
    if not _filler_mulaw and not _keyboard_mulaw:
        _load_hold_audio()

    # Import VAD (lazy to avoid numpy dep at module level)
    from src.app.services.vad import SileroVAD, TurnDetector

    vad = SileroVAD(threshold=0.5, sample_rate=MULAW_SAMPLE_RATE)
    turn_detector = TurnDetector(
        vad=vad,
        end_of_turn_ms=settings.vad_silence_ms,
        min_speech_ms=150,
        prefix_padding_ms=300,
    )

    stream_sid = ""
    caller_id = ""
    state = CallState.LISTENING
    call_start = time.time()
    logger.info(f"[Voice:{tenant_id}] WebSocket conectado")

    try:
        async for raw_msg in ws.iter_text():
            msg: dict[str, Any] = json.loads(raw_msg)
            event = msg.get("event")

            if event == "start":
                start_data = msg.get("start", {})
                stream_sid = start_data.get("streamSid", "")
                custom = start_data.get("customParameters", {})
                caller_id = custom.get("From", "") or start_data.get("callSid", stream_sid)

                # Inject greeting into session history so LLM knows it already greeted
                redis = ws.app.state.redis
                if redis:
                    greeting_text = random.choice(GREETING_TEXTS)
                    session_key = f"{tenant_id}:{caller_id or 'voice_anonymous'}"
                    try:
                        from src.app.services.llm.base import LLMMessage
                        from src.app.services.llm.provider_factory import get_llm_provider
                        from src.app.services.session import SessionManager
                        llm = await get_llm_provider(ws.app.state.http_client, tenant_id=tenant_id)
                        session = SessionManager(redis, llm=llm)
                        await session.save_history(session_key, [
                            LLMMessage(role="assistant", content=greeting_text),
                        ])
                    except Exception as e:
                        logger.warning(f"[Voice:{tenant_id}] Could not inject greeting: {e}")

            elif event == "media":
                payload = msg.get("media", {}).get("payload", "")
                mulaw_chunk = base64.b64decode(payload)

                if state == CallState.SPEAKING:
                    prob = vad.process_chunk(mulaw_chunk)
                    if prob is not None and prob >= 0.5:
                        await ws.send_text(
                            json.dumps({"event": "clear", "streamSid": stream_sid})
                        )
                        state = CallState.LISTENING
                        turn_detector.reset_turn()
                    continue

                utterance_audio = turn_detector.feed(mulaw_chunk)
                if utterance_audio:
                    state = CallState.PROCESSING

                    # Send hold audio while processing
                    hold_mulaw = _get_hold_mulaw(3000)
                    if hold_mulaw:
                        asyncio.create_task(_send_audio(ws, stream_sid, hold_mulaw))

                    response_audio, user_text = await _process_utterance(
                        utterance_audio, ws, tenant_id, caller_id
                    )
                    if response_audio:
                        # Clear hold audio before sending response
                        await ws.send_text(
                            json.dumps({"event": "clear", "streamSid": stream_sid})
                        )
                        state = CallState.SPEAKING
                        await _send_audio(ws, stream_sid, response_audio)

                        # Detect farewell — play goodbye audio after response
                        user_lower = user_text.lower().strip()
                        is_farewell = any(t in user_lower for t in FAREWELL_TRIGGERS)
                        if is_farewell and _farewell_mulaw:
                            await _send_audio(ws, stream_sid, _farewell_mulaw)
                            if HANGUP_AFTER_FAREWELL:
                                logger.info(f"[Voice:{tenant_id}] Farewell detected, closing")
                                break
                    else:
                        state = CallState.LISTENING

            elif event == "mark":
                mark_name = msg.get("mark", {}).get("name", "")
                if mark_name == "response_end":
                    state = CallState.LISTENING

            elif event == "stop":
                duration_s = int(time.time() - call_start)
                logger.info(f"[Voice:{tenant_id}] Llamada terminada ({duration_s}s)")
                break

    except WebSocketDisconnect:
        logger.info(f"[Voice:{tenant_id}] WebSocket desconectado")
    except Exception as e:
        logger.error(f"[Voice:{tenant_id}] Error: {e}", exc_info=True)


@router.websocket("/ws/media-stream")
async def media_stream(ws: WebSocket) -> None:
    await media_stream_tenant(ws, settings.tenant_id)


async def _process_utterance(
    mulaw_audio: bytes,
    ws: WebSocket,
    tenant_id: str,
    caller_id: str = "",
) -> tuple[bytes | None, str]:
    """STT → LLM → TTS pipeline. Returns (mulaw_audio, user_text)."""
    http_client = ws.app.state.http_client
    redis = ws.app.state.redis
    api_key = settings.openrouter_api_key

    # µ-law → PCM 16kHz
    pcm_8k = audioop.ulaw2lin(mulaw_audio, 2)
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, MULAW_SAMPLE_RATE, WHISPER_SAMPLE_RATE, None)

    # STT
    stt = OpenRouterSTT(http_client, api_key, model=settings.stt_model)
    text = await stt.transcribe_pcm(pcm_16k, sample_rate=WHISPER_SAMPLE_RATE)
    if not text.strip():
        return None, ""
    logger.info(f"[Voice:{tenant_id}] Transcrito: {text[:80]}")

    # LLM
    tenant = await load_tenant_async(tenant_id, redis)
    llm = await get_llm_provider(http_client, tenant_id=tenant_id)
    tools = get_tools_for_tenant(tenant, channel=Channel.CALL)
    agent = AgentRouter(
        llm=llm,
        tools=tools,
        tenant_prompt=tenant.get_prompt("voz"),
        sender_id=caller_id,
        tenant_id=tenant_id,
    )

    session_key = f"{tenant_id}:{caller_id or 'voice_anonymous'}"
    history: list[Any] = []
    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            history = await session.get_history(session_key)
        except Exception:
            pass

    result = await agent.run(user_message=text, history=history)
    logger.info(f"[Voice:{tenant_id}] Respuesta: {result.response[:80]}")

    if redis:
        try:
            session = SessionManager(redis, llm=llm)
            relevant = [m for m in result.messages if m.role in ("user", "assistant") and m.content]
            await session.save_history(session_key, relevant)
        except Exception:
            pass

    # TTS
    tts = OpenRouterTTS(
        http_client, api_key,
        model=settings.tts_model,
        voice=settings.tts_voice,
        speed=settings.tts_speed,
    )
    mp3_bytes = await tts.synthesize(result.response)
    if not mp3_bytes:
        return None, text

    return _mp3_to_mulaw(mp3_bytes), text


def _mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    """Convert MP3 to mulaw 8kHz for Twilio."""
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
        await ws.send_text(
            json.dumps(
                {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                }
            )
        )
        await asyncio.sleep(0.018)

    await ws.send_text(
        json.dumps(
            {
                "event": "mark",
                "streamSid": stream_sid,
                "mark": {"name": "response_end"},
            }
        )
    )

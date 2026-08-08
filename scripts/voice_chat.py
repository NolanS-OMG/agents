"""
Voice chat interactivo via OpenRouter.
Habla por micrófono → transcripción (STT) → respuesta LLM → audio (TTS) → speaker.

Uso:
    uv run python scripts/voice_chat.py
    uv run python scripts/voice_chat.py --tenant santa_lena --estilo voz
    uv run python scripts/voice_chat.py --stt-model openai/whisper-large-v3 --tts-model microsoft/mai-voice-2-flash
    uv run python scripts/voice_chat.py --text-only   # solo texto, sin mic/speaker (para WSL sin audio)

Controles:
    - ENTER para empezar a grabar → ENTER para detener y enviar
    - Escribe 'q' + ENTER para salir
    - En modo --text-only: escribe tu mensaje directamente
"""

import argparse
import asyncio
import base64
import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
SAMPLE_RATE = 16000
CHANNELS = 1

DEFAULT_STT_MODEL = "openai/whisper-large-v3"
DEFAULT_TTS_MODEL = "microsoft/mai-voice-2"
DEFAULT_TTS_VOICE = "es-MX-Valeria:MAI-Voice-2"
DEFAULT_TTS_SPEED = 1.15
DEFAULT_LLM_MODEL = "google/gemini-2.5-flash-lite"

AUDIO_DIR = Path(__file__).resolve().parent.parent / "audio"
KEYBOARD_SOUND = AUDIO_DIR / "keyboard_sound.mp3"
FILLERS_DIR = AUDIO_DIR / "fillers"

# Pre-load keyboard sound and slice into random chunks
_keyboard_audio = None
_filler_audios: list[tuple[str, "AudioSegment"]] = []


def _load_audio_assets():
    """Load keyboard sound and fillers into memory once."""
    global _keyboard_audio, _filler_audios
    from pydub import AudioSegment

    if KEYBOARD_SOUND.exists():
        _keyboard_audio = AudioSegment.from_mp3(str(KEYBOARD_SOUND))
        _keyboard_audio = _keyboard_audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    if FILLERS_DIR.exists():
        for f in sorted(FILLERS_DIR.glob("*.mp3")):
            audio = AudioSegment.from_mp3(str(f))
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            _filler_audios.append((f.stem, audio))


def _get_keyboard_chunk(duration_ms: int = 2000) -> "AudioSegment | None":
    """Get a random chunk from the keyboard sound."""
    if _keyboard_audio is None:
        return None
    import random
    max_start = len(_keyboard_audio) - duration_ms
    if max_start <= 0:
        return _keyboard_audio[:duration_ms]
    start = random.randint(0, max_start)
    return _keyboard_audio[start:start + duration_ms]


def _get_random_filler() -> "AudioSegment | None":
    """Get a random filler muletilla."""
    if not _filler_audios:
        return None
    import random
    _, audio = random.choice(_filler_audios)
    return audio

HAS_SOUNDDEVICE = False
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except OSError:
    pass


def get_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        print("ERROR: OPENROUTER_API_KEY no encontrada en .env")
        sys.exit(1)
    return key


def _is_wsl() -> bool:
    try:
        return "microsoft" in os.uname().release.lower()
    except Exception:
        return False


def record_audio_wsl() -> bytes:
    """Graba audio usando PowerShell NAudio (accede al mic de Windows desde WSL).

    Requiere: scripts/record.ps1 (generado automáticamente si no existe).
    """
    scripts_dir = Path(__file__).resolve().parent
    ps1_path = scripts_dir / "record.ps1"
    win_ps1 = subprocess.run(
        ["wslpath", "-w", str(ps1_path)], capture_output=True, text=True
    ).stdout.strip()

    # Output file en /tmp (accesible desde Windows via \\wsl$\...)
    wsl_tmp = tempfile.mktemp(suffix=".wav", dir="/tmp")
    win_tmp = subprocess.run(
        ["wslpath", "-w", wsl_tmp], capture_output=True, text=True
    ).stdout.strip()

    print("\n  🎤 Grabando... (presiona ENTER para detener)")

    proc = subprocess.Popen(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", win_ps1, "-OutputFile", win_tmp],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        input()
    except EOFError:
        pass

    # Send newline to PowerShell's Read-Host to stop
    try:
        stdout, stderr = proc.communicate(input=b"\n", timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    if os.path.exists(wsl_tmp) and os.path.getsize(wsl_tmp) > 44:
        data = Path(wsl_tmp).read_bytes()
        duration_s = (len(data) - 44) / (SAMPLE_RATE * 2)
        print(f"  ⏱ Grabación: {duration_s:.1f}s")
        os.unlink(wsl_tmp)
        return data

    err = stderr.decode(errors="ignore").strip() if stderr else ""
    if err:
        print(f"  ⚠ Error grabando: {err[:200]}")
    else:
        print("  ⚠ No se generó archivo de audio.")
        print(f"    Verifica que record.ps1 exista en: {ps1_path}")
    return b""


def record_audio_sounddevice() -> bytes:
    """Graba audio con sounddevice (Linux nativo con PortAudio)."""
    print("\n  🎤 Grabando... (presiona ENTER para detener)")
    frames: list[np.ndarray] = []
    recording = True

    def callback(indata, frame_count, time_info, status):
        if recording:
            frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=callback,
        blocksize=1024,
    )
    stream.start()

    try:
        input()
    except EOFError:
        pass

    recording = False
    stream.stop()
    stream.close()

    if not frames:
        return b""

    audio_data = np.concatenate(frames, axis=0)
    return audio_data.tobytes()


def record_audio() -> bytes:
    """Graba audio. Usa el método adecuado según el entorno."""
    if _is_wsl():
        return record_audio_wsl()
    if HAS_SOUNDDEVICE:
        return record_audio_sounddevice()
    print("  ❌ No hay método de grabación disponible. Usa --text-only")
    return b""


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convierte PCM int16 raw a WAV."""
    import struct

    buf = io.BytesIO()
    data_size = len(pcm_bytes)
    file_size = 36 + data_size
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", file_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))  # PCM
    buf.write(struct.pack("<H", CHANNELS))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * CHANNELS * 2))
    buf.write(struct.pack("<H", CHANNELS * 2))
    buf.write(struct.pack("<H", 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_bytes)

    return buf.getvalue()


def play_audio(audio_bytes: bytes) -> None:
    """Reproduce audio MP3. Convierte a WAV y usa SoundPlayer en WSL."""
    from pydub import AudioSegment

    # Convertir MP3 a WAV (SoundPlayer de Windows solo acepta WAV)
    audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(wav_tmp.name, format="wav")
    wav_tmp.close()

    try:
        if _is_wsl():
            win_path = subprocess.run(
                ["wslpath", "-w", wav_tmp.name], capture_output=True, text=True
            ).stdout.strip()
            subprocess.run(
                [
                    "powershell.exe", "-c",
                    f'(New-Object System.Media.SoundPlayer("{win_path}")).PlaySync()',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        elif HAS_SOUNDDEVICE:
            samples = np.frombuffer(audio.raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(samples, samplerate=16000)
            sd.wait()
        else:
            for player in ["mpv", "ffplay", "paplay"]:
                try:
                    subprocess.run([player, wav_tmp.name], capture_output=True, timeout=30)
                    return
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            print(f"  💾 Audio guardado: {wav_tmp.name}")
            return
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"  ⚠ Error reproduciendo: {e}")
        print(f"  💾 Audio guardado: {wav_tmp.name}")
        return
    finally:
        try:
            os.unlink(wav_tmp.name)
        except OSError:
            pass


async def transcribe(client: httpx.AsyncClient, api_key: str, wav_bytes: bytes, model: str) -> str:
    """STT via OpenRouter."""
    audio_b64 = base64.b64encode(wav_bytes).decode()

    t = time.time()
    response = await client.post(
        f"{OPENROUTER_BASE}/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "input_audio": {"data": audio_b64, "format": "wav"},
            "language": "es",
            "temperature": 0.0,
            "response_format": "json",
        },
        timeout=30.0,
    )
    elapsed = int((time.time() - t) * 1000)

    if response.status_code != 200:
        print(f"  ❌ STT error {response.status_code}: {response.text[:200]}")
        return ""

    data = response.json()
    text = data.get("text", "")
    print(f"  📝 STT ({elapsed}ms, {model.split('/')[-1]}): {text}")
    return text


async def chat_llm(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    system_prompt: str,
    history: list[dict],
    user_text: str,
    play_hold_audio: bool = False,
) -> str:
    """LLM chat via OpenRouter. Plays hold audio if response takes >1.5s."""
    import threading

    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_text}]

    # Set up hold audio that triggers after delay
    # STT already took ~2s, so user has been waiting. Trigger faster.
    stop_hold = threading.Event()
    hold_thread = None
    if play_hold_audio and _keyboard_audio is not None:
        hold_thread = threading.Thread(target=_play_hold_sync, args=(stop_hold,), daemon=True)
        hold_thread.start()

    t = time.time()
    response = await client.post(
        f"{OPENROUTER_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": messages,
            "max_tokens": 300,
        },
        timeout=30.0,
    )
    elapsed = int((time.time() - t) * 1000)

    # Signal hold audio to stop
    stop_hold.set()

    if response.status_code != 200:
        print(f"  ❌ LLM error {response.status_code}: {response.text[:200]}")
        return "Disculpa, tuve un error."

    data = response.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    print(f"  🤖 LLM ({elapsed}ms, {usage.get('prompt_tokens', '?')}in/{usage.get('completion_tokens', '?')}out): {text}")

    # Wait for hold audio to finish (if it started playing)
    if hold_thread and hold_thread.is_alive():
        hold_thread.join(timeout=5)

    return text


def _play_hold_sync(stop_event: "threading.Event"):
    """Wait a natural pause, then play filler + keyboard."""
    # Pausa natural (~1s) — como si la persona procesara la pregunta
    if stop_event.wait(timeout=0.5):
        return

    # Muletilla
    filler = _get_random_filler()
    if filler and not stop_event.is_set():
        _play_audio_segment(filler)

    # Pausa corta entre muletilla y teclado
    if stop_event.wait(timeout=0.4):
        return

    # Keyboard (más fuerte, +8dB)
    if not stop_event.is_set():
        chunk = _get_keyboard_chunk(3000)
        if chunk:
            louder = chunk + 8
            _play_audio_segment(louder)


def _play_audio_segment(audio_seg) -> None:
    """Play a pydub AudioSegment synchronously (blocking, runs in background task)."""
    wav_tmp = tempfile.mktemp(suffix=".wav")
    audio_seg.export(wav_tmp, format="wav")
    try:
        if _is_wsl():
            win_path = subprocess.run(
                ["wslpath", "-w", wav_tmp], capture_output=True, text=True
            ).stdout.strip()
            subprocess.run(
                ["powershell.exe", "-c",
                 f'(New-Object System.Media.SoundPlayer("{win_path}")).PlaySync()'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
            )
        elif HAS_SOUNDDEVICE:
            samples = np.frombuffer(audio_seg.raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(samples, samplerate=audio_seg.frame_rate)
            sd.wait()
    except Exception:
        pass
    finally:
        try:
            os.unlink(wav_tmp)
        except OSError:
            pass


async def synthesize(
    client: httpx.AsyncClient, api_key: str, text: str, model: str, voice: str, speed: float = 1.0
) -> bytes | None:
    """TTS via OpenRouter."""
    t = time.time()
    payload: dict = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    if speed != 1.0:
        payload["speed"] = speed
    response = await client.post(
        f"{OPENROUTER_BASE}/audio/speech",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    elapsed = int((time.time() - t) * 1000)

    if response.status_code != 200:
        print(f"  ❌ TTS error {response.status_code}: {response.text[:200]}")
        return None

    audio_bytes = response.content
    print(f"  🔊 TTS ({elapsed}ms, {len(audio_bytes)//1024}KB, {model.split('/')[-1]})")
    return audio_bytes


async def main() -> None:
    parser = argparse.ArgumentParser(description="Voice chat interactivo via OpenRouter")
    parser.add_argument("--tenant", default="santa_lena")
    parser.add_argument("--estilo", default="voz")
    parser.add_argument("--stt-model", default=DEFAULT_STT_MODEL)
    parser.add_argument("--tts-model", default=DEFAULT_TTS_MODEL)
    parser.add_argument("--tts-voice", default=DEFAULT_TTS_VOICE)
    parser.add_argument("--tts-speed", type=float, default=DEFAULT_TTS_SPEED)
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL)
    parser.add_argument("--text-only", action="store_true", help="Solo texto, sin mic/speaker")
    args = parser.parse_args()

    can_record = HAS_SOUNDDEVICE or _is_wsl()
    text_only = args.text_only or not can_record
    if not can_record and not args.text_only:
        print("  ⚠ No hay método de grabación disponible, usando modo texto")
        print("    En WSL: el script usa PowerShell para grabar")
        print("    En Linux: sudo apt-get install -y libportaudio2\n")

    api_key = get_api_key()
    _load_audio_assets()

    print("=" * 60)
    print("  VOICE CHAT — OpenRouter STT + LLM + TTS")
    print("=" * 60)
    print(f"  STT: {args.stt_model}")
    print(f"  LLM: {args.llm_model}")
    print(f"  TTS: {args.tts_model} (voice: {args.tts_voice}, speed: {args.tts_speed})")
    print(f"  Tenant: {args.tenant} | Estilo: {args.estilo}")
    print(f"  Modo: {'TEXTO (escribes)' if text_only else 'VOZ (mic + speaker)'}")
    print("=" * 60)

    if text_only:
        print("\n  Escribe tu mensaje y presiona ENTER. 'q' para salir.\n")
    else:
        print("\n  ENTER para grabar → ENTER para detener → escuchas respuesta")
        print("  'q' para salir\n")

    system_prompt = "Eres un asistente de atencion al cliente. Responde de forma breve y natural, como en una llamada telefonica. Maximo 2-3 oraciones."

    # Load tenant from DB
    try:
        from tortoise import Tortoise
        from src.app.core.config import settings as app_settings
        from src.app.services.tenant_loader import load_tenant_async

        await Tortoise.init(
            db_url=app_settings.database_url,
            modules={"models": ["src.app.db.models"]},
        )
        tenant = await load_tenant_async(args.tenant)
        system_prompt = tenant.get_prompt(args.estilo)
        print(f"  ✓ Prompt cargado de tenant '{args.tenant}' (estilo: {args.estilo})\n")
    except Exception as e:
        print(f"  ⚠ No se pudo cargar tenant: {e}")
        print(f"    Usando prompt genérico\n")

    history: list[dict] = []

    async with httpx.AsyncClient() as client:
        while True:
            print("-" * 40)

            if text_only:
                try:
                    user_text = input("  Tú: ").strip()
                except EOFError:
                    print("\n  👋 Hasta luego!")
                    break
                if user_text.lower() == "q":
                    print("\n  👋 Hasta luego!")
                    break
                if not user_text:
                    continue
            else:
                user_input = input("  [ENTER para grabar, 'q' para salir]: ").strip()
                if user_input.lower() == "q":
                    print("\n  👋 Hasta luego!")
                    break

                audio_bytes = record_audio()
                if not audio_bytes:
                    print("  ⚠ No se grabó audio")
                    continue

                # WSL returns full WAV, sounddevice returns raw PCM
                if audio_bytes[:4] == b"RIFF":
                    wav_bytes = audio_bytes
                else:
                    duration_s = len(audio_bytes) / (SAMPLE_RATE * 2)
                    print(f"  ⏱ Grabación: {duration_s:.1f}s")
                    wav_bytes = pcm_to_wav(audio_bytes)

                user_text = await transcribe(client, api_key, wav_bytes, args.stt_model)
                if not user_text.strip():
                    print("  ⚠ No se entendió nada, intenta de nuevo")
                    continue

            # LLM (play hold audio if not text-only)
            assistant_text = await chat_llm(
                client, api_key, args.llm_model, system_prompt, history, user_text,
                play_hold_audio=not text_only,
            )

            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": assistant_text})

            # TTS
            audio = await synthesize(client, api_key, assistant_text, args.tts_model, args.tts_voice, args.tts_speed)
            if audio:
                print("  ▶ Reproduciendo...")
                try:
                    play_audio(audio)
                except Exception as e:
                    print(f"  ⚠ Error reproduciendo: {e}")
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    tmp.write(audio)
                    tmp.close()
                    print(f"  💾 Audio guardado: {tmp.name}")


async def _run() -> None:
    try:
        await main()
    finally:
        try:
            from tortoise import Tortoise
            await Tortoise.close_connections()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(_run())

# Plan: Agente de Voz (STT + LLM Router + TTS)

## Objetivo

Agregar capacidades de voz al agente existente usando el enfoque cascada: Audio → STT → Texto → LLM Router (el que ya tenemos) → Texto → TTS → Audio. Dos funcionalidades:

1. **Leer audio messages de WhatsApp** — transcribir y procesar como texto
2. **Llamadas de voz por WhatsApp Calling API** — conversación bidireccional en tiempo real

---

## Proveedores elegidos

### STT: Faster-Whisper (local)

| Aspecto | Detalle |
|---------|---------|
| Modelo | `large-v3` INT8 (~3GB VRAM) o `distil-large-v3` (~2.5GB) |
| Hardware | RTX 5060 8GB — sobra VRAM para STT |
| Latencia | ~1-2s para clips de 10s en GPU |
| Calidad español | Excelente (Whisper es state-of-the-art en español) |
| Costo | $0 — local |
| Lib Python | `faster-whisper` (CTranslate2 backend) |

**Alternativa cloud (fallback):** Groq Whisper API — free tier con 7,200 seg/día de audio.

### TTS: Edge-TTS (Microsoft, gratuito)

| Aspecto | Detalle |
|---------|---------|
| Voces es-MX | `es-MX-DaliaNeural` (mujer), `es-MX-JorgeNeural` (hombre) |
| Calidad | Neural, muy natural para español mexicano |
| Costo | $0 — sin API key, sin límites conocidos |
| Latencia | ~500-800ms para frases cortas (streaming disponible) |
| Lib Python | `edge-tts` (async nativo) |
| Formato salida | MP3 u OGG (configurable) |

**Alternativa local (si Edge-TTS se bloquea):** Piper TTS — voces español (`es_MX`) open source, ~50ms en CPU, calidad aceptable pero menos natural que Edge.

---

## Funcionalidad 1: Leer audios de WhatsApp

### Cómo funciona WhatsApp Cloud API con audio

1. El usuario envía un audio → webhook llega con `type: "audio"` y un `media_id`
2. Obtener URL del media: `GET /v25.0/{media_id}` con Bearer token
3. Descargar el archivo: `GET {url}` con Bearer token → OGG/OPUS
4. Transcribir con Faster-Whisper → texto
5. Pasar texto al AgentRouter (flujo normal)
6. Responder por texto (o por audio si queremos)

### Archivos a crear/modificar

| Archivo | Cambio |
|---------|--------|
| `src/app/services/transcriber.py` | **NUEVO** — clase `Transcriber` que recibe bytes de audio y retorna texto |
| `src/app/services/synthesizer.py` | **NUEVO** — clase `Synthesizer` que recibe texto y retorna bytes de audio |
| `src/app/channels/whatsapp.py` | Ampliar `parse_incoming` para manejar `type: "audio"` |
| `src/app/api/routes/webhook.py` | Si incoming tiene audio, transcribir antes de pasar al router |
| `src/app/core/config.py` | Agregar: `whisper_model`, `tts_voice`, `voice_enabled` |
| `src/app/core/lifespan.py` | Inicializar Transcriber en startup (carga modelo en VRAM) |

### Flujo detallado

```
WhatsApp audio msg → webhook
  → parse_incoming detecta type="audio"
  → download_media(media_id) → bytes OGG
  → transcriber.transcribe(audio_bytes) → texto
  → agent.run(texto) → resultado
  → responder por texto (o TTS → send audio)
```

### Transcriber service

```python
from faster_whisper import WhisperModel

class Transcriber:
    def __init__(self, model_size: str = "large-v3", device: str = "cuda"):
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def transcribe(self, audio_bytes: bytes) -> str:
        # Escribir a tempfile, transcribir, retornar texto
        segments, _ = self._model.transcribe(temp_path, language="es")
        return " ".join(s.text for s in segments)
```

### Download media de WhatsApp

```python
async def download_media(http_client, media_id: str, token: str) -> bytes:
    # 1. Obtener URL
    resp = await http_client.get(
        f"https://graph.facebook.com/v25.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    url = resp.json()["url"]
    # 2. Descargar bytes
    media_resp = await http_client.get(url, headers={"Authorization": f"Bearer {token}"})
    return media_resp.content
```

---

## Funcionalidad 2: Llamadas de voz WhatsApp Calling API

### Requisitos de Meta

- WhatsApp Business API con llamadas habilitadas
- El usuario debe iniciar la llamada (inbound) o dar opt-in previo
- Audio llega como WebSocket stream (raw audio)

### Arquitectura

```
[Usuario llama por WhatsApp]
        │
        ▼
[Meta Cloud API] → webhook event: call_incoming
        │
        ▼
[Backend FastAPI] → POST /calls (accept)
        │
        ▼
[WebSocket Media Stream] ←→ [Voice Pipeline]
                                    │
                              ┌─────┴─────┐
                              │   Buffer   │
                              │  (VAD +    │
                              │  silence)  │
                              └─────┬─────┘
                                    │ (cuando detecta fin de frase)
                                    ▼
                              [Faster-Whisper STT]
                                    │ texto
                                    ▼
                              [AgentRouter.run(texto)]
                                    │ respuesta
                                    ▼
                              [Edge-TTS → audio]
                                    │
                                    ▼
                              [Enviar audio por WebSocket]
```

### Archivos a crear

| Archivo | Descripción |
|---------|-------------|
| `src/app/api/routes/voice.py` | **NUEVO** — webhook de llamadas + WebSocket `/ws/voice-stream` |
| `src/app/services/voice_pipeline.py` | **NUEVO** — orquesta VAD → STT → Router → TTS → audio out |
| `src/app/services/vad.py` | **NUEVO** — Voice Activity Detection (silero-vad, ~5MB) |

### Voice Pipeline

```python
class VoicePipeline:
    def __init__(self, transcriber, synthesizer, agent_router):
        self._transcriber = transcriber
        self._synthesizer = synthesizer
        self._agent = agent_router
        self._vad = SileroVAD()
        self._audio_buffer = bytearray()

    async def handle_audio_chunk(self, chunk: bytes) -> bytes | None:
        self._audio_buffer.extend(chunk)

        if self._vad.detect_end_of_speech(self._audio_buffer):
            # Transcribir el buffer acumulado
            text = self._transcriber.transcribe(bytes(self._audio_buffer))
            self._audio_buffer.clear()

            if not text.strip():
                return None

            # Pasar por el mismo LLM router
            result = await self._agent.run(user_message=text)

            # Sintetizar respuesta
            audio_response = await self._synthesizer.synthesize(result.response)
            return audio_response

        return None
```

### VAD (Voice Activity Detection)

Usamos `silero-vad` (modelo PyTorch de ~5MB):
- Detecta cuándo el usuario dejó de hablar
- Evita cortar a mitad de frase
- Threshold configurable (500ms de silencio = fin de turno)

---

## Dependencias nuevas

```toml
# pyproject.toml
[project.optional-dependencies]
voice = [
    "faster-whisper>=1.0.0",
    "edge-tts>=6.1.0",
    "silero-vad>=4.0",
    "pydub>=0.25.1",       # conversión de formatos de audio
]
```

Se instalan con `uv sync --extra voice`. El bot de texto sigue funcionando sin ellas.

---

## Config additions

```python
# config.py
voice_enabled: bool = False
whisper_model: str = "large-v3"
whisper_device: str = "cuda"
tts_voice: str = "es-MX-DaliaNeural"
vad_silence_threshold_ms: int = 500
```

---

## Orden de implementación

### Sprint 1: Audio messages WhatsApp (más valor inmediato)

1. `services/transcriber.py` — wrapper de faster-whisper
2. Ampliar `whatsapp.py` para parsear audio messages + download media
3. Ampliar `webhook.py` para transcribir antes de procesar
4. Test: enviar audio por WhatsApp → recibir respuesta texto

### Sprint 2: TTS para responder con audio

5. `services/synthesizer.py` — wrapper de edge-tts
6. Método `send_audio` en WhatsAppAdapter (upload media + enviar)
7. Config flag para responder con audio o texto

### Sprint 3: Llamadas en tiempo real (más complejo)

8. `services/vad.py` — Silero VAD
9. `services/voice_pipeline.py` — orquestador
10. `api/routes/voice.py` — WebSocket endpoint
11. Integrar con WhatsApp Calling API webhooks

---

## Consideraciones

### VRAM budget (RTX 5060, 8GB)

| Componente | VRAM |
|------------|------|
| Faster-Whisper large-v3 INT8 | ~3 GB |
| Silero VAD | ~50 MB |
| Edge-TTS | 0 (cloud) |
| **Total** | **~3 GB** |

Sobran ~5GB. Si necesitamos más, podemos bajar a `distil-large-v3` (~2.5GB) o `medium` (~1.5GB).

### Latencia estimada (cascada completa)

| Paso | Tiempo |
|------|--------|
| STT (10s audio) | ~1.5s |
| LLM (OpenRouter) | ~2-5s |
| TTS (frase corta) | ~0.8s |
| **Total** | **~4-7s** |

Para audio messages es aceptable. Para llamadas en tiempo real es borderline — optimizable con:
- Streaming TTS (empezar a hablar antes de terminar de generar)
- Modelo LLM más rápido para voz (Groq con Llama, ~200ms)
- STT con VAD chunking más agresivo

### Fallback si la GPU no está disponible

Si el servidor de producción no tiene GPU (ej: Docker en VPS):
- STT: usar Groq Whisper API (free, 7200s/día)
- TTS: Edge-TTS sigue funcionando (cloud)
- Sin cambios en el flujo

---

## Diferido (no implementar ahora)

- ❌ Audio-to-audio nativo (OpenAI Realtime / Gemini Live)
- ❌ Llamadas PSTN vía Twilio/Telnyx
- ❌ Clonación de voz con ElevenLabs
- ❌ Barge-in detection (interrumpir al bot mientras habla)

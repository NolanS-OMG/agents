# OpenRouter — Modelos de Voz (STT + TTS)

> Investigación: 2026-08-08
> Objetivo: Reemplazar edge-tts (calidad baja) y Groq STT por modelos unificados en OpenRouter

## Estado actual

| Servicio | Implementación | Problema |
|----------|---------------|----------|
| STT (cloud) | Groq Whisper Large v3 Turbo | Requiere API key separada, no unificado |
| STT (local) | faster-whisper (CUDA) | Solo sirve con GPU, no en producción |
| TTS | edge-tts (Microsoft Edge) | Calidad objetivamente mala, voces robóticas |

---

## Endpoints OpenRouter

| Función | Endpoint | Método |
|---------|----------|--------|
| Transcripción (STT) | `POST /api/v1/audio/transcriptions` | JSON (base64) o multipart |
| Síntesis (TTS) | `POST /api/v1/audio/speech` | JSON → raw audio bytes |

Base URL: `https://openrouter.ai/api/v1`
Auth: `Authorization: Bearer <OPENROUTER_API_KEY>` (la misma key que ya usamos para chat)

---

## STT — Modelos de Transcripción

### Top candidatos para nuestro caso

| Modelo | Precio | Unidad | Español | Notas |
|--------|--------|--------|---------|-------|
| **`qwen/qwen3-asr-flash-2026-02-10`** | $0.000035/s | por segundo | Si | El mas barato. 11 idiomas. |
| **`fish-audio/transcribe-1`** | $0.0001/s | por segundo | Si | Timestamps por palabra, auto-detect idioma |
| `openai/whisper-large-v3` | $0.0015/s | por segundo | Si | 99+ idiomas, referencia de calidad |
| `openai/gpt-4o-mini-transcribe` | $1.25/M in + $5/M out | por token | Si | Mas caro pero mayor accuracy |
| `deepgram/nova-3` | $0.0043/s | por segundo | Si | Multilingue, buena reputacion |

### Tabla completa (14 modelos disponibles)

| Modelo | Precio | Notas |
|--------|--------|-------|
| `qwen/qwen3-asr-flash-2026-02-10` | $0.000035/s | Mas barato |
| `fish-audio/transcribe-1` | $0.0001/s | Word timestamps |
| `openai/gpt-4o-mini-transcribe` | $1.25/$5 per M tokens | Token-based |
| `openai/gpt-4o-transcribe` | $2.50/$10 per M tokens | Alta calidad |
| `nvidia/parakeet-tdt-0.6b-v3` | $0.0015/s | 670k+ hrs training |
| `openai/whisper-large-v3` | $0.0015/s | Referencia |
| `mistralai/voxtral-mini-transcribe` | $0.003/s | — |
| `deepgram/nova-3` | $0.0043/s | Multilingue |
| `openai/gpt-transcribe` | $0.0045/s | Keyword hints |
| `openai/whisper-1` | $0.006/s | 50+ idiomas |
| `google/chirp-3` | $0.016/s | Auto-puntuacion |
| `openai/whisper-large-v3-turbo` | $0.04/s | Speed-optimized |
| `x-ai/grok-stt-1.0` | $0.10/s | Diarizacion |
| `microsoft/mai-transcribe-1.5` | $0.36/s | 43 idiomas, caro |

### Request STT (JSON con base64)

```python
response = await client.post(
    "https://openrouter.ai/api/v1/audio/transcriptions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "qwen/qwen3-asr-flash-2026-02-10",
        "input_audio": {"data": base64_audio, "format": "ogg"},
        "language": "es",
        "temperature": 0.0,
        "response_format": "json",
    }
)
# Response: {"text": "texto transcrito", "usage": {"seconds": 5.2, "cost": 0.000182}}
```

Formatos aceptados: WAV, MP3, FLAC, M4A, OGG, WebM, AAC. Limite: 25 MB.

---

## TTS — Modelos de Sintesis de Voz

### Top candidatos para nuestro caso

| Modelo | Precio/char | Español | Voces | Notas |
|--------|-------------|---------|-------|-------|
| **`fish-audio/s2.1-pro-free:free`** | GRATIS | Si | — | Solo para dev/testing |
| **`hexgrad/kokoro-82m`** | $0.00000062 | Si | 54 | 8 idiomas, el mas barato pagado |
| **`fish-audio/s2.1-pro`** | $0.000015 | Si | — | Produccion, voice cloning, emocional |
| **`microsoft/mai-voice-2-flash`** | $0.000015 | Si | 4 | Low-latency, 15 idiomas, 24kHz |
| **`deepgram/aura-2`** | $0.00003 | Si | 90 | Catalogo de voces mas grande |

### Tabla completa (19 modelos disponibles)

| Modelo | Precio/char | Idiomas | Notas |
|--------|-------------|---------|-------|
| `hexgrad/kokoro-82m` | $0.00000062 | 8 | Mas barato pagado, 54 voces |
| `zyphra/zonos-v0.1-transformer` | $0.000007 | EN only | 5 voces |
| `zyphra/zonos-v0.1-hybrid` | $0.000007 | EN only | Hybrid arch |
| `canopylabs/orpheus-3b-0.1-ft` | $0.000007 | EN only | Prosodia natural |
| `sesame/csm-1b` | $0.000007 | EN only | Conversational |
| `fish-audio/s1` | $0.000015 | Multi | Controles emocionales |
| `fish-audio/s2-pro` | $0.000015 | Multi | Multi-speaker |
| `fish-audio/s2.1-pro` | $0.000015 | Multi | Voice cloning |
| `microsoft/mai-voice-2-flash` | $0.000015 | 15 | Low-latency |
| `x-ai/grok-voice-tts-1.0` | $0.000015 | 20+ | Auto-detection |
| `qwen/qwen-audio-3.0-tts-flash` | $0.000015 | Multi | Fast |
| `mistralai/voxtral-mini-tts-2603` | $0.000016 | Multi | Zero-shot cloning |
| `qwen/qwen-audio-3.0-tts-plus` | $0.00002 | Multi | Alta calidad |
| `microsoft/mai-voice-2` | $0.000022 | 15 | Estilos expresivos |
| `deepgram/aura-2` | $0.00003 | Multi | 90 voces |
| `minimax/speech-2.8-turbo` | $0.00006 | Multi | Custom voice IDs |
| `minimax/speech-2.8-hd` | $0.0001 | Multi | HD quality |
| `fish-audio/s2.1-pro-free:free` | GRATIS | Multi | Solo testing |
| `google/gemini-3.1-flash-tts-preview` | $0.001/M in + $20/M out | 30 | Token-based |

### Request TTS

```python
response = await client.post(
    "https://openrouter.ai/api/v1/audio/speech",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "fish-audio/s2.1-pro",
        "input": "Hola, bienvenido. En que puedo ayudarte?",
        "voice": "alloy",  # depende del modelo
        "response_format": "mp3",  # o "pcm" para real-time
    }
)
audio_bytes = response.content  # raw audio, NO es JSON
```

---

## Comparacion de costos (ejemplo: 1 min de audio procesado)

### STT — Transcribir 1 minuto de audio

| Modelo | Costo |
|--------|-------|
| Qwen ASR Flash | $0.0021 |
| Fish Transcribe 1 | $0.006 |
| Whisper Large v3 | $0.09 |
| Deepgram Nova-3 | $0.258 |
| Groq (actual) | ~$0.006 (pero key separada) |

### TTS — Sintetizar respuesta de 100 chars (~25 palabras)

| Modelo | Costo |
|--------|-------|
| Kokoro 82M | $0.000062 |
| Fish S2.1 Pro | $0.0015 |
| MAI Voice 2 Flash | $0.0015 |
| Deepgram Aura-2 | $0.003 |
| edge-tts (actual) | GRATIS (pero mala calidad) |

---

## Voces seleccionadas — Microsoft MAI Voice 2

Probadas el 2026-08-08. Ranking basado en escucha real.

### Ganadora (default)

| Modelo | Voice ID | Descripcion |
|--------|----------|-------------|
| `microsoft/mai-voice-2` | `es-MX-Valeria:MAI-Voice-2` | Mujer mexicana, muy natural, #1 audiorealism |

### Alternativas testeadas (todas buenas)

| Voice ID | Genero | Acento | Notas |
|----------|--------|--------|-------|
| `es-MX-Valeria:MAI-Voice-2` | Mujer | MX | **DEFAULT.** La mas natural de todas. |
| `es-MX-Alejo:MAI-Voice-2` | Hombre | MX | Muy buena, masculina formal. |
| `es-MX-Valeria:MAI-Voice-2-Flash` | Mujer | MX | Version rapida (~600ms vs ~1.5s), menor calidad. |
| `es-MX-Alejo:MAI-Voice-2-Flash` | Hombre | MX | Version rapida masculina. |

### Todas las voces es-MX disponibles en MAI-Voice-2-Flash

Estas son más rápidas (~500-800ms) pero suenan más robóticas que la v2:

| Voice ID | Genero | Notas |
|----------|--------|-------|
| `es-MX-DaliaNeural` | Mujer | La mas comun |
| `es-MX-JorgeNeural` | Hombre | Formal |
| `es-MX-BeatrizNeural` | Mujer | — |
| `es-MX-CandelaNeural` | Mujer | Joven, calida |
| `es-MX-CarlotaNeural` | Mujer | — |
| `es-MX-CecilioNeural` | Hombre | — |
| `es-MX-GerardoNeural` | Hombre | — |
| `es-MX-LarissaNeural` | Mujer | — |
| `es-MX-LibertoNeural` | Hombre | — |
| `es-MX-LucianoNeural` | Hombre | Grave |
| `es-MX-MarinaNeural` | Mujer | — |
| `es-MX-NuriaNeural` | Mujer | — |
| `es-MX-PelayoNeural` | Hombre | — |
| `es-MX-RenataNeural` | Mujer | Profesional |
| `es-MX-YagoNeural` | Hombre | — |

### Estilos emocionales (MAI-Voice-2 Valeria/Alejo)

Ambas voces soportan 18 estilos via parametro `style`:
angry, confused, determined, disgusted, embarrassed, excited, fearful, happy, hopeful, jealous, joyful, regretful, relieved, sad, shouting, softvoice, surprised, whispering

### Comparativa de precios

| Modelo | Latencia | Precio | Calidad |
|--------|---------|--------|---------|
| `microsoft/mai-voice-2` | ~1.5s | $22/M chars | La mejor |
| `microsoft/mai-voice-2-flash` | ~600ms | $15/M chars | Buena (robotica) |

---

## Recomendacion final

### Default actual

| Servicio | Modelo | Voice | Razon |
|----------|--------|-------|-------|
| STT | `qwen/qwen3-asr-flash-2026-02-10` | — | Mas barato, buen español |
| TTS | `microsoft/mai-voice-2` | `es-MX-Valeria:MAI-Voice-2` | La mas natural en MX |

### Si se necesita menor latencia (ej: llamadas en vivo)

| Servicio | Modelo | Voice | Razon |
|----------|--------|-------|-------|
| STT | `qwen/qwen3-asr-flash-2026-02-10` | — | — |
| TTS | `microsoft/mai-voice-2-flash` | `es-MX-DaliaNeural` | 600ms vs 1.5s |

### Ventaja de unificar en OpenRouter

1. **Una sola API key** — ya la tenemos configurada
2. **Una sola libreria** — httpx que ya usamos
3. **Mismo patron** — se integra con el provider factory existente
4. **Facil cambiar** — solo cambiar model ID para probar alternativas

---

## Arquitectura propuesta

```
src/app/services/
  stt_openrouter.py    # Nuevo: STT via OpenRouter (reemplaza stt_cloud.py/Groq)
  tts_openrouter.py    # Nuevo: TTS via OpenRouter (reemplaza synthesizer.py/edge-tts)
  voice_pipeline.py    # Refactor: usa los nuevos servicios
```

Config en `.env`:
```
STT_MODEL=qwen/qwen3-asr-flash-2026-02-10
TTS_MODEL=microsoft/mai-voice-2
TTS_VOICE=es-MX-Valeria:MAI-Voice-2
```

El `http_client` compartido de lifespan se reutiliza — sin instanciar clientes nuevos.

# Investigación: Llamadas de Voz en Tiempo Real con IA (STT → LLM → TTS)

## 1. VAD — Voice Activity Detection

### El problema central

Necesitamos saber cuándo el usuario **dejó de hablar** para enviar su audio al STT. Esto se llama "endpointing" o "turn detection".

### Opciones

#### A) Energy-based (RMS threshold) — NO RECOMENDADO

```python
avg_energy = sum(abs(b - 128) for b in chunk) / len(chunk)
```

**Por qué falla en llamadas telefónicas:**
- Ruido de fondo en celulares (calle, carro, ventilador)
- Respiración del usuario se detecta como "habla"
- Mulaw encoding distorsiona los niveles de energía
- Un solo chunk ruidoso reinicia el timer de silencio

#### B) Silero VAD — RECOMENDADO

**Repo:** https://github.com/snakers4/silero-vad

- Modelo ONNX de ~2MB (ya incluido en faster-whisper)
- Retorna probabilidad 0.0-1.0 de que hay voz
- Soporta 8kHz y 16kHz directamente
- Frame size: 256 samples @8kHz (32ms) o 512 @16kHz
- Threshold recomendado: 0.5

**Input esperado:** float32 numpy array normalizado [-1.0, 1.0]

**Para usarlo con Twilio (mulaw 8kHz):**
```python
# 1. Decodificar mulaw a PCM int16
pcm = audioop.ulaw2lin(mulaw_bytes, 2)
# 2. Convertir a float32 normalizado
samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
# 3. Alimentar a Silero en frames de 256 samples
prob = vad.process_frame(samples)
```

#### C) WebRTC VAD — alternativa legacy

**Repo:** https://github.com/wiseman/py-webrtcvad
- Más rápido pero menos preciso que Silero
- Solo retorna 0/1 (sin probabilidad)
- No se mantiene desde 2017

### Cómo lo hacen los de producción

| Plataforma | Método |
|-----------|--------|
| Vapi.ai | Silero VAD + silence timeout adaptativo |
| Retell.ai | VAD propio + "turn detection" con LLM |
| Bland.ai | Silero VAD + filler words durante procesamiento |
| LiveKit | Silero VAD con pre-buffer de 300ms |
| Pipecat | Silero VAD + state machine (LISTENING/SPEAKING) |

### Configuración recomendada

```python
vad_threshold = 0.5          # Probabilidad mínima para considerar "voz"
min_speech_ms = 150          # Mínimo de voz antes de activar (evita falsos)
end_of_turn_ms = 700         # Silencio para considerar fin de turno
prefix_padding_ms = 300      # Audio que guardamos ANTES del inicio de voz
max_utterance_s = 30         # Flush forzado si hablan sin parar
```

---

## 2. Formato de Audio — Twilio Media Streams

### Lo que Twilio envía

- **Encoding:** mulaw (G.711 µ-law)
- **Sample rate:** 8000 Hz
- **Channels:** 1 (mono)
- **Chunk:** cada mensaje WebSocket = 20ms = 160 bytes de mulaw
- **Formato:** base64 dentro de JSON `{"event": "media", "media": {"payload": "..."}}`

### Conversiones necesarias

```
RECEPCIÓN:
Twilio mulaw 8kHz → PCM int16 8kHz → float32 (para VAD)
                  → PCM int16 16kHz (para Whisper, necesita upsample)

ENVÍO:
Edge-TTS MP3 → PCM int16 → mulaw 8kHz → base64 → JSON → WebSocket
```

### Código de conversión (en memoria, sin disco)

```python
import audioop
import numpy as np

# Recibir: mulaw → PCM 16kHz (para Whisper)
def mulaw_to_pcm16k(mulaw_bytes: bytes) -> bytes:
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
    return pcm_16k

# Recibir: mulaw → float32 (para Silero VAD)
def mulaw_to_float32(mulaw_bytes: bytes) -> np.ndarray:
    pcm = audioop.ulaw2lin(mulaw_bytes, 2)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

# Enviar: PCM → mulaw (para Twilio)
def pcm16k_to_mulaw(pcm_16k: bytes) -> bytes:
    pcm_8k, _ = audioop.ratecv(pcm_16k, 2, 1, 16000, 8000, None)
    return audioop.lin2ulaw(pcm_8k, 2)
```

### MP3 → mulaw sin ffmpeg (pydub en memoria)

```python
from pydub import AudioSegment
import io

def mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
    audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
    pcm = audio.raw_data
    return audioop.lin2ulaw(pcm, 2)
```

---

## 3. Estrategia de Buffering

### El problema del buffer

- Muy poco buffer → cortas palabras a la mitad
- Mucho buffer → latencia alta (esperas demasiado)
- Pausa mid-frase ("quiero... eh... una hamburguesa") → no debes cortar en "quiero"

### Patrón: Ring Buffer con Pre-padding

```python
from collections import deque

class AudioBuffer:
    def __init__(self, pre_padding_ms: int = 300, sample_rate: int = 8000):
        # Pre-buffer: guarda audio ANTES de que se detecte voz
        pre_frames = int(pre_padding_ms / 32)  # 32ms por frame Silero @8kHz
        self._pre_buffer = deque(maxlen=pre_frames)
        self._speech_buffer = bytearray()
        self._is_speaking = False

    def add_frame(self, frame: bytes, is_speech: bool):
        if not self._is_speaking:
            self._pre_buffer.append(frame)
            if is_speech:
                self._is_speaking = True
                # Incluir pre-buffer para no cortar inicio
                for f in self._pre_buffer:
                    self._speech_buffer.extend(f)
        else:
            self._speech_buffer.extend(frame)

    def flush(self) -> bytes:
        data = bytes(self._speech_buffer)
        self._speech_buffer.clear()
        self._is_speaking = False
        return data
```

### Streaming STT vs Batch STT

| Approach | Latencia | Precisión | Complejidad |
|----------|----------|-----------|-------------|
| Batch (esperar fin de turno) | +700ms (silence) | Alta | Baja |
| Streaming (enviar chunks) | Tiempo real | Media | Alta |

**Recomendación:** Batch con Faster-Whisper. Es más simple y la calidad es mejor. La latencia la domina el LLM, no el STT.

---

## 4. Latencia — El Problema Principal

### Budget de latencia actual (nuestro sistema)

| Paso | Tiempo actual |
|------|---------------|
| VAD end-of-turn silence | 700ms |
| Conversión mulaw→PCM | <1ms |
| Faster-Whisper STT (base, CPU) | 500-1500ms |
| LLM OpenRouter (free tier) | 2000-5000ms |
| Edge-TTS | 500-800ms |
| ffmpeg MP3→mulaw | 50-100ms |
| **Total** | **4-8 segundos** |

### Budget optimizado (alcanzable)

| Paso | Tiempo | Cómo |
|------|--------|------|
| VAD end-of-turn | 500ms | Threshold más agresivo |
| Conversión | <1ms | En memoria |
| STT (distil-large-v3, GPU) | 200-400ms | GPU + modelo optimizado |
| LLM (Groq, Llama 3.3 70B) | 200-400ms | **Cambiar provider para voz** |
| Edge-TTS (primera frase) | 300-500ms | Streaming parcial |
| Conversión in-memory | 20-30ms | pydub sin disco |
| **Total** | **1.2-1.8 segundos** |

### Técnicas para reducir latencia percibida

**1. Filler audio** — mientras procesas, envía "Mmm, déjame ver..." o un sonido de typing
```python
FILLERS = ["Mmm, un momento.", "Déjame revisar.", "Claro, dame un segundo."]
```

**2. Streaming TTS por oraciones** — no esperes toda la respuesta LLM
```
LLM genera: "Tenemos tres opciones. [enviar TTS] La primera es..."
```

**3. Pre-caché de frases comunes** — saludo, despedida, "no entendí"
```python
PRECACHED = {
    "greeting": synthesize("Hola, bienvenido. En qué puedo ayudarte?"),
    "not_understood": synthesize("Perdona, no te escuché bien. Puedes repetir?"),
}
```

**4. LLM más rápido para voz** — Groq es 10-20x más rápido que OpenRouter free

### Latencia aceptable para conversación

- **<1.5s** — se siente natural, como hablar con una persona
- **1.5-2.5s** — aceptable, como un IVR moderno
- **2.5-4s** — tolerable con filler audio
- **>4s** — el usuario cuelga o repite la pregunta

---

## 5. Barge-in (Interrupciones)

### ¿Necesitamos echo cancellation?

**NO** con Twilio Media Streams. El audio inbound y outbound son streams separados a nivel de red. El audio que envías al usuario NO aparece en el stream que recibes.

### Cómo implementar barge-in

```python
# Cuando detectas voz del usuario MIENTRAS estás en estado SPEAKING:
# 1. Enviar "clear" para detener el audio que se está reproduciendo
await ws.send_text(json.dumps({
    "event": "clear",
    "streamSid": stream_sid,
}))
# 2. Cancelar la generación de TTS en curso
# 3. Transicionar a estado LISTENING
```

### State Machine

```
LISTENING → (voz detectada) → SPEECH_DETECTED
SPEECH_DETECTED → (silencio >= 700ms) → PROCESSING
PROCESSING → (respuesta lista) → SPEAKING
SPEAKING → (playback completo) → LISTENING
SPEAKING → (usuario interrumpe) → LISTENING  [barge-in]
```

### Detectar barge-in vs ruido

- Solo activar barge-in si hay **>150ms de voz continua** durante SPEAKING
- Ruido de fondo aislado (<150ms) se ignora
- Si el usuario solo dice "mhm" o "ajá" (backchannel), ignorar también

---

## 6. Implementaciones Open Source de Referencia

### Pipecat (by Daily.co) — el más completo

**Repo:** https://github.com/pipecat-ai/pipecat

- Framework Python para voice AI pipelines
- Soporte nativo para Twilio, LiveKit, Daily, WebRTC
- STT/TTS/LLM todos como componentes intercambiables
- VAD con Silero integrado
- State machine de turn-taking built-in
- **Arquitectura:** pipeline de frames (audio/text frames fluyen por processors)

### LiveKit Agents

**Repo:** https://github.com/livekit/agents

- SDK para construir voice agents sobre LiveKit (WebRTC)
- Turn detection con Silero VAD
- Barge-in automático
- Menos flexible que Pipecat pero más fácil de usar

### Twilio call-gpt

**Repo:** https://github.com/twilio-labs/call-gpt

- Ejemplo oficial de Twilio para voz con GPT
- Node.js (no Python)
- Usa GPT-4 + ElevenLabs/Deepgram
- Referencia para el protocolo de Media Streams

### Vocode

**Repo:** https://github.com/vocodedev/vocode-python
- Menos activo desde 2024
- Buen diseño de abstracciones pero menos robusto

---

## 7. Twilio Media Streams — Protocolo Completo

### Mensajes que recibes

```json
// Stream iniciado
{"event": "start", "start": {"streamSid": "MZ...", "callSid": "CA...", "accountSid": "AC..."}}

// Audio del usuario (cada 20ms)
{"event": "media", "media": {"payload": "<base64 mulaw>", "timestamp": "123", "chunk": "1"}}

// Stream terminado (usuario cuelga)
{"event": "stop"}

// Confirmación de que tu audio se reprodujo
{"event": "mark", "mark": {"name": "tu_nombre_custom"}}
```

### Mensajes que envías

```json
// Enviar audio al usuario
{"event": "media", "streamSid": "MZ...", "media": {"payload": "<base64 mulaw>"}}

// Detener audio en reproducción (barge-in)
{"event": "clear", "streamSid": "MZ..."}

// Marcar un punto en el audio (para tracking)
{"event": "mark", "streamSid": "MZ...", "mark": {"name": "sentence_1_end"}}
```

### Notas importantes

- **160 bytes mulaw = 20ms de audio** a 8kHz
- El stream es **full-duplex** — puedes enviar y recibir simultáneamente
- `clear` es instantáneo — útil para barge-in
- `mark` te notifica cuando el audio previo terminó de reproducirse

---

## 8. Pitfalls Comunes

### Por qué nuestra detección de silencio falló

1. **Math incorrecta:** tratábamos mulaw como PCM linear (`b - 128`). En mulaw, 0xFF es silencio, no 128.
2. **Threshold fijo:** un solo chunk ruidoso reseteaba el timer completo.
3. **Sin modelo de voz:** energy-based no distingue voz de ruido de fondo.

### Otros problemas comunes

- **Whisper hallucinations:** con audio silencioso/ruidoso, Whisper puede inventar texto ("Thanks for watching", "Subtítulos por.."). Filtrar resultados cortos o repetitivos.
- **Memory leak en llamadas largas:** buffers que crecen infinitamente. Usar `max_utterance_s` para flush forzado.
- **Race condition:** usuario habla mientras aún procesas la frase anterior. Necesitas generation_id para invalidar respuestas viejas.
- **WebSocket muere:** Twilio reintenta pero el estado se pierde. Guardar estado en Redis por call_sid.

---

## 9. Arquitectura Recomendada para Nuestro Sistema

### Componentes

```
┌─────────────────────────────────────────────────┐
│                WebSocket Handler                 │
│  (recibe audio, envía audio, maneja eventos)    │
└────────┬──────────────────────────────┬─────────┘
         │ audio frames                 ▲ mulaw chunks
         ▼                              │
┌─────────────────┐              ┌──────────────┐
│  Silero VAD     │              │  TTS → mulaw │
│  (detect turn)  │              │  (Edge-TTS)  │
└────────┬────────┘              └──────▲───────┘
         │ end-of-turn                  │ texto
         ▼                              │
┌─────────────────┐              ┌──────┴───────┐
│ Audio Buffer    │              │  LLM Router  │
│ (pre+speech)    │              │  (AgentRouter│
└────────┬────────┘              └──────▲───────┘
         │ PCM 16kHz                    │ texto
         ▼                              │
┌─────────────────┐                     │
│ Faster-Whisper  │─────────────────────┘
│ (STT)           │
└─────────────────┘
```

### State Machine completa

```python
class CallState(Enum):
    LISTENING = "listening"
    SPEECH_DETECTED = "speech_detected"
    PROCESSING = "processing"
    SPEAKING = "speaking"
```

### Tareas concurrentes (asyncio)

```python
async def handle_call(ws):
    # Tres tareas corriendo en paralelo:
    receive_task = asyncio.create_task(receive_audio(ws))    # Lee WebSocket
    process_task = asyncio.create_task(process_speech())      # VAD + STT + LLM
    send_task = asyncio.create_task(send_audio(ws))          # Envía TTS chunks
    await asyncio.gather(receive_task, process_task, send_task)
```

---

## 10. Decisiones para Nuestra Implementación

| Decisión | Elección | Razón |
|----------|----------|-------|
| VAD | Silero (ONNX, ya en faster-whisper) | Preciso, ligero, soporta 8kHz |
| Conversión audio | audioop (in-memory) | Ya disponible en Python 3.12 |
| Buffering | Pre-buffer 300ms + flush en end-of-turn | Captura inicio de palabra |
| STT | Faster-Whisper batch | Más preciso que streaming para frases cortas |
| LLM para voz | Groq (futuro) o OpenRouter actual | Groq da ~300ms vs 3s |
| TTS | Edge-TTS → pydub → mulaw | Sin ffmpeg, todo en memoria |
| Barge-in | clear event + 150ms threshold | Simple y efectivo |
| Estado | State machine con 4 estados | Previene race conditions |

---

## Fuentes

- https://github.com/snakers4/silero-vad
- https://github.com/pipecat-ai/pipecat
- https://github.com/livekit/agents
- https://github.com/twilio-labs/call-gpt
- https://github.com/twilio/media-streams
- https://www.twilio.com/docs/voice/media-streams/websocket-messages
- https://docs.livekit.io/agents/build/turn-detection
- https://github.com/wiseman/py-webrtcvad

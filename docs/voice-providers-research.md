# Investigación: Proveedores de Voz — Fuentes, Cuentas y Configuración

## 1. STT (Speech-to-Text)

### 1.1 Faster-Whisper (Local, GPU) — RECOMENDADO

**Repo:** https://github.com/SYSTRAN/faster-whisper (11.6k stars)

**Instalación:**
```bash
uv add faster-whisper
```

**VRAM por modelo (INT8):**

| Modelo | VRAM | Calidad español |
|--------|------|-----------------|
| tiny | ~300 MB | Baja |
| base | ~400 MB | Aceptable |
| small | ~1.0 GB | Buena |
| medium | ~2.0 GB | Muy buena |
| large-v3 | ~3.0 GB | Excelente |
| distil-large-v3 | ~2.5 GB | Excelente (más rápido) |

**Config para nuestro proyecto:**
```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
segments, info = model.transcribe("audio.ogg", beam_size=5, language="es")
text = " ".join(s.text for s in segments)
```

**OGG/OPUS:** Soportado nativamente via PyAV (no necesita FFmpeg instalado).

**Cuenta necesaria:** Ninguna. Solo GPU con CUDA.

---

### 1.2 Groq Whisper API (Cloud Fallback)

**Docs:** https://console.groq.com/docs/speech-to-text
**Signup:** https://console.groq.com

**Free tier:**
- 20 requests/minuto
- 2,000 requests/día
- 28,800 segundos de audio/día (8 horas)
- Max file size: 25 MB

**Formatos soportados:** flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm

**Setup:**
1. Crear cuenta en https://console.groq.com (Google/GitHub/email)
2. Console > API Keys > Create API Key
3. `uv add groq`
4. Variable: `GROQ_API_KEY=gsk_...`

```python
from groq import Groq

client = Groq(api_key="gsk_...")
transcription = client.audio.transcriptions.create(
    file=("audio.ogg", audio_bytes),
    model="whisper-large-v3-turbo",
    language="es",
)
print(transcription.text)
```

**Costo:** $0.04/hora (turbo) o $0.111/hora (large-v3). Free tier suficiente para dev.

---

### 1.3 Deepgram (Alternativa cloud)

**Docs:** https://developers.deepgram.com/docs
**Signup:** https://console.deepgram.com/signup

**Free tier:** $200 de crédito sin expiración (~575 horas de audio a $0.0058/min)

**Setup:**
1. Crear cuenta (sin tarjeta)
2. Obtener API key
3. `uv add deepgram-sdk`
4. Variable: `DEEPGRAM_API_KEY=...`

**Español:** Soportado (es, es-419 para Latam). Nova-3 multilingual.

---

### 1.4 Google Cloud Speech-to-Text

**Docs:** https://cloud.google.com/speech-to-text/v2/docs
**Free tier:** 60 minutos/mes

**Setup:**
1. Crear proyecto GCP
2. Habilitar Speech-to-Text API
3. Crear service account + descargar JSON key
4. `uv add google-cloud-speech`
5. `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

**Español MX:** Soportado (es-MX). Modelos: chirp_3 (mejor), long, short.

---

### Resumen STT

| Provider | Costo | Latencia | Setup |
|----------|-------|----------|-------|
| Faster-Whisper | $0 (GPU local) | ~1.5s/10s audio | Solo CUDA |
| Groq | Free 8hrs/día | ~200ms | API key |
| Deepgram | $200 crédito gratis | Rápido | API key |
| Google | 60 min/mes gratis | Moderado | GCP project |

**Decisión:** Faster-Whisper local + Groq como fallback cloud.

---

## 2. TTS (Text-to-Speech)

### 2.1 Edge-TTS (Microsoft, gratis) — RECOMENDADO

**Repo:** https://github.com/rany2/edge-tts (11.6k stars, GPL-3.0)

**Instalación:**
```bash
uv add edge-tts
```

**Voces es-MX destacadas:**
- `es-MX-DaliaNeural` — Mujer, estándar (la más natural)
- `es-MX-JorgeNeural` — Hombre, estándar
- `es-MX-Ximena:DragonHDLatestNeural` — Mujer, Neural HD (mejor calidad)
- `es-MX-Tristan:DragonHDLatestNeural` — Hombre, Neural HD
- 29 voces mexicanas en total (más multilingual y MAI con emociones)

**Cuenta necesaria:** Ninguna. No requiere API key.

**Código:**
```python
import edge_tts

communicate = edge_tts.Communicate(text, "es-MX-DaliaNeural")
await communicate.save("output.mp3")
```

**Riesgos para producción:**
- Es uso no oficial del endpoint de Microsoft Edge
- Sin SLA — Microsoft puede bloquear sin aviso
- Licencia GPL-3.0 (contagiosa)
- Para alto volumen considerar Azure Cognitive Services ($16/1M chars)

**Latencia:** ~500-800ms para frases cortas. Soporta streaming.

---

### 2.2 Piper TTS (Local, open source)

**Repo:** https://github.com/OHF-Voice/piper1-gpl (fork activo, 4.9k stars)
**Original (archivado):** https://github.com/rhasspy/piper

**Instalación:** `pip install piper-tts`

**Voces es-MX:** Disponibles en https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_MX

**Rendimiento:** Más rápido que real-time en CPU. No necesita GPU.

**Calidad vs Edge-TTS:** Notablemente inferior. Suena más robótico. Útil como fallback offline.

**Cuenta necesaria:** Ninguna.

---

### Resumen TTS

| Provider | Costo | Calidad | Custom voice | Latencia |
|----------|-------|---------|--------------|----------|
| Edge-TTS | $0 | 9/10 | No | ~600ms |
| Piper | $0 | 6/10 | No | ~50ms |
| XTTS v2 | $0 (GPU) | 7/10 | Sí (cloning) | ~200ms |
| Edge + RVC | $0 (GPU) | 8/10 | Sí (hybrid) | ~700ms |

**Decisión:** Edge-TTS para Sprint 2. Si necesitamos voz custom → XTTS v2 o RVC.

---

## 3. Clonación de Voz Open Source

### 3.1 Coqui XTTS v2 — MEJOR OPCIÓN PERMISIVA

**Repo:** https://github.com/coqui-ai/TTS (45.8k stars, MPL-2.0)
**Estado:** Coqui cerró en 2024, pero el repo sigue activo con comunidad manteniendo.

**Capacidades:**
- Clonación con solo **3 segundos** de audio (6-10s recomendado)
- 16 idiomas incluyendo español
- Streaming con <200ms latencia
- Cross-language cloning (clonar voz de un idioma, generar en otro)

**VRAM:** ~4-6 GB para inferencia. En CPU funciona pero lento (5-10x real-time).

**Instalación:**
```bash
pip install TTS
```

**Código:**
```python
from TTS.api import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts.tts_to_file(
    text="Hola, en qué puedo ayudarle?",
    file_path="output.wav",
    speaker_wav=["referencia_voz.wav"],  # 6-10s de la voz a clonar
    language="es"
)
```

**Licencia:** MPL-2.0 (permisiva, uso comercial OK)

**Calidad español:** 7/10 — tiende a acento neutro/castellano. Fine-tuning con datos MX mejora.

---

### 3.2 OpenVoice V2

**Repo:** https://github.com/myshell-ai/OpenVoice (37k stars, MIT)

**Cómo funciona (2 etapas):**
1. MeloTTS genera el habla en el idioma target
2. Tone Color Converter aplica el timbre de la voz de referencia

NO es clonación completa — solo clona timbre, no estilo/cadencia.

**VRAM:** ~4 GB
**Español:** Soportado nativamente en V2
**Audio mínimo:** 5-10 segundos referencia

**Instalación:**
```bash
git clone https://github.com/myshell-ai/OpenVoice.git
cd OpenVoice && pip install -e .
pip install git+https://github.com/myshell-ai/MeloTTS.git
```

**Licencia:** MIT (totalmente permisiva)

**Calidad:** 6/10 — inferior a XTTS para clonación fiel.

---

### 3.3 RVC (Voice Conversion)

**Repo:** https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI (36.7k stars, MIT)

**Cómo funciona:** NO genera voz desde texto. Convierte una voz existente a otra.
Pipeline: `TTS cualquiera → RVC → Audio con voz clonada`

**Entrenamiento:** 10 minutos mínimo (30-60 min recomendado) de audio limpio.
**Inferencia real-time:** Sí — 170ms latencia (90ms con ASIO).

**Uso para nosotros:**
```
Texto → Edge-TTS (calidad alta) → RVC (convierte a voz del negocio) → Audio final
```

**Licencia:** MIT

---

### 3.4 Fish Speech

**Repo:** https://github.com/fishaudio/fish-speech (31.4k stars)

**Capacidades:** TTS + clonación con 10-30s de audio. 4B parámetros. Español Tier 1.
**Latencia:** ~100ms TTFA en H200.
**VRAM:** 8-16 GB (modelo grande).
**Licencia:** FISH AUDIO RESEARCH LICENSE — **restricciones comerciales**. No apto para producción sin verificar.

---

### 3.5 GPT-SoVITS

**Repo:** https://github.com/RVC-Boss/GPT-SoVITS (60.1k stars, MIT)

**Capacidades:** Clonación con 5 segundos. Inferencia rapidísima (RTF 0.028 en RTX 4060Ti).
**Problema:** **NO soporta español.** Solo chino, japonés, inglés, coreano, cantonés.

---

### Comparativa clonación

| Tool | Audio mínimo | Calidad | VRAM | Español | Licencia |
|------|-------------|---------|------|---------|----------|
| XTTS v2 | 3-10s | 7/10 | 4-6 GB | Sí | MPL-2.0 |
| OpenVoice | 5-10s | 6/10 | 4 GB | Sí | MIT |
| RVC | 10-60 min train | 8/10 | 4 GB | Sí* | MIT |
| Fish Speech | 10-30s | 8/10 | 8-16 GB | Sí | Restrictiva |
| GPT-SoVITS | 5s | 9/10 | 4 GB | **No** | MIT |

*RVC no genera voz, solo convierte. Necesita TTS upstream.

**¿Es production-ready?** Sí, con XTTS v2 o RVC+Edge-TTS. La calidad es ~70-80% de ElevenLabs pero gratis y self-hosted.

---

## 4. Barge-in Detection — Por qué es difícil

### El problema central: Echo Cancellation

Cuando el bot habla, su audio sale por el speaker del usuario y se captura por el micrófono. El sistema necesita distinguir:
- **Echo:** el audio del bot rebotando → ignorar
- **Voz del usuario hablando encima** → interrumpir

Esto requiere Acoustic Echo Cancellation (AEC) — un problema de DSP que los ingenieros de telecoms llevan décadas refinando.

### Componentes técnicos necesarios

1. **AEC (Acoustic Echo Cancellation):** Resta la señal del bot del audio capturado
2. **Double-talk detection:** Detectar que hay 2 personas hablando a la vez
3. **VAD durante playback:** Detectar voz del usuario MIENTRAS el bot suena
4. **Buffer management:** Detener playback inmediatamente al detectar interrupción
5. **Latencia <150ms** para que se sienta natural

### La buena noticia: en telefonía NO necesitas AEC

En Twilio/Vonage/WhatsApp Calling, el audio inbound y outbound son streams separados a nivel de red. El inbound que recibes ya NO tiene echo del bot — la red telefónica hace echo cancellation.

Tu implementación se simplifica a:
```
Audio inbound (limpio) → Silero VAD → ¿Detectó voz >150ms?
    Sí → Cancelar TTS en curso + flush buffer outbound
    No → Seguir reproduciendo
```

### Cómo lo resuelven las plataformas

| Plataforma | Barge-in | Cómo |
|-----------|----------|------|
| Twilio Media Streams | Sí | `clear` event para flush buffer + VAD en inbound |
| LiveKit Agents SDK | Sí (built-in) | WebRTC AEC del cliente + agent framework |
| Vonage WebSockets | Sí | Stream bidireccional, `clear` para interrumpir |
| Daily.co / Pipecat | Sí (built-in) | Framework con turn-taking automático |

### WhatsApp Calling API

**Estado actual:** WhatsApp Cloud API **NO tiene API de llamadas en tiempo real** pública para bots. Las llamadas son P2P con E2E encryption. Meta no expone un media stream.

Esto significa: **barge-in no aplica a WhatsApp hoy.** Los voice notes son async (graban → envían → procesan).

### Si añadimos canal de voz en el futuro

**Opción 1 — Usar plataforma (RECOMENDADO):**
- LiveKit Agents SDK o Pipecat (Daily.co) — barge-in gratis
- Twilio Media Streams — barge-in con `clear` + VAD manual

**Opción 2 — Implementar desde cero:**
- Silero VAD en inbound stream
- Threshold: 150-200ms de voz detectada antes de interrumpir
- Al detectar: cancelar TTS, flush buffer, transcribir lo acumulado
- Complejidad: ~2-3 semanas para un dev experimentado

**Opción 3 — NO implementar (MVP):**
- Half-duplex: bot habla → espera → usuario habla → espera
- Funciona para la mayoría de casos de atención al cliente
- Se siente menos natural pero es robusto

### Librerías Python relevantes

| Librería | Propósito | Estado |
|----------|-----------|--------|
| `silero-vad` | VAD (detección de voz) | Activo, MIT |
| `webrtcvad` | VAD legacy | Sin mantenimiento (2017) |
| `speexdsp` | Echo cancellation | Sin mantenimiento (2018) |
| `pipecat` | Framework voz completo | Activo (Daily.co) |
| `livekit-agents` | Framework voz completo | Activo (LiveKit) |

### Conclusión barge-in

**No es un problema para Sprint 1-2** (WhatsApp audio messages son async).
Para Sprint 3 (si añadimos llamadas vía Twilio/LiveKit), el barge-in viene resuelto por la plataforma. Solo necesitas Silero VAD + lógica de flush.

**NO intentes implementar AEC propio** — es meses de trabajo DSP. Usa una plataforma que lo resuelva.

---

## 5. Cuentas y Configuración Necesarias

### Para Sprint 1 (audio → texto)

| Qué | Dónde | Costo |
|-----|-------|-------|
| CUDA toolkit | Ya instalado (RTX 5060) | $0 |
| Faster-Whisper model | Se descarga automáticamente de HuggingFace | $0 |
| Groq API key (fallback) | https://console.groq.com | $0 |

### Para Sprint 2 (texto → audio)

| Qué | Dónde | Costo |
|-----|-------|-------|
| Edge-TTS | Sin cuenta necesaria | $0 |
| (Opcional) Azure Speech | https://portal.azure.com | $16/1M chars |

### Para Sprint 3 (llamadas real-time)

| Qué | Dónde | Costo |
|-----|-------|-------|
| LiveKit Cloud | https://cloud.livekit.io | Free tier generoso |
| O Twilio | https://www.twilio.com/voice | ~$0.013/min |
| Silero VAD | `pip install silero-vad` | $0 |

### Para voz custom (opcional)

| Qué | Necesitas | Costo |
|-----|-----------|-------|
| XTTS v2 | 6-10s de audio de la voz target + GPU 4-6GB | $0 |
| RVC | 10-60 min de audio + entrenamiento (~1-2hrs GPU) | $0 |

---

## 6. Decisiones Finales Actualizadas

| Componente | Elegido | Razón |
|-----------|---------|-------|
| STT principal | Faster-Whisper large-v3 INT8 | Gratis, excelente español, local |
| STT fallback | Groq Whisper API | Mismo modelo, 8hrs/día gratis |
| TTS principal | Edge-TTS (es-MX-DaliaNeural) | Gratis, calidad neural, async nativo |
| TTS fallback | Piper TTS | Offline, CPU-only |
| Clonación (futuro) | XTTS v2 o Edge+RVC | MPL-2.0/MIT, 3-10s de audio |
| Llamadas (futuro) | LiveKit o Twilio | Barge-in resuelto por plataforma |
| VAD | Silero VAD | 5MB, MIT, production-ready |

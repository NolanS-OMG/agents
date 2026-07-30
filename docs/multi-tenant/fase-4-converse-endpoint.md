# Fase 4: Endpoint `/api/v1/converse`

## Objetivo

Un endpoint universal que acepta texto o audio, responde texto o audio, mantiene historial por `conversant_id`, y funciona con los proveedores cloud elegidos.

---

## 4.1 Request/Response Models

**Archivo nuevo:** `src/app/models/converse.py`

### Request (JSON — texto)
```python
class ConverseRequest(BaseModel):
    conversant_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4096)
    response_format: Literal["text", "audio", "both"] = "text"
    estilo: str = "chat"
```

### Request (Multipart — audio)
Multipart form con:
- `conversant_id`: string
- `audio`: UploadFile (ogg, mp3, wav, m4a)
- `response_format`: "text" | "audio" | "both"
- `estilo`: "chat" | "voz"

### Response
```python
class ConverseResponse(BaseModel):
    conversant_id: str
    conversation_id: str
    response: str
    audio_url: str | None = None
    input_type: str  # "text" o "audio"
    transcription: str | None = None
    tool_used: str | None = None
    usage: dict  # tokens_in, tokens_out, latency_ms, cost_usd
```

---

## 4.2 Proveedores Cloud

### STT: Groq Whisper Turbo

**Archivo nuevo:** `src/app/services/stt/groq_whisper.py`

```python
class GroqWhisperSTT:
    async def transcribe(self, audio_bytes: bytes, language: str = "es") -> str:
        # POST https://api.groq.com/openai/v1/audio/transcriptions
        # model: "whisper-large-v3-turbo"
        # file: audio_bytes
        # language: "es"
```

### TTS: Edge-TTS (ya existe)

Reusar `src/app/services/synthesizer.py` — ya funciona.

### LLM: OpenRouter (ya existe)

Reusar `src/app/services/llm/openai_compatible.py` — ya funciona. Solo parametrizar el API key por tenant.

---

## 4.3 Flujo del Endpoint

```python
@router.post("/converse")
async def converse(
    tenant: TenantContext,
    request: ConverseRequest | None = None,  # JSON
    audio: UploadFile | None = None,          # Multipart
    conversant_id: str = Form(None),
    response_format: str = Form("text"),
):
    # 1. Determinar input type (text o audio)
    # 2. Si audio → STT (Groq) → texto
    # 3. Cargar/crear conversation por (tenant_id, conversant_id)
    # 4. Cargar history del conversation
    # 5. Construir AgentRouter con TenantConfig
    # 6. agent.run(text, history)
    # 7. Si response_format incluye audio → TTS → guardar archivo → URL firmada
    # 8. Guardar message en DB
    # 9. Log event (para billing)
    # 10. Retornar ConverseResponse
```

---

## 4.4 Conversations en DB

- Crear conversation si no existe para (tenant_id, conversant_id)
- ID generado: `conv_{uuid_short}`
- History: cargar últimos N messages de DB (no Redis)
- Redis sigue para rate limit y cache de TenantConfig, pero history va a PostgreSQL

---

## 4.5 Audio File Serving

**Archivo nuevo:** `src/app/api/routes/audio.py`

```
GET /api/v1/audio/{file_id}?token={hmac}&expires={timestamp}
```

- Archivos en `data/audio/{tenant_id}/{uuid}.mp3`
- Token = HMAC-SHA256(file_id + expires, secret)
- Si token inválido o expirado → 403
- Cleanup: borrar archivos >24h (cron o background task)

---

## 4.6 Tests

- Texto → texto (sin audio)
- Audio → texto (multipart upload)
- Texto → audio (verifica audio_url en response)
- Audio → audio (pipeline completo)
- Conversant_id mantiene historial entre requests
- API key de otro tenant no ve conversaciones ajenas
- Audio format inválido → 400
- Rate limit per-conversant funciona

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `src/app/models/converse.py` | **NUEVO** |
| `src/app/api/routes/converse.py` | **NUEVO** |
| `src/app/api/routes/audio.py` | **NUEVO** |
| `src/app/services/stt/groq_whisper.py` | **NUEVO** |
| `src/app/services/llm/provider_factory.py` | Modificar (per-tenant key) |
| `src/app/main.py` | Registrar routes |
| `tests/test_converse.py` | **NUEVO** |

# Plan: API Multi-Tenant para Agente de Voz

## Qué tenemos hoy (single-tenant)

- 1 tenant (santa_lena) hardcodeado en `.env`
- WhatsApp credentials globales
- Twilio credentials globales
- SQLite para analytics
- Redis sessions con key = phone number
- Endpoint `/api/v1/chat` básico

## Qué necesitamos (multi-tenant MVP, 5-10 clientes)

---

## 1. Endpoint Unificado `/api/v1/converse`

Un solo endpoint que maneja los 4 modos:

```
POST /api/v1/converse
Headers: X-API-Key: sk_santa_lena_xxxxx
Content-Type: application/json | multipart/form-data
```

### Request (texto)
```json
{
  "conversant_id": "cliente_123",
  "message": "Quiero una hamburguesa",
  "response_format": "text"  // o "audio" o "both"
}
```

### Request (audio) — multipart/form-data
```
conversant_id: "cliente_123"
audio: <file.ogg>
response_format: "audio"
```

### Response
```json
{
  "conversant_id": "cliente_123",
  "conversation_id": "conv_abc123",
  "response": "Claro, tenemos 3 opciones...",
  "audio_url": "/api/v1/audio/resp_xyz.mp3",  // si pidió audio
  "input_type": "audio",
  "transcription": "Quiero una hamburguesa",  // si input fue audio
  "tool_used": null,
  "usage": {"tokens_in": 234, "tokens_out": 89}
}
```

### Modos

| Input | response_format | Resultado |
|-------|----------------|-----------|
| text | text | texto → LLM → texto |
| text | audio | texto → LLM → TTS → audio URL |
| audio file | text | STT → LLM → texto |
| audio file | audio | STT → LLM → TTS → audio URL |

---

## 2. Modelo de Datos

### Tabla: tenants
```sql
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,           -- "santa_lena"
    name TEXT NOT NULL,            -- "Santa Leña Restaurante"
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    config JSONB                   -- settings overrides (LLM model, voice, etc.)
);
```

### Tabla: api_keys
```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT REFERENCES tenants(id),
    key_hash TEXT NOT NULL,        -- SHA-256 del key
    key_prefix TEXT NOT NULL,      -- "sk_santa_" (para identificar sin exponer)
    scopes TEXT[] DEFAULT '{converse,conversations}',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    last_used_at TIMESTAMP
);
```

### Tabla: tenant_credentials
```sql
CREATE TABLE tenant_credentials (
    tenant_id TEXT PRIMARY KEY REFERENCES tenants(id),
    whatsapp_access_token_enc TEXT,    -- Fernet encrypted
    whatsapp_phone_number_id TEXT,
    whatsapp_verify_token TEXT,
    twilio_account_sid TEXT,
    twilio_auth_token_enc TEXT,        -- Fernet encrypted
    twilio_phone_number TEXT,
    llm_api_key_enc TEXT,             -- Fernet encrypted (override global)
    llm_model TEXT,                    -- override per tenant
    tts_voice TEXT DEFAULT 'es-MX-DaliaNeural'
);
```

### Tabla: conversations
```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,               -- "conv_abc123"
    tenant_id TEXT REFERENCES tenants(id),
    conversant_id TEXT NOT NULL,        -- quien habla con el AI
    channel TEXT DEFAULT 'api',         -- api, whatsapp, voice_call
    started_at TIMESTAMP,
    last_message_at TIMESTAMP,
    total_turns INTEGER DEFAULT 0,
    metadata JSONB                     -- flexible per-tenant data
);
CREATE INDEX idx_conv_tenant_conversant ON conversations(tenant_id, conversant_id);
```

### Tabla: messages
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    tenant_id TEXT NOT NULL,
    role TEXT NOT NULL,                 -- user, assistant, tool
    content TEXT,
    input_type TEXT DEFAULT 'text',     -- text, audio
    audio_duration_ms INTEGER,
    transcription_ms INTEGER,
    tts_ms INTEGER,
    tokens_in INTEGER,
    tokens_out INTEGER,
    response_latency_ms INTEGER,
    model_used TEXT,
    tool_used TEXT,
    cost_usd REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Tabla: usage_daily
```sql
CREATE TABLE usage_daily (
    tenant_id TEXT,
    date DATE,
    total_requests INTEGER DEFAULT 0,
    text_requests INTEGER DEFAULT 0,
    audio_requests INTEGER DEFAULT 0,
    voice_call_minutes REAL DEFAULT 0,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    PRIMARY KEY (tenant_id, date)
);
```

---

## 3. Autenticación y Seguridad

### Flujo de auth
```
Request → Extract X-API-Key header
       → SHA-256 hash
       → Lookup en api_keys table (by hash + active)
       → Load tenant_id → TenantContext
       → Inject en request.state
```

### API Key format
```
sk_{tenant_prefix}_{random_32_chars}
Ejemplo: sk_santa_a8f2c9d1e4b7...
```

### Credential encryption
- Fernet symmetric encryption (de `cryptography` package)
- Master key en env var `CREDENTIAL_ENCRYPTION_KEY`
- Tokens de WhatsApp/Twilio/LLM encriptados at rest

### Rate limiting per tenant
- Default: 100 req/min por tenant, 20 req/min por conversant
- Configurable por tenant en `tenants.config` JSONB
- Keys en Redis: `ratelimit:{tenant_id}:{conversant_id}`

---

## 4. Webhooks Multi-Tenant

### WhatsApp
```
POST /webhook/whatsapp/{tenant_id}
```
Cada tenant configura SU webhook URL en Meta apuntando a su path específico.
El handler carga las credentials del tenant desde DB.

### Twilio Voice
```
POST /incoming-call/{tenant_id}
WS   /ws/media-stream/{tenant_id}
```
Cada número de Twilio apunta a la URL con su tenant_id.

---

## 5. Lo que Te Falta para MVP

### Crítico (sin esto no es multi-tenant)

| # | Qué | Por qué |
|---|-----|---------|
| 1 | PostgreSQL | SQLite no soporta escrituras concurrentes de múltiples tenants |
| 2 | API Keys + auth middleware | Sin esto cualquiera puede usar el servicio |
| 3 | Tabla de credentials encriptadas | No puedes tener tokens de 10 clientes en un .env |
| 4 | Endpoint `/api/v1/converse` | El punto de integración universal |
| 5 | `conversant_id` en todo el flujo | Desacoplar de "phone number = identity" |
| 6 | Tenant resolution en webhooks | Cada cliente su propio webhook path |

### Importante (antes del 2do cliente)

| # | Qué | Por qué |
|---|-----|---------|
| 7 | Script de onboarding | Crear tenant + API key + seed config |
| 8 | Usage tracking diario | Saber cuánto consume cada cliente |
| 9 | Semáforo de GPU para Whisper | 2+ transcripciones simultáneas = OOM |
| 10 | Conversation history API | Clientes quieren ver sus conversaciones |
| 11 | Audio file serving | URLs firmadas para respuestas de audio |
| 12 | Per-tenant rate limiting | Un cliente no puede tumbar a los demás |

### Nice-to-have (producción polish)

| # | Qué | Por qué |
|---|-----|---------|
| 13 | WebSocket para streaming | Respuestas en real-time para web clients |
| 14 | Dashboard admin por tenant | Ver uso, rotar keys, editar prompts |
| 15 | S3 para audio | Local filesystem no escala |
| 16 | OpenAPI docs auto-generadas | Para que clientes integren fácil |
| 17 | Webhook signature validation | Seguridad de Meta/Twilio callbacks |

---

## 6. Decisiones Arquitectónicas

| Decisión | Razón |
|----------|-------|
| PostgreSQL (no MySQL) | JSONB nativo, asyncpg rápido, arrays para scopes |
| Fernet encryption (no KMS) | Zero deps externas para MVP. Migrar a AWS KMS después |
| Whisper compartido con semáforo | Cargar 1 modelo por tenant = imposible (3GB VRAM cada uno) |
| Row-level isolation (no schema-per-tenant) | 5-10 tenants no justifica la complejidad |
| Content en archivos Markdown (no DB) | El menú/prompts son versionados en git, no cambian en runtime |
| Signed URLs para audio (no base64 inline) | Base64 infla respuestas 33%, URLs permiten caching |
| Un endpoint unificado `/converse` | Un solo punto de integración, modo se elige con parámetros |

---

## 7. Secuencia de Implementación

### Fase 1: Data Layer (2-3 días)
- Agregar asyncpg + SQLAlchemy async + Alembic
- Modelos ORM (tenants, api_keys, conversations, messages, usage_daily)
- Credential vault service (encrypt/decrypt Fernet)
- PostgreSQL en docker-compose
- Migración inicial

### Fase 2: Auth + Tenant Resolution (1-2 días)
- Auth middleware (X-API-Key → tenant)
- Dependency `get_current_tenant() -> TenantContext`
- Rate limit per-tenant en Redis
- Tests de auth

### Fase 3: Endpoint Converse (2-3 días)
- Request/response models Pydantic
- Ruta `/api/v1/converse` con los 4 modos
- Audio upload (multipart) + audio serving (signed URLs)
- Conversant_id en sessions + history

### Fase 4: Webhooks Multi-Tenant (1 día)
- Parametrizar rutas: `/webhook/whatsapp/{tenant_id}`
- Cargar credentials de DB en vez de env
- Voice routes parametrizadas

### Fase 5: Onboarding + Management (1 día)
- Script CLI: `python scripts/onboard_tenant.py`
- Migrar santa_lena a la DB
- Endpoint de usage

**Total estimado: 7-10 días de trabajo**

---

## 8. Ejemplo de Integración para un Cliente

```python
import httpx

client = httpx.Client(
    base_url="https://api.tuagente.com",
    headers={"X-API-Key": "sk_santa_a8f2c9d1e4b7..."}
)

# Texto a texto
resp = client.post("/api/v1/converse", json={
    "conversant_id": "mesa_5",
    "message": "Quiero dos hamburguesas clásicas para llevar",
})
print(resp.json()["response"])

# Audio a texto
with open("pedido.ogg", "rb") as f:
    resp = client.post("/api/v1/converse", files={"audio": f}, data={
        "conversant_id": "llamada_123",
        "response_format": "audio",
    })
print(resp.json()["audio_url"])
```

---

## 9. Infraestructura Mínima para Producción

```
┌─────────────────────────────────────────┐
│          Load Balancer (Caddy)           │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│        FastAPI App (uvicorn x2)          │
│  - Auth middleware                       │
│  - Converse endpoint                     │
│  - Webhooks per-tenant                   │
│  - Voice WebSocket                       │
└──┬──────────┬───────────────┬───────────┘
   │          │               │
   ▼          ▼               ▼
┌──────┐  ┌───────┐  ┌──────────────┐
│Redis │  │Postgres│  │ GPU (Whisper)│
│(sessions│ │(data) │  │ + Edge-TTS   │
│ cache)│  │       │  │              │
└──────┘  └───────┘  └──────────────┘
```

Para 5-10 tenants, un solo servidor con 8GB VRAM + 16GB RAM + 4 cores es suficiente.

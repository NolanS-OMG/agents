# Plan Completo: API Multi-Tenant para Agente de Voz

## Visión

Transformar el agente single-tenant actual en una API multi-tenant donde cada restaurante (u otro negocio) tiene su propia configuración, credenciales, base de conocimiento, y métricas — todo servido desde un solo deployment.

---

## Arquitectura Objetivo

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                  │
│  X-API-Key → Tenant Resolution → Rate Limit → Route     │
└──────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
  /api/v1/     /webhook/   /incoming-  /api/v1/
  converse     whatsapp/   call/       knowledge
               {tenant}    {tenant}
       │          │          │          │
       └──────────┴──────────┴──────────┘
                       │
              ┌────────▼────────┐
              │  Tenant Context │
              │  (config, docs, │
              │   credentials)  │
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
  ┌─────────┐    ┌──────────┐    ┌──────────┐
  │PostgreSQL│    │  Redis   │    │ Providers│
  │(tenants, │    │(sessions,│    │(Groq STT,│
  │ docs,    │    │ cache,   │    │ OpenRouter│
  │ metrics) │    │ ratelimit│    │ Edge-TTS) │
  └─────────┘    └──────────┘    └──────────┘
```

---

## Componentes del Sistema

### 1. Data Layer (PostgreSQL + Tortoise ORM)

**Tablas:**
- `tenants` — registro principal de cada cliente
- `api_keys` — autenticación, múltiples keys por tenant
- `tenant_credentials` — tokens encriptados (WhatsApp, Twilio, LLM)
- `knowledge_documents` — base de conocimiento OKF (menú, acciones, negocio)
- `tenant_prompts` — estilos de comunicación por canal
- `conversations` — historial de conversaciones
- `messages` — cada mensaje individual con métricas
- `events` — cada operación billable (LLM call, STT, TTS)
- `usage_daily` — agregados diarios por tenant

**Migraciones:** Tortoise ORM built-in (auto-detect changes).

**Docker:** PostgreSQL 16 Alpine en docker-compose para desarrollo.

### 2. Auth & Tenant Resolution

**Flujo:**
```
Request → X-API-Key header → SHA-256 hash → DB lookup → TenantContext
```

**Para webhooks (sin API key):**
```
/webhook/whatsapp/{tenant_id} → DB lookup por tenant_id → Verificar credentials
```

**Rate limiting:**
- Per-tenant: 100 req/min (configurable)
- Per-conversant: 20 req/min
- Redis sorted sets (ya implementado, solo namespace por tenant)

### 3. Endpoint Unificado `/api/v1/converse`

| Input | response_format | Pipeline |
|-------|----------------|----------|
| text | text | LLM → texto |
| text | audio | LLM → TTS → audio URL |
| audio (multipart) | text | STT → LLM → texto |
| audio (multipart) | audio | STT → LLM → TTS → audio URL |

### 4. Knowledge Base (OKF → PostgreSQL)

- Documentos Markdown almacenados en `knowledge_documents`
- Campos de acciones como arrays nativos (no parsing de tablas)
- Prompts/estilos en tabla separada `tenant_prompts`
- Cache en Redis (TTL 5 min, invalidar en write)
- **Fallback:** si no hay prompt custom, usar el BASE_SYSTEM_PROMPT actual

### 5. Webhooks Multi-Tenant

- `/webhook/whatsapp/{tenant_id}` — cada tenant configura su webhook en Meta
- `/incoming-call/{tenant_id}` — cada número Twilio apunta a su path
- `/ws/media-stream/{tenant_id}` — WebSocket para llamadas por tenant
- Credentials cargadas de DB (encriptadas con Fernet)

### 6. Proveedores Cloud (sin GPU local)

| Servicio | Provider | Costo |
|----------|----------|-------|
| STT | Groq Whisper Turbo | $0.04/hora |
| TTS | Edge-TTS (MVP) → AWS Polly (prod) | $0 → $3/mes |
| LLM | OpenRouter (0% markup <$25K/mes) | ~$5-15/mes |

### 7. Métricas y Usage Tracking

**Per-request:** tabla `events` con tenant_id, tipo, provider, latencia, costo
**Per-conversation:** resolución, duración, turnos, costo total
**Diario:** agregados en `usage_daily` para billing
**Alertas:** latencia >3s, error rate >2%, resolution <80%

### 8. Credential Encryption

- Fernet (symmetric) con master key en env var
- Encriptar: WhatsApp tokens, Twilio auth, LLM API keys por tenant
- `CREDENTIAL_ENCRYPTION_KEY` en .env (generado una vez)

### 9. Audio File Serving

- TTS genera MP3 → guardado en `data/audio/{tenant_id}/{uuid}.mp3`
- Response incluye `audio_url: /api/v1/audio/{id}?token=xxx&expires=xxx`
- Token firmado (HMAC) con expiración de 1 hora
- Cleanup job para archivos >24h

### 10. Script de Creación de Tenant

```bash
uv run python scripts/create_tenant.py \
  --id nueva_pizzeria \
  --name "Nueva Pizzería" \
  --whatsapp-token "EAABx..." \
  --twilio-sid "AC..."
# Output: API Key generada: sk_nueva_pi_a8f2c9d1...
```

---

## Decisiones Técnicas

| Decisión | Elección | Alternativa si falla |
|----------|----------|---------------------|
| ORM | Tortoise ORM | Piccolo ORM (v1.x estable) |
| DB | PostgreSQL 16 | — |
| Auth | API key + SHA-256 | JWT si necesitamos scopes |
| Encryption | Fernet | AWS KMS |
| Cache | Redis (TTL 5min) | — |
| Audio storage | Local filesystem | S3 |
| Migrations | Tortoise built-in | Alembic |
| STT provider | Groq | Deepgram |
| Prompts fallback | BASE_SYSTEM_PROMPT hardcoded | — |

---

## Lo que NO cambia

- El `AgentRouter` sigue igual (recibe tools + prompt + history)
- Las 3 tools mantienen la misma interfaz (`BaseTool.execute()`)
- El formato del contenido sigue siendo Markdown
- Redis para sessions/cache/ratelimit
- El LLM provider service (factory pattern)
- Los scripts CLI existentes (stats, transcribe, synthesize)

---

## Estimación de Tiempo

| Fase | Días | Entregable |
|------|------|-----------|
| 1. PostgreSQL + ORM + Docker | 2-3 | DB corriendo, modelos definidos, migraciones |
| 2. Auth + Tenant Resolution | 1-2 | API keys, middleware, TenantContext |
| 3. Knowledge Base en DB | 2 | CRUD docs, migración OKF, cache |
| 4. Endpoint /converse | 2-3 | Los 4 modos funcionando |
| 5. Webhooks multi-tenant | 1-2 | WhatsApp + Twilio parametrizados |
| 6. Métricas + Events | 1-2 | Tracking por request, usage_daily |
| 7. Audio serving + scripts | 1 | URLs firmadas, create_tenant.py |
| **Total** | **10-15 días** | MVP multi-tenant funcional |

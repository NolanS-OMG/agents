# Architecture

## System Overview

```
                         ┌─────────────────────────────────────────────────┐
                         │                  Clients                         │
                         │  WhatsApp (Meta)  │  Phone (Twilio)  │  API     │
                         └────────┬──────────┴────────┬─────────┴────┬─────┘
                                  │                   │              │
                         ┌────────▼──────────┐  ┌─────▼─────┐  ┌────▼────┐
                         │ POST /webhook/     │  │ WebSocket │  │ POST    │
                         │ whatsapp/{tenant}  │  │ /ws/media │  │/converse│
                         └────────┬──────────┘  └─────┬─────┘  └────┬────┘
                                  │                   │              │
                    ┌─────────────▼───────────────────▼──────────────▼──────┐
                    │                    Middleware                          │
                    │  CorrelationID → Auth (API Key → Tenant) → Rate Limit │
                    └─────────────────────────┬────────────────────────────┘
                                              │
                    ┌─────────────────────────▼────────────────────────────┐
                    │               Message Processor Service               │
                    │  1. Transcribe audio (if needed)                      │
                    │  2. Load tenant config (DB → cache → filesystem)      │
                    │  3. Build tools for tenant                            │
                    │  4. Run AgentRouter                                   │
                    │  5. Save session history                              │
                    │  6. Send reply via channel adapter                    │
                    └─────────────────────────┬────────────────────────────┘
                                              │
                    ┌─────────────────────────▼────────────────────────────┐
                    │                   AgentRouter                         │
                    │  System prompt + tenant context + user message        │
                    │  Loop (max 5 iterations):                             │
                    │    LLM.complete() → tool_call? → execute → inject     │
                    │  Until: text response or max iterations               │
                    └──────┬──────────────┬──────────────┬─────────────────┘
                           │              │              │
                    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────────────┐
                    │ ejecutar_   │ │ consultar_ │ │ buscar_base_     │
                    │ accion      │ │ info_      │ │ conocimiento_    │
                    │             │ │ negocio    │ │ extensa          │
                    └─────────────┘ └────────────┘ └──────────────────┘
```

## Request Lifecycle

### 1. Channel Ingress

Each channel has its own entry point:

- **WhatsApp**: `POST /webhook/whatsapp/{tenant_id}` — Meta sends webhook payloads. The handler returns `200 OK` immediately and processes in background via `_bg()` pattern (task retained in module-level set to prevent GC).
- **Voice**: `POST /incoming-call/{tenant_id}` returns TwiML connecting to `WS /ws/media-stream/{tenant_id}`. Audio streams as mulaw 8kHz chunks over WebSocket.
- **API**: `POST /api/v1/converse` — synchronous multipart form accepting text or audio file. Returns when processing completes.

### 2. Tenant Resolution

Two paths depending on channel:

- **API/Converse**: `AuthMiddleware` extracts `X-API-Key` header → SHA-256 hash → DB lookup in `api_keys` table → resolves `tenant_id` into `request.state`.
- **Webhooks**: Tenant ID comes from the URL path (`/{tenant_id}`). Credentials loaded from `TenantCredentials` table, decrypted via Fernet vault.

### 3. Message Processing

The `message_processor.py` service provides two reusable functions:

```
transcribe_audio(incoming, adapter, voice_pipeline)
    → Downloads media via channel adapter
    → Runs Whisper STT in a thread (asyncio.to_thread)
    → Returns transcribed text or None (with error reply sent)

process_and_reply(tenant_id, incoming, adapter, http_client, redis, user_text)
    → Loads tenant config (with Redis cache, 300s TTL)
    → Builds tool set for tenant
    → Gets session history from Redis
    → Runs AgentRouter
    → Saves updated history (with compression if > threshold)
    → Sends reply via adapter
    → Returns AgentResult
```

### 4. AgentRouter — The Core Loop

```python
for _ in range(MAX_TOOL_ITERATIONS):  # max 5
    response = await llm.complete(messages, tools)
    
    if no tool_calls:
        return text response
    
    tool_result = await execute_tool(name, args)
    
    if tool == "transferir_a_humano":
        return immediately with needs_human=True
    
    if tool_result is ToolError:
        inject system message: "ask user for {campos_faltantes}"
    
    append tool result to messages, continue loop
```

The system prompt includes:
1. Base instructions (response rules, available tools)
2. Tenant business context (from `TenantConfig.get_prompt(estilo)`)
3. Sender ID (so `ejecutar_accion` doesn't need to ask for phone)

### 5. Session Management

Redis-backed with two keys per session:

- `session:{tenant_id}:{conversant_id}:history` — recent messages (JSON array, TTL 1h)
- `session:{tenant_id}:{conversant_id}:summary` — compressed older context

Compression triggers when message count exceeds threshold (default 16). The oldest messages are summarized by the LLM into 2 sentences, stored as summary. Only the most recent N messages (default 10) are kept in full.

---

## Multi-Tenant Data Model

```
┌──────────┐     ┌──────────┐     ┌────────────────────┐
│  Tenant  │────<│  ApiKey  │     │ TenantCredentials  │
│          │     │          │     │ (whatsapp, twilio,  │
│  id (PK) │     │ key_hash │     │  llm — encrypted)  │
│  name    │     │ scopes   │     └────────────────────┘
│  active  │     │ active   │
└──────┬───┘     └──────────┘
       │
       ├────< KnowledgeDocument (slug, doc_type, body, campos_requeridos)
       ├────< TenantPrompt (estilo, system_prompt, tono, restricciones)
       ├────< Conversation (conversant_id, channel, resolution_status)
       │         └────< Message (role, content, tokens, cost, latency)
       └────< Event (event_type, provider, tokens, cost, latency)
```

Key design decisions:
- API keys stored as SHA-256 hashes; raw key shown only at creation
- Credentials encrypted with Fernet (master key in env var)
- Soft deletes: `status="archived"` for documents, `active=False` for prompts
- Composite unique: `(tenant_id, slug)` for documents, `(tenant_id, estilo)` for prompts

---

## Tools

### ejecutar_accion

Executes side-effect actions (orders, reservations). Schema is dynamic — built from the tenant's knowledge documents of type `accion`. Each action defines `campos_requeridos` and `campos_opcionales`.

Flow: LLM calls tool → tool checks if all required fields are present → if missing, returns `ToolError` with `campos_faltantes` → LLM asks user for those fields → retries.

### consultar_informacion_negocio

Reads the tenant's `negocio/info-general.md` and `negocio/promociones.md` documents. Used when the LLM needs to verify business info that's already in context but wants confirmation.

### buscar_base_conocimiento_extensa

Reads one or more documents by slug from the tenant's knowledge base. The LLM sees an index of available documents in its system prompt and requests specific ones by path.

### transferir_a_humano

Breaks the agent loop immediately. Sets `needs_human=True` in the session, which causes subsequent messages to get a "you're being attended by a human" reply until manually released via `POST /api/v1/sessions/{id}/release`.

---

## Voice Pipeline

### Cloud STT (default for API)

```
Audio bytes → Groq Whisper API → text
```

Uses `GROQ_API_KEY` if set. Fast, no GPU required.

### Local STT + TTS (for real-time calls)

```
Audio bytes → faster-whisper (GPU) → text
Text → Edge TTS → MP3 bytes
```

Enabled with `VOICE_ENABLED=true`. Requires CUDA-capable GPU.

### Twilio Real-Time Voice

```
Phone call → Twilio → TwiML (Connect/Stream) → WebSocket

WebSocket receives mulaw 8kHz chunks (20ms each):
  → SileroVAD detects speech probability per frame
  → TurnDetector accumulates speech, detects end-of-turn (700ms silence)
  → On turn end: mulaw → PCM 16kHz → Whisper → AgentRouter → TTS → mulaw → send back

Barge-in: if user speaks while bot is talking, clear the audio stream.
```

---

## Caching Strategy

| What | Where | TTL | Invalidation |
|------|-------|-----|--------------|
| Tenant config (docs + prompts) | Redis | 300s | On any write to knowledge/prompts endpoints |
| Session history | Redis | 3600s | Natural expiry |
| Dedup message IDs | Redis | 300s | Natural expiry |
| Rate limit windows | Redis sorted set | window_secs | Automatic (ZREMRANGEBYSCORE) |

---

## Error Handling Patterns

| Layer | Pattern |
|-------|---------|
| Routes | `raise HTTPException(status, detail)` |
| Middleware | Return `JSONResponse` directly |
| Tools | Return `ToolError` model (never raise) |
| Services (non-critical) | `try/except` + `logger.warning()` + continue |
| Services (critical) | `raise RuntimeError` to prevent startup |
| Channel adapters | Return `(False, latency_ms)` tuple |
| Background tasks | Fire-and-forget with logged warnings |

---

## Observability

### Structured Logging

JSON format with correlation ID on every log line:
```json
{"ts": "...", "level": "INFO", "logger": "...", "msg": "...", "correlation_id": "a1b2c3d4"}
```

### Metrics (in-memory)

`GET /metrics` returns counters and latency percentiles:
- `messages_received`, `messages_sent`, `errors`
- `llm_calls`, `tokens_input`, `tokens_output`
- `tool_calls:{tool_name}`
- Latency p95: `llm`, `whatsapp_send`, `webhook_total`

### Event Tracking (PostgreSQL)

Every billable operation writes to the `events` table:
- `llm_call`: provider, model, tokens in/out, cost, latency
- `stt`: provider, audio duration, latency
- `tts`: provider, characters, latency
- `whatsapp_msg`: status

Queried via `GET /api/v1/usage?from=...&to=...` for per-tenant billing.

### Analytics (SQLite — legacy)

Local SQLite with per-message and per-conversation aggregates. Detects frustration patterns, resolution, tool loops, and bot errors. Available at `GET /analytics`.

---

## Security

- API keys: SHA-256 hashed in DB, raw key shown only once at creation
- Tenant credentials: Fernet-encrypted (`_enc` suffix fields)
- No secrets in response bodies or logs
- Webhook verification: per-tenant `verify_token` (not global)
- Input validation: slug regex prevents path traversal
- Rate limiting: per-tenant AND per-sender (Redis sorted set)
- Auth middleware excludes only: `/health`, `/docs`, webhooks, WebSocket

---

## Deployment

### Docker Compose (development)

```bash
docker compose up --build
```

Runs: API (port 8000) + Redis (6379) + PostgreSQL (5434).

### Production checklist

1. Set `DATABASE_URL` (no default — fails fast if missing)
2. Set `CREDENTIAL_ENCRYPTION_KEY` (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
3. Set `LLM_API_KEY` for your provider
4. Set `DEBUG=false` (disables /docs endpoint)
5. Run database migrations (Aerich or manual schema apply)
6. Configure WhatsApp webhook URL: `https://your-domain/webhook/whatsapp/{tenant_id}`
7. Configure Twilio voice URL: `https://your-domain/incoming-call/{tenant_id}`

# Fases de Implementación

Cada fase tiene su propio documento con detalle de archivos, código, y pasos.

---

## Fase 1: PostgreSQL + Tortoise ORM + Docker

**Objetivo:** Tener la base de datos corriendo con todos los modelos definidos.

**Entregables:**
- PostgreSQL en docker-compose
- Tortoise ORM configurado con FastAPI
- Modelos: tenants, api_keys, tenant_credentials, knowledge_documents, tenant_prompts
- Migraciones iniciales aplicadas
- setup.sh actualizado para levantar PostgreSQL
- Tests de conexión

**Documento:** [fase-1-database.md](fase-1-database.md)

---

## Fase 2: Autenticación + Tenant Resolution

**Objetivo:** Cualquier request con API key válida resuelve su tenant automáticamente.

**Entregables:**
- Middleware de auth (X-API-Key → TenantContext)
- Fernet encryption para credentials
- Dependency injection: `get_current_tenant()`
- Rate limiting namespaced por tenant
- Tests de auth (key válida, inválida, expirada)

**Documento:** [fase-2-auth.md](fase-2-auth.md)

---

## Fase 3: Knowledge Base en PostgreSQL

**Objetivo:** El sistema OKF funciona desde la DB con CRUD via API.

**Entregables:**
- CRUD endpoints `/api/v1/knowledge` y `/api/v1/prompts`
- `TenantConfig` refactorizado para cargar de DB
- Fallback a BASE_SYSTEM_PROMPT si no hay prompt custom
- Cache en Redis con invalidación en writes
- Script de migración: filesystem OKF → PostgreSQL
- Tests: tools siguen funcionando con datos de DB

**Documento:** [fase-3-knowledge-base.md](fase-3-knowledge-base.md)

---

## Fase 4: Endpoint `/api/v1/converse`

**Objetivo:** Un endpoint universal para text↔text, text↔audio, audio↔text, audio↔audio.

**Entregables:**
- Request/response Pydantic models
- Multipart upload para audio
- conversant_id como identificador de interlocutor
- Integración con proveedores cloud (Groq STT, Edge-TTS, OpenRouter)
- Conversation persistence en PostgreSQL
- Audio file serving con URLs firmadas
- Tests de los 4 modos

**Documento:** [fase-4-converse-endpoint.md](fase-4-converse-endpoint.md)

---

## Fase 5: Webhooks Multi-Tenant

**Objetivo:** Cada tenant tiene su propio webhook de WhatsApp y número de Twilio.

**Entregables:**
- `/webhook/whatsapp/{tenant_id}` — parametrizado
- `/incoming-call/{tenant_id}` + `/ws/media-stream/{tenant_id}`
- Credentials cargadas de DB (no de .env)
- Validación de webhook signature de Meta por tenant
- Tests con payloads mock

**Documento:** [fase-5-webhooks.md](fase-5-webhooks.md)

---

## Fase 6: Métricas + Events + Usage

**Objetivo:** Trackear todo lo billable y tener visibilidad por tenant.

**Entregables:**
- Tabla `events` con cada operación (LLM, STT, TTS, WhatsApp, Twilio)
- Tabla `usage_daily` con agregados
- Endpoint `/api/v1/usage` (filtrado por tenant vía API key)
- Cálculo de costos por provider
- Stats script actualizado para multi-tenant

**Documento:** [fase-6-metrics.md](fase-6-metrics.md)

---

## Fase 7: Scripts de Gestión + Cleanup

**Objetivo:** Poder operar el sistema sin tocar la DB directamente.

**Entregables:**
- `scripts/create_tenant.py` — alta de tenant + API key
- `scripts/migrate_okf_to_db.py` — migrar santa_lena del filesystem
- Cleanup job para audio files antiguos
- Actualización de docs (README, .env.example)
- Smoke tests end-to-end

**Documento:** [fase-7-scripts.md](fase-7-scripts.md)

---

## Orden de Dependencias

```
Fase 1 (DB)
    ↓
Fase 2 (Auth) ←── requiere tenants table
    ↓
Fase 3 (Knowledge) ←── requiere auth + tenants
    ↓
Fase 4 (Converse) ←── requiere knowledge + auth
    ↓
Fase 5 (Webhooks) ←── requiere credentials en DB
    ↓
Fase 6 (Métricas) ←── requiere events table + todo lo anterior
    ↓
Fase 7 (Scripts) ←── requiere todo funcionando
```

Cada fase es deployable independientemente. Después de Fase 3, el sistema ya funciona multi-tenant para el endpoint converse. Las fases 5-7 agregan canales y operabilidad.

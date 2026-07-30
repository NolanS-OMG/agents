# Fase 6: Métricas + Events + Usage

## Objetivo

Trackear cada operación billable, agregar por día/tenant, y exponer un endpoint de usage.

---

## 6.1 Event Logging

**Archivo nuevo:** `src/app/services/event_tracker.py`

Cada vez que se hace una llamada a un provider externo, registrar:

```python
async def track_event(
    tenant_id: str,
    event_type: str,       # "llm_call", "stt", "tts", "whatsapp_send", "voice_minute"
    provider: str,         # "openrouter", "groq", "edge_tts", "twilio", "meta"
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    audio_duration_s: float = 0.0,
    characters: int = 0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    status: str = "success",
    conversation_id: str | None = None,
):
    await Event.create(...)
```

Integrar en:
- `AgentRouter.run()` → track llm_call
- STT service → track stt
- TTS service → track tts
- WhatsApp send → track whatsapp_send
- Voice call end → track voice_minute

---

## 6.2 Cálculo de Costos

**Archivo nuevo:** `src/app/services/cost_calculator.py`

```python
PRICING = {
    "groq_whisper_turbo": 0.00067,      # per minute
    "openrouter_input": 0.00,           # varies by model, lookup table
    "edge_tts": 0.0,                    # free
    "polly_neural": 0.000016,           # per character
    "twilio_inbound_mx": 0.0085,        # per minute
    "whatsapp_service": 0.0,            # free tier (service conversations)
}

def calculate_cost(event_type: str, provider: str, **kwargs) -> float:
    ...
```

---

## 6.3 Agregación Diaria

**Background task** que corre cada hora (o al cierre del día):

```python
async def aggregate_daily_usage(tenant_id: str, date: date):
    events = await Event.filter(tenant_id=tenant_id, created_at__date=date)
    # Sumar por tipo
    # Upsert en UsageDaily
```

Alternativa simple: calcular on-demand cuando se consulta `/usage`.

---

## 6.4 Endpoint de Usage

**Archivo nuevo:** `src/app/api/routes/usage.py`

```
GET /api/v1/usage?from=2026-07-01&to=2026-07-31
```

Requiere auth. Retorna:
```json
{
  "tenant_id": "santa_lena",
  "period": {"from": "2026-07-01", "to": "2026-07-31"},
  "totals": {
    "conversations": 1523,
    "text_requests": 1200,
    "audio_requests": 323,
    "voice_call_minutes": 45.2,
    "tokens_in": 890000,
    "tokens_out": 234000,
    "total_cost_usd": 12.45
  },
  "daily": [...]
}
```

---

## 6.5 Reemplazar AnalyticsStore (SQLite)

El `AnalyticsStore` actual usa SQLite. En multi-tenant, sus responsabilidades se dividen:
- Messages → tabla `messages` en PostgreSQL
- Conversations → tabla `conversations` en PostgreSQL
- Métricas de costo → tabla `events`
- Agregados → tabla `usage_daily`

El `AnalyticsStore` se depreca. Sus callers (webhook, chat) se migran a escribir directo en las tablas nuevas.

---

## 6.6 Tests

- Track event → verificar row en DB
- Aggregate daily → totales correctos
- GET /usage → retorna datos del tenant autenticado
- Un tenant no ve usage de otro

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `src/app/services/event_tracker.py` | **NUEVO** |
| `src/app/services/cost_calculator.py` | **NUEVO** |
| `src/app/api/routes/usage.py` | **NUEVO** |
| `src/app/services/analytics.py` | Deprecar (reemplazar callers) |
| `src/app/api/routes/webhook.py` | Migrar de analytics a events |
| `src/app/api/routes/converse.py` | Integrar event tracking |
| `tests/test_usage.py` | **NUEVO** |

# Sugerencias de Refactoring

Notas de mejora para legibilidad, mantenibilidad y DRY. Ninguna es urgente — el código funciona. Implementar cuando haya tiempo o antes de escalar.

---

## 1. Extraer `WebhookHandler` class del endpoint

**Archivo:** `src/app/api/routes/webhook.py`

El endpoint `whatsapp_webhook` tiene ~120 líneas con múltiples responsabilidades: parsing, rate limiting, needs_human check, agent execution, analytics logging, session management, reply sending. Refactorizar a:

```python
class WebhookHandler:
    def __init__(self, request: Request): ...
    async def handle(self, payload: dict) -> Response: ...
```

Cada paso como un método privado. El endpoint se reduce a 3 líneas.

---

## 2. SessionManager no debería necesitar LLMProvider

**Archivo:** `src/app/services/session.py`

Pasar el LLM al SessionManager acopla dos responsabilidades. Alternativa: extraer la compresión a un servicio separado `HistoryCompressor` que recibe mensajes y retorna el resumen. SessionManager solo hace I/O con Redis.

---

## 3. Duplicación en creación de SessionManager

**Archivos:** `webhook.py`, `chat.py`

Se crea `SessionManager(redis, llm=llm)` 3-4 veces en el mismo request. Crear una sola vez al inicio y reusar. Mejor aún: inyectar vía `Depends()` de FastAPI.

---

## 4. TenantConfig se carga en cada request

**Archivos:** `webhook.py`, `chat.py`

`load_tenant(settings.tenant_id)` parsea todos los markdown files en cada request. Para un negocio que no cambia, esto es trabajo repetido. Opciones:
- Cache en `app.state.tenant` (se carga una vez en lifespan)
- Cache con TTL (recargar cada 5 min)
- FileWatcher que invalida cache cuando cambian los archivos

---

## 5. Analytics logging es verbose y repetitivo

**Archivo:** `webhook.py`

Los dos `analytics.log_message()` calls tienen 15+ kwargs cada uno. Crear un dataclass `MessageEvent` que se construye una vez y se pasa a analytics:

```python
event = MessageEvent(conversation_id=..., role="assistant", ...)
analytics.log(event)
```

---

## 6. Separar parsing de datos de OpenRouter en su propio módulo

**Archivo:** `src/app/services/llm/openai_compatible.py`

El método `_parse_stream_response` tiene 80+ líneas mezclando SSE parsing, timing, y extracción de campos. Separar en:
- `_parse_sse_lines(text) -> Iterator[dict]` (puro parsing)
- `_build_response(chunks, start_time, retry_count) -> LLMResponse` (construcción)

---

## 7. Tool registry debería ser dinámico

**Archivo:** `src/app/tools/registry.py`

Actualmente hard-codea las 4 tools. Si añadimos más (ej: por tenant), hay que editar este archivo. Alternativa: auto-discovery desde el directorio `tools/` o configuración por tenant que lista qué tools activar.

---

## 8. `AgentResult` debería ser un dataclass o Pydantic model

**Archivo:** `src/app/services/agent_router.py`

`AgentResult` es una clase con 15 campos en `__init__`. Convertir a `@dataclass` o `BaseModel` para:
- Inmutabilidad (frozen=True)
- Serialización gratis
- Menos boilerplate

---

## 9. Lógica de `update_conversation` es demasiado larga

**Archivo:** `src/app/services/analytics.py`

El método tiene ~40 líneas con SQL, cálculos, y detección de patrones. Separar:
- `_compute_metrics(user_msgs, bot_msgs, tools, latencies) -> ConversationMetrics`
- `_upsert_conversation(id, metrics)` (solo SQL)

---

## 10. Webhook debería retornar 200 inmediatamente y procesar async

**Archivo:** `webhook.py`

Meta requiere 200 en <15s. Si el LLM tarda más, perdemos el webhook. Patrón correcto:
1. Retornar 200 inmediatamente
2. Procesar en background task (`BackgroundTasks` de FastAPI o una queue)

Esto también desacopla la latencia del LLM del timeout de Meta.

---

## 11. Constantes mágicas dispersas

Números hardcodeados en varios archivos:
- `MAX_TOOL_ITERATIONS = 5` (agent_router.py)
- `MAX_HISTORY_MESSAGES = 20` (session.py)
- `MAX_LATENCY_SAMPLES = 1000` (metrics.py)
- `MAX_CONTEXT_WINDOW = 128_000` (webhook.py)
- `SESSION_TTL = 3600` (session.py)

Moverlos todos a `config.py` como settings configurables por env var.

---

## 12. Tests no cubren el flujo de streaming

Los tests mockean con SSE text estático. No hay test que verifique:
- Retry count se propaga correctamente
- TTFT se mide bien
- Tool calls se acumulan correctamente desde chunks parciales
- Error handling cuando el stream se corta a mitad

---

## 13. Tipo de retorno inconsistente en `send_reply`

**Archivo:** `channels/whatsapp.py`

Retorna `tuple[bool, int]` lo cual es poco expresivo. Crear:
```python
@dataclass
class SendResult:
    success: bool
    latency_ms: int
    error: str | None = None
```

---

## 14. `_extract_table_column` usa heurísticas frágiles

**Archivo:** `tenant.py`

Parsear tablas markdown con splits y checks de `"-"` es propenso a fallar con formatos variados. Considerar usar una librería como `marko` o un parser de tablas markdown dedicado, o simplificar el formato OKF para usar listas en lugar de tablas para los campos.

---

## Prioridad sugerida

| # | Impacto | Esfuerzo |
|---|---------|----------|
| 10 | Alto (reliability) | Medio |
| 4 | Alto (performance) | Bajo |
| 1 | Alto (legibilidad) | Medio |
| 3 | Medio (DRY) | Bajo |
| 8 | Medio (mantenibilidad) | Bajo |
| 2 | Medio (SRP) | Medio |
| 5 | Medio (legibilidad) | Bajo |
| 6 | Medio (legibilidad) | Medio |
| 12 | Medio (confianza) | Alto |
| 11 | Bajo (config) | Bajo |
| 7 | Bajo (extensibilidad) | Medio |
| 9 | Bajo (legibilidad) | Bajo |
| 13 | Bajo (expresividad) | Bajo |
| 14 | Bajo (robustez) | Alto |

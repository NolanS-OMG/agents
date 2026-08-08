# Análisis de Manejo de Contexto (Tokens)

## Resumen ejecutivo

**Costo fijo por request:** ~3,200 tokens de input (sistema + tools)
**Request simple ("hola"):** ~3,250 tokens input, ~50 output = $0.000126 con Qwen Flash
**Request con tool call:** ~7,500 tokens input (2 llamadas LLM), ~150 output = $0.000285
**Request con RAG (3 docs):** ~10,000 tokens input (2 llamadas), ~200 output = $0.00038

---

## Desglose: ¿Qué se envía en cada llamada al LLM?

### 1. System Prompt (~2,100 tokens) — SE ENVÍA SIEMPRE

| Componente | Tokens aprox. | Fuente |
|-----------|--------------|--------|
| BASE_SYSTEM_PROMPT (reglas del agente) | ~450 | Hardcoded en `agent_router.py` |
| Negocio info body (horarios, dirección) | ~300 | `knowledge_documents` type=negocio |
| Promociones body | ~120 | `knowledge_documents` type=promociones |
| Índice de documentos disponibles | ~350 | Generado dinámicamente de todos los docs |
| Estilo de comunicación (tono, vocabulario, ejemplos) | ~620 | `tenant_prompts` tabla |
| Lista de docs disponibles + instrucción idioma | ~280 | Inyectado por `_build_system_prompt()` |
| **Total system prompt** | **~2,120** | |

### 2. Tool Schemas (~1,100 tokens) — SE ENVÍAN SIEMPRE

| Tool | Tokens aprox. | Contenido |
|------|--------------|-----------|
| `ejecutar_accion` | ~320 | Descripción + parámetros + enum de categorías |
| `consultar_informacion_negocio` | ~175 | Descripción + 1 parámetro |
| `buscar_base_conocimiento_extensa` | ~230 | Descripción + array de strings |
| `transferir_a_humano` | ~150 | Descripción + motivo |
| `dispatch_frontend` (si está activo) | ~235 | Descripción + tipo + datos |
| **Total tools** | **~1,100** | |

### 3. Historial de Conversación (variable) — CRECE CON CADA MENSAJE

| Estado del historial | Tokens aprox. |
|---------------------|--------------|
| Primera interacción (sin historial) | 0 |
| Después de 5 mensajes | ~250 |
| Después de 10 mensajes | ~500 |
| Después de compresión (summary + 10 recent) | ~550 |
| Sesión madura (resumen largo + 10 mensajes) | ~600 |

**Compresión:** Se activa cuando hay >16 mensajes. Genera un resumen de 2-3 oraciones (~50 tokens) y conserva los 10 mensajes más recientes. La compresión consume una llamada LLM extra (~600-1,100 tokens input).

### 4. Mensaje del Usuario (~10-50 tokens)

Típicamente 5-30 palabras en español.

### 5. Resultados de Tools (solo cuando se usan)

| Tool | Tokens del resultado |
|------|---------------------|
| `consultar_informacion_negocio` | ~400 (negocio + promos) |
| `buscar_base_conocimiento_extensa` (1 doc) | ~600 (un menú completo) |
| `buscar_base_conocimiento_extensa` (3 docs) | ~1,500 (tres menús) |
| `ejecutar_accion` (éxito) | ~70 |
| `ejecutar_accion` (error/campos faltantes) | ~100 |

---

## Flujo de una Conversación Típica

### Escenario A: "Hola" (primera interacción)

```
LLM Call 1:
  system prompt:  2,120 tokens
  tool schemas:   1,100 tokens
  user message:      10 tokens
  ─────────────────────────────
  INPUT TOTAL:    3,230 tokens
  OUTPUT:            ~40 tokens ("¡Qué onda! ¿Qué se te antoja?")
```

**Costo:** $0.000126 (Qwen), $0.000374 (DeepSeek)

### Escenario B: "¿Qué hamburguesas tienen?" (requiere RAG)

```
LLM Call 1 (decide buscar):
  system prompt:  2,120 tokens
  tool schemas:   1,100 tokens
  historial:        100 tokens
  user message:      15 tokens
  ─────────────────────────────
  INPUT:          3,335 tokens
  OUTPUT:           ~30 tokens (tool_call: buscar_conocimiento)

LLM Call 2 (responde con datos):
  system prompt:  2,120 tokens
  tool schemas:   1,100 tokens
  historial:        100 tokens
  user message:      15 tokens
  tool call msg:     30 tokens
  tool result:      600 tokens (menú hamburguesas completo)
  ─────────────────────────────
  INPUT:          3,965 tokens
  OUTPUT:          ~150 tokens (recomendación 2-3 opciones)
```

**Costo total:** ~7,300 input + ~180 output = $0.000243 (Qwen)

### Escenario C: "Quiero hacer un pedido a domicilio" (acción)

```
LLM Call 1 (intenta ejecutar):
  INPUT:          3,335 tokens
  OUTPUT:           ~50 tokens (tool_call: ejecutar_accion con campos parciales)

LLM Call 2 (recibe error de campos faltantes):
  INPUT:          3,335 + 50 + 100 = 3,485 tokens
  OUTPUT:           ~80 tokens ("Claro, dime tu nombre y dirección")

(usuario responde con datos)

LLM Call 3 (ejecuta con todos los campos):
  INPUT:          3,485 + 80 + 50 + 50 + 70 = 3,735 tokens
  OUTPUT:           ~50 tokens (tool_call completo)

LLM Call 4 (confirma):
  INPUT:          3,735 + 50 + 70 = 3,855 tokens
  OUTPUT:           ~60 tokens ("¡Listo! Tu pedido está en camino")
```

**Costo total:** ~14,400 input + ~240 output = $0.000463 (Qwen)

---

## ¿Dónde se desperdician tokens?

### 1. System Prompt repetido en CADA llamada (~2,120 tokens)

El system prompt se envía completo en cada iteración del tool-calling loop. Si hay 3 tool calls, se envía 3 veces = **6,360 tokens** en solo el prompt.

**Optimización posible:** Prompt caching (Gemini ofrece cache read a $0.03/1M = 70% descuento en la porción cacheada).

### 2. Tool schemas repetidos en CADA llamada (~1,100 tokens)

Los 4 schemas se envían siempre, aunque el LLM ya "sabe" que existen del call anterior.

**Optimización posible:** Prompt caching. O: solo enviar tools relevantes por contexto (pero esto rompe la arquitectura actual).

### 3. Índice de documentos completo en system prompt (~350 tokens)

Lista TODOS los documentos disponibles siempre, aunque la mayoría de queries no necesitan RAG.

**Optimización posible:** Solo listar categorías (no cada doc individual). Pasar de 13 items a 3 categorías: menú, acciones, info.

### 4. Estilo completo con EJEMPLOS (~620 tokens)

El estilo incluye ejemplos de conversación completos (~4 pares pregunta-respuesta). Útil para calidad pero caro.

**Optimización posible:** Reducir a 1-2 ejemplos cortos en vez de 4 largos. O: usar fine-tuning/few-shot en vez de in-context.

### 5. Historial no se comprime hasta 16 mensajes

Entre el mensaje 1 y 16, el historial crece linealmente sin control.

**Optimización posible:** Comprimir antes (cada 8 mensajes) o usar sliding window más agresivo (keep 5 instead of 10).

---

## Tabla resumen de overhead

| Componente | % del input típico | ¿Evitable? |
|-----------|-------------------|------------|
| System prompt | 60-65% | Parcial (caching, reducir) |
| Tool schemas | 30-35% | Parcial (caching) |
| Historial | 0-15% | Sí (comprimir antes) |
| User message | 1-2% | No |
| Tool results | 0-20% (solo con tools) | Parcial (resumir docs) |

---

## Comparación: costo por escenario con diferentes modelos

| Escenario | Qwen Flash ($0.03/1M) | DeepSeek v4 ($0.09/1M) | Gemini Flash Lite ($0.10/1M) |
|-----------|----------------------|----------------------|---------------------------|
| "Hola" (3.2K in) | $0.000097 | $0.000290 | $0.000320 |
| Menú query + RAG (7.3K in) | $0.000219 | $0.000657 | $0.000730 |
| Pedido completo (14.4K in) | $0.000432 | $0.001296 | $0.001440 |
| 1000 conversaciones/mes mixtas | **~$0.30** | **~$0.90** | **~$1.00** |

---

## Recomendaciones de optimización (en orden de impacto)

1. **Prompt caching** (Gemini): 90% descuento en system prompt + tools = reduce overhead fijo de 3,200 a ~320 tokens efectivos
2. **Reducir índice de docs**: Listar solo 3 categorías en vez de 13 paths = ahorrar ~250 tokens/call
3. **Comprimir estilo**: 2 ejemplos cortos en vez de 4 largos = ahorrar ~300 tokens/call
4. **Sliding window más agresivo**: Keep 5 mensajes en vez de 10 = ahorrar ~250 tokens/call
5. **Resumir tool results antes de re-enviar**: Si un menú tiene 15 items, resumir a los 3 relevantes antes del siguiente call

# Comparación de Modelos LLM para el Agente (OpenRouter)

> Investigado: 2026-08-08. Todos soportan tool/function calling via OpenRouter.

## Recomendaciones

| Uso | Modelo | Input $/1M | Output $/1M | Por qué |
|-----|--------|-----------|-------------|---------|
| **Producción** | `deepseek/deepseek-v4-flash-0731` | $0.09 | $0.18 | Mejor score agéntico (48.4), 115 tok/s, 1M context |
| **Alt. producción** | `google/gemini-2.5-flash-lite` | $0.10 | $0.40 | Más rápido (386 tok/s), mejor español, prompt caching |
| **Desarrollo** | `qwen/qwen3.7-flash` | $0.03 | $0.13 | Casi gratis, 1M context, tool calling |
| **Fallback** | `mistralai/mistral-small-3.2-24b-instruct` | $0.094 | $0.25 | Optimizado para function calling, buen español |

## Costo estimado (producción, 10 tenants)

Asumiendo ~500 tokens in + ~200 tokens out por intercambio WhatsApp:
- DeepSeek v4 Flash: **$0.000081/mensaje** → 100K mensajes/mes = **$8.10**
- Gemini 2.5 Flash Lite: **$0.00013/mensaje** → 100K mensajes/mes = **$13.00**
- Qwen 3.7 Flash: **$0.000041/mensaje** → 100K mensajes/mes = **$4.10**

---

## Ranking por Velocidad (tokens/segundo)

| # | Modelo | tok/s | TTFT |
|---|--------|-------|------|
| 1 | `google/gemini-2.5-flash-lite` | ~386 | 8.69s* |
| 2 | `deepseek/deepseek-v4-flash-0731` | ~115 | 1.15s |
| 3 | `meta-llama/llama-4-scout` | ~99 | — |
| 4 | `meta-llama/llama-3.1-8b-instruct` | Muy rápido (8B) | — |
| 5 | `mistralai/mistral-nemo` | Muy rápido (12B) | — |

*TTFT alto de Gemini es por reasoning; se puede desactivar para WhatsApp.

---

## Ranking por Calidad (Agentic/Tool Calling Score)

| # | Modelo | Score | Notas |
|---|--------|-------|-------|
| 1 | `deepseek/deepseek-v4-flash-0731` | 48.4 | MoE 284B/13B activos, diseñado para agentes |
| 2 | `google/gemini-3.5-flash-lite` | 27.2 | Más caro ($0.30), diseñado para sub-agentes |
| 3 | `deepseek/deepseek-v3.2` | 18.3 | $0.27 input, bueno pero más caro |
| 4 | `qwen/qwen3-32b` | 1.8 | Dense 32B, bueno para razonamiento |
| 5 | `meta-llama/llama-4-scout` | 1.1 | MoE 109B, contexto enorme pero score bajo |

---

## Ranking por Precio (más baratos primero)

| # | Modelo | In $/1M | Out $/1M | Context |
|---|--------|---------|----------|---------|
| 1 | `mistralai/mistral-nemo` | $0.019 | $0.03 | 131K |
| 2 | `qwen/qwen3.7-flash` | $0.03 | $0.13 | 1M |
| 3 | `qwen/qwen3-30b-a3b-instruct-2507` | $0.048 | $0.19 | 262K |
| 4 | `meta-llama/llama-3.1-8b-instruct` | $0.05 | $0.08 | 131K |
| 5 | `qwen/qwen3.5-flash-02-23` | $0.065 | $0.26 | 1M |
| 6 | `qwen/qwen3-32b` | $0.08 | $0.28 | 131K |
| 7 | `deepseek/deepseek-v4-flash-0731` | $0.09 | $0.18 | 1M |
| 8 | `mistralai/mistral-small-3.2-24b-instruct` | $0.094 | $0.25 | 256K |
| 9 | `google/gemini-2.5-flash-lite` | $0.10 | $0.40 | 1M |
| 10 | `meta-llama/llama-3.3-70b-instruct` | $0.10 | $0.32 | 131K |

---

## Notas por Familia

### DeepSeek
- `deepseek-v4-flash-0731`: Mejor relación calidad-precio absoluta. Soporta `reasoning_effort` (low/high). Poner en "low" para consultas simples (menú) y "high" para pedidos complejos.
- Riesgo: empresa china, español no es idioma primario. Probar calidad de tool-calling en español.

### Google Gemini
- `gemini-2.5-flash-lite`: El más rápido. Soporta prompt caching (leer cache: $0.03/1M = 90% descuento en system prompt repetido).
- Mejor soporte de español de todos (Google Translate heritage).
- `structured_outputs` garantiza JSON válido en tool calls.

### Qwen (Alibaba)
- `qwen3.7-flash`: Ridículamente barato ($0.03/1M). Bueno para desarrollo.
- `qwen3-30b-a3b-instruct-2507`: MoE 30B/3B activos, modo non-thinking. Buena calidad sin overhead de razonamiento.
- Buen soporte multilingüe (inglés, chino, +idiomas).

### Meta Llama
- `llama-3.3-70b-instruct`: Probado en producción, buen español. Pero score agéntico bajo (0.3).
- `llama-4-scout`: Contexto de 1.3M tokens pero score agéntico débil (1.1).
- En general: Llama es bueno para texto pero débil para tool calling comparado con DeepSeek/Gemini.

### Mistral
- `mistral-small-3.2-24b-instruct`: Explícitamente optimizado para function calling. Empresa francesa = buen español.
- `mistral-nemo`: Ultra-barato ($0.019/1M) pero modelo viejo, quality limitada.

---

## Config recomendada para .env

```bash
# Producción (mejor calidad agéntica)
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-v4-flash-0731
LLM_BASE_URL=https://openrouter.ai/api/v1

# Alternativa (más rápido, mejor español)
# LLM_MODEL=google/gemini-2.5-flash-lite

# Desarrollo (casi gratis)
# LLM_MODEL=qwen/qwen3.7-flash
```

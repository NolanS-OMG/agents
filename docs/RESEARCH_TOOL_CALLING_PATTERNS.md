# Research: Cómo los Agentes en Producción Manejan Tool Calling

## El Problema Central

El LLM necesita entender que parte de su trabajo es **enriquecer la experiencia visual del frontend** — no solo responder con texto. ¿Cómo hacen los agentes en producción para que el modelo sepa cuándo y cómo disparar acciones de UI?

---

## 1. Gemini (Google)

### Sistema de Decisión

Gemini usa tres modos via `tool_choice`:
- `"auto"` (default): El modelo decide independientemente si invocar una función o responder directo
- `"any"`: Forzado a siempre predecir un function call
- `"none"`: Prohibido hacer function calls

### Multi-Tool Orchestration

1. **Ejecución Paralela** — Múltiples funciones independientes se ejecutan simultáneamente en un solo turno cuando no tienen dependencias
2. **Composicional/Secuencial** — Para workflows complejos, encadena múltiples calls a través de turnos

### Google Search Grounding (Enrichment Automático) — EL PATRÓN CLAVE

Este es el patrón más relevante para nuestro problema. Gemini:
1. Analiza el prompt entrante
2. **Autónomamente determina** si Google Search enriquecería la respuesta — sin dirección explícita del usuario
3. Ejecuta queries automáticamente
4. Procesa resultados y sintetiza
5. Retorna respuesta con citaciones inline

**Esto es exactamente la solución de Google al problema de "el modelo debe enriquecer la respuesta más allá del texto"** — dispara tools de enrichment automáticamente cuando el modelo juzga que agregan valor.

### Project Mariner (Control de UI)

El agente experimental de Google puede "entender y razonar sobre información en tu pantalla" y controlar UI directamente. Demuestra el patrón de decisiones del LLM disparando acciones de UI directamente.

---

## 2. Claude (Anthropic)

### Cómo Decide

> "Claude determines when to call a tool based on the user's request and the tool's description. It calls a tool when the request maps to that tool's described capability and the answer isn't already in context."

### Steering via System Prompt — CLAVE

> "This boundary is steerable through your system prompt. If Claude isn't calling tools when you expect, a light instruction such as 'Use the tools to investigate before responding.' increases tool use. A stronger form such as 'Always call a tool first before responding.' pushes further."

### Tool Descriptions (El Factor #1 en Confiabilidad)

Anthropic dice que esto es **"by far the most important factor in tool performance"**:

**Buena descripción:**
```json
{
  "name": "get_stock_price",
  "description": "Retrieves the current stock price for a given ticker symbol. The ticker symbol must be a valid symbol for a publicly traded company on a major US stock exchange. The tool will return the latest trade price in USD. It should be used when the user asks about the current or most recent price of a specific stock. It will not provide any other information about the stock or company.",
  "input_schema": { ... }
}
```

**Mala descripción:**
```json
{
  "name": "get_stock_price",
  "description": "Gets the stock price for a ticker.",
  "input_schema": { ... }
}
```

**Reglas:**
- Mínimo 3-4 oraciones por tool
- Explicar QUÉ hace, CUÁNDO usarla (y cuándo NO), qué significa cada parámetro
- Consolidar operaciones relacionadas en menos tools
- Usar `input_examples` para tools complejas

### Concepto "Trained-in"

Tools cuyo schema el modelo fue **optimizado para usar** se llaman más confiablemente que tools custom equivalentes. El modelo "conoce" ciertos schemas de fábrica.

### Multi-output (text + tool_use simultáneo)

Claude y Gemini soportan nativamente responder con texto Y disparar un tool_use en el mismo turno. Este es el mecanismo para "responder + enriquecer simultáneamente".

---

## 3. OpenAI (ChatGPT/GPTs)

### Mejores Prácticas

- Nombres claros y descripciones detalladas
- Usar enums y estructura para "hacer estados inválidos irrepresentables"
- No hacer que el modelo llene argumentos que ya conoces (pre-fill lo estático)
- **Mantener bajo 20 tools iniciales** para mejor accuracy
- Incluir ejemplos concretos de cuándo invocar
- Especificar cuándo NO usar ciertas tools
- Instruir al modelo a "resolver el query completo antes de ceder control, descomponiendo en sub-tareas"

### `strict: true`

Garantiza que los function calls se adhieran al schema via structured outputs.

---

## 4. Patrones Clave para Enrichment Confiable

### Patrón 1: Response Protocol en System Prompt

Definir reglas explícitas de cuándo disparar cada acción:

```
RESPONSE PROTOCOL:
- When discussing a specific project → ALWAYS call ejecutar_accion("mostrar-proyectos", {ids: [project_id]})
- When mentioning a section of the portfolio → ALWAYS call ejecutar_accion("navegar-a-seccion", {section: "..."})
- When the user asks to contact → ALWAYS call ejecutar_accion("iniciar-formulario-contacto")
```

### Patrón 2: Tool Description con Triggers Explícitos

En vez de:
```
"Ejecuta acciones del frontend"
```

Escribir:
```
"Dispatches visual actions to the user's browser. MUST be called in these scenarios:
- User asks about or you discuss a specific project → show_projects with that project's ID
- User asks to see work/portfolio → navigate_to projects section
- User wants to contact → send_message form
You should call this tool PROACTIVELY to enrich the visual experience, not only when explicitly asked."
```

### Patrón 3: Enrichment como Responsabilidad Mandatoria

No presentar las tools de UI como "opcionales". Enmarcarlo como parte del ROL del agente:

```
You are a portfolio assistant. Your job has TWO parts:
1. Answer questions with accurate information
2. ORCHESTRATE the visual experience — show relevant projects, navigate to sections, and trigger UI actions that complement your text response

A text-only response when a visual action was relevant is INCOMPLETE.
```

### Patrón 4: Ejemplos In-Context (Few-shot en el prompt)

```
EXAMPLES:
User: "Tell me about his AI projects"
→ You MUST: buscar_base_conocimiento_extensa(["snake-rl"]) AND ejecutar_accion("mostrar-proyectos", {ids: ["snake-rl"]})

User: "How can I reach him?"
→ You MUST: ejecutar_accion("mostrar-info-contacto") AND then answer with contact details
```

### Patrón 5: Classifier Post-Hoc (Segundo pase)

Después de que el LLM responde, un segundo pase ligero evalúa:
- "¿Se mencionó un proyecto? → emit show_projects"
- "¿Se habló de contacto? → emit copy_contact"

Esto es un safety net, no el mecanismo primario.

---

## 5. Por Qué Fallan los Tool Calls

| Causa | Solución |
|-------|----------|
| Descripción vaga de la tool | Mínimo 3-4 oraciones, con CUÁNDO usarla |
| Demasiadas tools (>20) | Consolidar, lazy-load |
| El modelo no "sabe" que debe enriquecer | System prompt explícito con protocol |
| Sin ejemplos | Few-shot en prompt o `input_examples` |
| Tool presentada como opcional | Enmarcar como MANDATORIA en ciertos contextos |
| Modelo barato | Modelos más capaces siguen instrucciones de tools mejor |

---

## 6. Hallazgo de Anthropic sobre SWE-bench

> "More time optimizing tools than the overall prompt" was needed for reliable tool calling in their SWE-bench agents.

Implicación: **invierte más en las descripciones de las tools que en el system prompt general**.

---

## 7. Recomendación para Nuestro Agente

### Approach: Prompt-Driven Enrichment (Camino B mejorado)

Dado que:
- Camino A (hardcoded) no escala
- Camino C (backend auto-dispatch) depende de granularidad de docs que no siempre tendremos
- **Los modelos son steering-able** — con el prompt correcto, tool descriptions correctas, y ejemplos, el modelo SÍ puede hacer enrichment confiablemente

**Implementar:**

1. **Reescribir la tool description de `ejecutar_accion`** — hacerla 5-8 oraciones, con triggers explícitos de cuándo DEBE usarse

2. **Agregar "Response Protocol" al system prompt** — lista explícita de: "cuando discutas X, SIEMPRE dispara Y"

3. **Few-shot examples en el prompt** — 2-3 ejemplos concretos de respuestas que combinan información + acción visual

4. **Considerar un modelo más capaz** para el router (si DeepSeek falla consistentemente en tool calling, el costo del enrichment perdido > el ahorro del modelo barato)

5. **Safety net backend opcional** — si después del turno del LLM no hubo tool_call pero la respuesta menciona un proyecto, el backend puede emitir el `show_projects` como fallback

### Ejemplo de Tool Description Mejorada

```python
EJECUTAR_ACCION_DESCRIPTION = """
Dispatches a visual/interactive action to the user's browser interface.

WHEN TO USE (mandatory, not optional):
- You mention or discuss a specific project → call with "mostrar-proyectos" and the project IDs
- You recommend the user view a section → call with "navegar-a-seccion"
- User wants to contact or send a message → call with "iniciar-formulario-contacto"
- You share contact information → call with "mostrar-info-contacto"
- User asks about compatibility/fit → call with "mostrar-compatibilidad"
- User asks for CV/resume → call with "descargar-cv"

IMPORTANT: A response that discusses a project without showing it visually is INCOMPLETE.
Call this tool ALONGSIDE your text response to create a rich visual experience.
Do NOT wait for the user to explicitly ask "show me" — trigger proactively when relevant.
"""
```

---

## Fuentes

- Google AI: ai.google.dev/gemini-api/docs/function-calling
- Anthropic: platform.claude.com/docs/en/agents-and-tools/tool-use/
- Anthropic Research: anthropic.com/research/building-effective-agents
- Anthropic Engineering: anthropic.com/engineering/writing-tools-for-agents
- OpenAI: developers.openai.com/docs/guides/function-calling
- OpenAI Agents: developers.openai.com/docs/guides/agents
- MCP: modelcontextprotocol.io/docs/concepts/tools
- LangChain: langchain.com/blog/tool-calling-with-langchain

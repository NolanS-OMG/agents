# CLAUDE.md - Agente IA para Atención al Cliente

## Descripción

Agente de IA con arquitectura de 3 tools mínimas (ejecutar_accion, consultar_informacion_negocio, buscar_base_conocimiento_extensa) orquestado por un LLM Router. Python + FastAPI + Pydantic.

## Comandos

```bash
# Desarrollo local
uv sync                          # instalar dependencias
uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000

# Docker
docker compose up --build        # levantar todo
docker compose down              # detener

# Calidad
uv run ruff check src/           # lint
uv run ruff format src/          # format
uv run mypy src/                 # type check
uv run pytest                    # tests
```

## Estructura

```
src/app/
  main.py                  # FastAPI app instance + routers
  core/
    config.py              # BaseSettings (env vars)
    lifespan.py            # startup/shutdown (Redis, HTTP client)
  api/routes/              # Endpoints HTTP
  services/llm/            # Servicio de proveedores LLM (factory + providers)
  tools/                   # Las 3 tools del agente (ejecutar_accion, info_negocio, RAG)
  models/                  # Pydantic models compartidos
  middleware/              # Guardrails, sanitización, rate limiting
```

## Convenciones de código

### Tipado estricto
- Todo modelo Pydantic usa `ConfigDict(strict=True)` en boundaries de API
- Todas las funciones tienen type hints explícitos en parámetros y retorno
- Nunca usar `Any` excepto en interfaces genéricas documentadas
- Preferir `dict[str, X]` sobre `Dict[str, X]` (syntax moderna 3.12)

### Async obligatorio
- Todas las llamadas I/O (LLM, APIs, Redis, DB) son `async`/`await`
- `httpx.AsyncClient` compartido via lifespan, nunca instanciar por request
- Nunca usar `requests` (bloqueante); siempre `httpx`

### Estilo
- Sin comentarios salvo constraint no obvio
- Sin docstrings multi-línea; máximo 1 línea si es necesaria
- Nombres descriptivos en español para tools y modelos de dominio del negocio
- Nombres en inglés para infraestructura técnica (services, providers, middleware)
- Line length: 100 chars

### Patrones
- Dependency injection via FastAPI `Depends()` con `Annotated`
- Service layer: lógica de negocio en services, no en routes
- Tools implementan `BaseTool` (ABC) con `execute()` async y `schema()` para OpenAI format
- Errores de validación en tools retornan `ToolError` (patrón 400), nunca exceptions
- Config centralizada en `core/config.py` via `pydantic_settings.BaseSettings`

### LLM Provider Service
- Factory pattern: `get_llm_provider()` retorna la implementación correcta
- Todos los providers implementan `LLMProvider` ABC
- Un solo punto de entrada para cambiar de proveedor (OpenRouter, Groq, Gemini, Bedrock, etc.)
- El provider traduce al formato OpenAI-compatible internamente

### Tests
- Archivos: `tests/test_<module>.py`
- Fixtures compartidos en `tests/conftest.py`
- Usar `pytest-httpx` para mockear llamadas HTTP al LLM (intercepta httpx.AsyncClient global)
- Async tests con `pytest-asyncio` (mode=auto), decorator `@pytest.mark.anyio`
- `ASGITransport(app=app)` para tests de integración (dispara lifespan events)
- Secuencia de `add_response` en pytest-httpx para simular loop de tool-calling
- `fakeredis` para mock de Redis sin necesidad de servicio externo
- Tests unitarios de tools: instanciar directamente y llamar `execute()`

### Git
- Commits atómicos: un commit por unidad lógica de cambio
- Formato: `<tipo>: <descripción corta>` (feat, fix, refactor, test, docs, chore)
- Siempre hacer commit después de cada cambio funcional completo
- Nunca acumular cambios de múltiples áreas en un solo commit

### Codebase Memory (MCP)
- Proyecto indexado como `home-nolan-proyectos-propios-prototipo-agente`
- Usar `search_graph` para encontrar funciones/clases/rutas antes de grep
- Usar `trace_path` para seguir call chains
- Usar `get_code_snippet` para obtener código exacto de un símbolo
- Re-indexar después de cambios estructurales significativos

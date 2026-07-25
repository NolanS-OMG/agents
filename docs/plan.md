# Plan de Implementación - Agente IA para Atención al Cliente

## Objetivo

Bot de atención al cliente multi-canal (WhatsApp, Web, Redes Sociales) orquestado por un LLM Router con 3 tools mínimas de alto nivel, siguiendo la arquitectura documentada en el PDF de referencia.

## Arquitectura Core

```
Cliente (WhatsApp / Web / API)
       │
       ▼
Capa de Guardrails & Filtros
       │
       ▼
AGENTE PADRE (LLM Router)
       │
       ├── Tool 1: ejecutar_accion         → Sub-workflows (Agenda, CRM, Mail)
       ├── Tool 2: consultar_info_negocio   → Datos estáticos OKF/Markdown
       └── Tool 3: buscar_conocimiento      → RAG (Embeddings + Keyword)
```

## Fases de Implementación

### Fase 1: Esqueleto funcional (ACTUAL)
- [x] Proyecto Python con uv + FastAPI + Pydantic
- [x] Docker + docker-compose (API + Redis)
- [x] Estructura de carpetas y módulos
- [x] Setup.sh para levantar todo
- [x] CLAUDE.md con convenciones
- [x] Servicio LLM con provider factory (OpenAI-compatible)
- [x] Esqueleto de las 3 tools con patrón Error 400
- [x] Endpoint /chat conectado al LLM Router
- [x] System prompt del Agente Padre
- [x] Loop de tool-calling (recibir tool_calls, ejecutar, responder)
- [x] Gestión de sesión en Redis (historial por session_id)
- [x] Tests robustos del AgentRouter (21 tests: unitarios + integración)

### Fase 2: Agente funcional básico (COMPLETADA)
- [x] Sistema de tenants con OKF v0.2 (markdown + YAML frontmatter)
- [x] Tool 2 funcional: info de negocio desde documentos OKF
- [x] Tool 1 funcional: validación dinámica de campos desde acciones OKF
- [x] Tool 3: lectura directa de documentos por ruta (el LLM navega el índice)
- [x] Estilos de comunicación configurables (chat/voz) con few-shot examples
- [x] CLI para testing en terminal
- [ ] Compresión/resumen de historial cuando excede N tokens (diferido)
- [ ] Handover protocol: escalar_a_humano (diferido)

### Fase 3: RAG y conocimiento extenso
- [ ] Integración con vector store (pgvector o similar)
- [ ] Pipeline de ingesta de documentos
- [ ] Búsqueda híbrida (keyword + semantic) en Tool 3
- [ ] Chunking y re-ranking de resultados

### Fase 4: Multi-canal
- [ ] Webhook para WhatsApp (Meta Cloud API)
- [ ] Adaptador de canal genérico (normalizar mensajes de cada fuente)
- [ ] Widget web (WebSocket o polling)
- [ ] Rate limiting por canal/usuario

### Fase 5: Observabilidad y mejora continua
- [ ] Logging estructurado de trazas (prompt, tool seleccionada, parámetros, resultado)
- [ ] Métricas: Tasa de Error 400, TCR, Handover Rate, Latencia, Tokens por sesión
- [ ] Dashboard de métricas
- [ ] Sistema de evaluación (eval set con conversaciones pasadas)
- [ ] Data flywheel: clasificación de fallos → refinamiento de prompts

### Fase 6: Producción
- [ ] Multi-tenancy (cada cliente/empresa con su config, OKF, y tools)
- [ ] Colas asíncronas (BullMQ/Celery equivalent) para integraciones lentas
- [ ] Confirmación explícita para acciones destructivas/financieras
- [ ] Sanitización anti prompt-injection
- [ ] Health checks avanzados y alerting

## Servicio de Proveedores LLM

Diseño: un servicio intermediario que abstrae el proveedor concreto de LLM.

```
LLMProvider (ABC)
  ├── OpenAICompatibleProvider  → OpenRouter, Groq, Cerebras, NVIDIA NIM, etc.
  ├── AnthropicProvider         → Claude directo / Bedrock
  ├── GeminiProvider            → Google AI Studio
  └── AzureProvider             → Azure OpenAI
```

El `provider_factory` selecciona la implementación según config. Esto permite:
- En desarrollo: usar free tiers (OpenRouter :free, Gemini Flash, GroqCloud)
- En producción: usar API de pago del proveedor que el cliente prefiera
- Mezclar modelos: un modelo rápido/barato para routing, uno potente para tareas complejas

## Decisiones técnicas

| Decisión | Elección | Razón |
|----------|----------|-------|
| Runtime | Python 3.12 + FastAPI | Async nativo, ecosystem maduro para LLMs |
| Validación | Pydantic v2 strict | Type safety en boundaries, performance |
| HTTP client | httpx async | No blocking, connection pooling |
| Cache/Session | Redis | Rápido, pub/sub para eventos, TTL nativo |
| Package manager | uv | 10-100x más rápido que pip, lockfile determinista |
| Container | Docker multi-stage | Imágenes pequeñas, reproducible |
| Linter/Format | Ruff | Reemplaza flake8+isort+black, ultra rápido |
| Type checker | Mypy strict | Catch bugs en compile time |

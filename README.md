# Agente IA — Customer Service AI Agent

Multi-tenant AI agent for customer service. Supports text and voice across WhatsApp, phone calls (Twilio), and a REST API. Each tenant configures their own prompts, knowledge base, and credentials from a single deployment.

## Features

- **3-tool architecture**: `ejecutar_accion` (orders, reservations), `consultar_informacion_negocio` (business info), `buscar_base_conocimiento_extensa` (knowledge base search)
- **Multi-tenant**: isolated credentials, prompts, knowledge docs, and usage tracking per tenant
- **Channels**: WhatsApp (Meta Cloud API), Twilio voice calls (real-time WebSocket), REST API (`/api/v1/converse`)
- **Voice pipeline**: STT (Whisper local or Groq cloud) + TTS (Edge TTS) with VAD-based turn detection
- **Session management**: Redis-backed conversation history with LLM-powered compression
- **Analytics**: per-message and per-conversation metrics with frustration/resolution detection

## Quick Start

```bash
# Prerequisites: Python 3.12+, Docker, uv
git clone <repo-url> && cd prototipo-agente

# Start infrastructure
docker compose up -d redis postgres

# Install dependencies and run
uv sync
cp .env.example .env  # configure your keys
uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker compose up --build
```

## Configuration

All configuration via environment variables (see `src/app/core/config.py`):

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | No | Redis URL (defaults to `redis://redis:6379/0`) |
| `LLM_API_KEY` | Yes | API key for LLM provider |
| `LLM_BASE_URL` | No | OpenAI-compatible endpoint (default: OpenRouter) |
| `LLM_MODEL` | No | Model identifier (default: `meta-llama/llama-3.3-70b-instruct:free`) |
| `CREDENTIAL_ENCRYPTION_KEY` | Yes* | Fernet key for encrypting tenant secrets |
| `GROQ_API_KEY` | No | Groq API key for cloud STT |
| `VOICE_ENABLED` | No | Enable local Whisper + TTS pipeline |

*Required for multi-tenant webhook functionality.

## Tenant Setup

```bash
# Create a new tenant with an API key
uv run python scripts/create_tenant.py --id mi_negocio --name "Mi Negocio"

# Rotate a tenant's API key
uv run python scripts/rotate_api_key.py --tenant-id mi_negocio
```

Then configure the tenant via API:

```bash
# Upload knowledge documents
curl -X POST http://localhost:8000/api/v1/knowledge \
  -H "X-API-Key: sk_..." \
  -H "Content-Type: application/json" \
  -d '{"slug": "menu/pizzas", "doc_type": "menu", "title": "Pizzas", "body": "..."}'

# Configure the agent prompt
curl -X POST http://localhost:8000/api/v1/prompts \
  -H "X-API-Key: sk_..." \
  -H "Content-Type: application/json" \
  -d '{"estilo": "chat", "system_prompt": "Eres el asistente de Mi Negocio..."}'
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/converse` | API Key | Text/audio conversation (multipart form) |
| POST | `/api/v1/chat` | API Key | Simple text chat (JSON) |
| CRUD | `/api/v1/knowledge` | API Key | Manage knowledge documents |
| CRUD | `/api/v1/prompts` | API Key | Manage agent prompts |
| GET | `/api/v1/usage?from=...&to=...` | API Key | Usage metrics by date range |
| POST | `/webhook/whatsapp/{tenant_id}` | Meta verify | WhatsApp webhook |
| POST | `/incoming-call/{tenant_id}` | Twilio | Voice call entry point |
| GET | `/health` | None | Health check |

## Development

```bash
uv run ruff check src/          # lint
uv run ruff format src/         # format
uv run mypy src/                # type check
uv run pytest                   # tests
```

## Project Structure

```
src/app/
  main.py                       # FastAPI app + router registration
  core/                         # Config, lifespan, logging
  api/routes/                   # HTTP endpoints (thin orchestration)
  api/deps.py                   # FastAPI dependencies (CurrentTenant DI)
  services/                     # Business logic
    agent_router.py             # LLM tool-calling loop (max 5 iterations)
    message_processor.py        # Shared transcribe + process + reply flow
    session.py                  # Redis session management + compression
    tenant_loader.py            # DB -> cache -> filesystem fallback
    llm/                        # LLM provider abstraction (OpenAI-compatible)
    voice_pipeline.py           # STT + TTS orchestration
    vad.py                      # Silero VAD + turn detection
  tools/                        # Agent tools (base + 4 implementations)
  channels/                     # Channel adapters (WhatsApp)
  middleware/                   # Auth, rate limiting, correlation ID
  db/                           # Tortoise ORM models
scripts/                        # CLI management tools
docs/                           # Architecture docs
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed system design.

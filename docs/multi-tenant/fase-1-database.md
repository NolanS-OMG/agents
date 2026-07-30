# Fase 1: PostgreSQL + Tortoise ORM + Docker

## Objetivo

Tener PostgreSQL corriendo en Docker para desarrollo, Tortoise ORM configurado con FastAPI async, y todos los modelos del sistema definidos con migraciones aplicadas.

---

## 1.1 Docker Compose

**Archivo:** `docker-compose.yml` (modificar)

Agregar servicio `postgres`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agente_ia
      POSTGRES_USER: agente
      POSTGRES_PASSWORD: dev_password_123
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agente -d agente_ia"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

---

## 1.2 Dependencias

**Archivo:** `pyproject.toml`

```toml
dependencies = [
    # ... existentes ...
    "tortoise-orm[asyncpg]>=0.23.0",
    "asyncpg>=0.30.0",
    "cryptography>=44.0.0",
]
```

---

## 1.3 Configuración

**Archivo:** `src/app/core/config.py`

Agregar:
```python
database_url: str = Field(default="postgres://agente:dev_password_123@localhost:5432/agente_ia")
credential_encryption_key: str = Field(default="")  # Fernet key, generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 1.4 Modelos Tortoise ORM

**Archivo nuevo:** `src/app/db/models.py`

### Tenant
```python
class Tenant(Model):
    id = fields.CharField(max_length=50, primary_key=True)  # "santa_lena"
    name = fields.CharField(max_length=200)
    active = fields.BooleanField(default=True)
    config = fields.JSONField(default={})  # overrides: llm_model, tts_voice, etc.
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "tenants"
```

### ApiKey
```python
class ApiKey(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="api_keys")
    key_hash = fields.CharField(max_length=64, unique=True)  # SHA-256
    key_prefix = fields.CharField(max_length=20)  # "sk_santa_" (para display)
    scopes = fields.JSONField(default=["converse", "knowledge", "conversations"])
    active = fields.BooleanField(default=True)
    last_used_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "api_keys"
```

### TenantCredentials
```python
class TenantCredentials(Model):
    tenant = fields.OneToOneField("models.Tenant", related_name="credentials", primary_key=True)
    whatsapp_access_token_enc = fields.TextField(default="")  # Fernet encrypted
    whatsapp_phone_number_id = fields.CharField(max_length=50, default="")
    whatsapp_verify_token = fields.CharField(max_length=100, default="")
    twilio_account_sid = fields.CharField(max_length=50, default="")
    twilio_auth_token_enc = fields.TextField(default="")  # Fernet encrypted
    twilio_phone_number = fields.CharField(max_length=20, default="")
    llm_api_key_enc = fields.TextField(default="")  # Fernet encrypted (override)
    llm_model = fields.CharField(max_length=100, default="")  # override
    tts_voice = fields.CharField(max_length=100, default="es-MX-DaliaNeural")

    class Meta:
        table = "tenant_credentials"
```

### KnowledgeDocument
```python
class KnowledgeDocument(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="documents")
    slug = fields.CharField(max_length=200)  # "menu/hamburguesas"
    doc_type = fields.CharField(max_length=50)  # menu, accion, negocio, promociones
    title = fields.CharField(max_length=300)
    description = fields.TextField(default="")
    body = fields.TextField()  # Markdown content
    tags = fields.JSONField(default=[])
    status = fields.CharField(max_length=20, default="stable")
    campos_requeridos = fields.JSONField(default=[])  # Para acciones
    campos_opcionales = fields.JSONField(default=[])  # Para acciones
    confirmacion_requerida = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "knowledge_documents"
        unique_together = [("tenant_id", "slug")]
```

### TenantPrompt
```python
class TenantPrompt(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="prompts")
    estilo = fields.CharField(max_length=50)  # "chat", "voz"
    system_prompt = fields.TextField()  # Prompt completo ensamblado
    tono = fields.TextField(default="")
    formato = fields.TextField(default="")
    vocabulario = fields.TextField(default="")
    ejemplos = fields.TextField(default="")
    restricciones = fields.TextField(default="")
    active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "tenant_prompts"
        unique_together = [("tenant_id", "estilo")]
```

### Conversation
```python
class Conversation(Model):
    id = fields.CharField(max_length=50, primary_key=True)  # "conv_abc123"
    tenant = fields.ForeignKeyField("models.Tenant", related_name="conversations")
    conversant_id = fields.CharField(max_length=200)  # Quien habla con el AI
    channel = fields.CharField(max_length=20, default="api")  # api, whatsapp, voice
    started_at = fields.DatetimeField(auto_now_add=True)
    last_message_at = fields.DatetimeField(auto_now=True)
    total_turns = fields.IntField(default=0)
    total_cost_usd = fields.FloatField(default=0.0)
    resolution_status = fields.CharField(max_length=20, default="active")
    metadata = fields.JSONField(default={})

    class Meta:
        table = "conversations"
```

### Message
```python
class Message(Model):
    id = fields.IntField(primary_key=True)
    conversation = fields.ForeignKeyField("models.Conversation", related_name="messages")
    tenant_id = fields.CharField(max_length=50)
    role = fields.CharField(max_length=20)  # user, assistant, tool
    content = fields.TextField()
    input_type = fields.CharField(max_length=10, default="text")  # text, audio
    audio_duration_ms = fields.IntField(default=0)
    transcription_ms = fields.IntField(default=0)
    tts_ms = fields.IntField(default=0)
    tokens_in = fields.IntField(default=0)
    tokens_out = fields.IntField(default=0)
    response_latency_ms = fields.IntField(default=0)
    model_used = fields.CharField(max_length=100, default="")
    tool_used = fields.CharField(max_length=50, null=True)
    cost_usd = fields.FloatField(default=0.0)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "messages"
```

### Event (billable operations)
```python
class Event(Model):
    id = fields.IntField(primary_key=True)
    tenant_id = fields.CharField(max_length=50, index=True)
    conversation_id = fields.CharField(max_length=50, null=True)
    event_type = fields.CharField(max_length=20)  # llm_call, stt, tts, whatsapp_msg, voice_call
    provider = fields.CharField(max_length=30)  # groq, openrouter, edge_tts, twilio
    model = fields.CharField(max_length=100, default="")
    input_tokens = fields.IntField(default=0)
    output_tokens = fields.IntField(default=0)
    audio_duration_s = fields.FloatField(default=0.0)
    characters = fields.IntField(default=0)
    latency_ms = fields.IntField(default=0)
    cost_usd = fields.FloatField(default=0.0)
    status = fields.CharField(max_length=20, default="success")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "events"
```

### UsageDaily
```python
class UsageDaily(Model):
    id = fields.IntField(primary_key=True)
    tenant_id = fields.CharField(max_length=50)
    date = fields.DateField()
    total_conversations = fields.IntField(default=0)
    text_requests = fields.IntField(default=0)
    audio_requests = fields.IntField(default=0)
    voice_call_minutes = fields.FloatField(default=0.0)
    tokens_in = fields.IntField(default=0)
    tokens_out = fields.IntField(default=0)
    tts_characters = fields.IntField(default=0)
    stt_seconds = fields.FloatField(default=0.0)
    total_cost_usd = fields.FloatField(default=0.0)

    class Meta:
        table = "usage_daily"
        unique_together = [("tenant_id", "date")]
```

---

## 1.5 Inicialización de Tortoise con FastAPI

**Archivo nuevo:** `src/app/db/__init__.py`

```python
TORTOISE_ORM = {
    "connections": {
        "default": settings.database_url,
    },
    "apps": {
        "models": {
            "models": ["src.app.db.models"],
            "default_connection": "default",
        }
    },
}
```

**Archivo:** `src/app/core/lifespan.py` (modificar)

Agregar en startup:
```python
from tortoise import Tortoise

await Tortoise.init(config=TORTOISE_ORM)
await Tortoise.generate_schemas()  # Solo para dev; en prod usar migraciones
```

En shutdown:
```python
await Tortoise.close_connections()
```

---

## 1.6 setup.sh

Agregar levantamiento de PostgreSQL:
```bash
if docker ps --format '{{.Names}}' | grep -q "prototipo-agente-postgres"; then
    echo ">> PostgreSQL ya está corriendo en Docker."
else
    echo ">> Levantando PostgreSQL en Docker..."
    docker compose up postgres -d --wait
fi
```

---

## 1.7 .env.example

Agregar:
```
DATABASE_URL=postgres://agente:dev_password_123@localhost:5432/agente_ia
CREDENTIAL_ENCRYPTION_KEY=  # Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 1.8 Tests

- Test de conexión a PostgreSQL
- Test de crear/leer un Tenant
- Test de crear/leer un KnowledgeDocument
- Test de relaciones (tenant.documents, tenant.api_keys)

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `docker-compose.yml` | Agregar servicio postgres |
| `pyproject.toml` | Agregar tortoise-orm, asyncpg, cryptography |
| `src/app/core/config.py` | Agregar database_url, credential_encryption_key |
| `src/app/db/__init__.py` | **NUEVO** — config Tortoise |
| `src/app/db/models.py` | **NUEVO** — todos los modelos |
| `src/app/core/lifespan.py` | Agregar init/close Tortoise |
| `setup.sh` | Agregar levantamiento PostgreSQL |
| `.env.example` | Agregar DATABASE_URL + encryption key |
| `tests/test_db.py` | **NUEVO** — tests de modelos |

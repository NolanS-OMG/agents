# Investigación: Multi-Tenant API — Proveedores, ORM, Métricas

## 1. Proveedores Cloud (sin GPU local)

### STT — Groq Whisper Large v3 Turbo GANADOR ($0.04/hora)

| Provider | Costo/min | Costo/hora | Español | Notas |
|----------|-----------|-----------|---------|-------|
| **Groq Whisper Turbo** | $0.00067 | **$0.04** | Excelente | Batch, no streaming |
| AssemblyAI Universal-2 | $0.0025 | $0.15 | Bueno | $50 crédito gratis |
| Deepgram Nova-3 | $0.0058 | $0.35 | Bueno | $200 crédito, streaming |
| AWS Transcribe | $0.006 | $0.36 | Bueno | 60 min/mes gratis |
| Google Speech | $0.006-0.009 | $0.36-0.54 | Bueno | 60 min/mes gratis |

**Decisión:** Groq Whisper Turbo como primario (4x más barato). Para streaming real-time → Deepgram.

**Costo real:** 1000 min/mes = **$0.67/mes**

### TTS — Edge-TTS (gratis) → AWS Polly Neural (producción)

| Provider | Costo/1M chars | Por respuesta (200 chars) | Español MX |
|----------|---------------|--------------------------|------------|
| **Edge-TTS** | $0 | $0 | Sí (DaliaNeural) |
| AWS Polly Standard | $4 | $0.0008 | Sí |
| AWS Polly Neural | $16 | $0.0032 | Sí |
| Google Cloud TTS | $16 | $0.0032 | Sí |
| ElevenLabs | ~$200 | $0.04 | Sí |

**Decisión:** Edge-TTS para MVP (gratis, calidad neural). AWS Polly Neural como fallback/producción ($3.20/mes para 10K respuestas).

### LLM — OpenRouter (0% markup) o AWS Bedrock

| Provider | Modelo | Input/1M tok | Output/1M tok | Function calling |
|----------|--------|-------------|---------------|-----------------|
| **AWS Bedrock** Nova Nano | Amazon | $0.03 | $0.06 | Sí |
| **Groq** Llama 3.1 8B | Meta | $0.05 | $0.08 | Sí |
| **OpenRouter** (cualquier modelo) | Varios | Varía | Varía | Sí |
| Together.ai gpt-oss-20B | OSS | $0.05 | $0.20 | Sí |
| Google Gemini 2.5 Flash Lite | Google | $0.10 | $0.40 | Sí |

**¿Existe un "Bedrock para modelos baratos"?**

| Plataforma | Modelos | Markup | Switching fácil |
|-----------|---------|--------|-----------------|
| AWS Bedrock | Anthropic, Meta, Mistral, Google, Nova | ~0% | Sí (cambiar model ID) |
| OpenRouter | 400+ modelos, 70+ providers | 0% hasta $25K/mes, luego 5.5% | Sí |
| Together.ai | ~50 OSS | ~0% | Sí |
| Fireworks.ai | ~50 modelos | ~0% | Sí |

**Decisión:** OpenRouter para desarrollo/MVP (0% markup hasta $25K/mes, ya lo tenemos integrado). Bedrock para producción si necesitamos SLA y AWS ecosystem.

### Costo total estimado (10 tenants, moderado)

| Componente | Mensual |
|-----------|---------|
| STT (Groq, 1000 min) | $0.67 |
| TTS (Edge-TTS) | $0 |
| LLM (OpenRouter, 50K calls) | ~$5-15 |
| Twilio (números + minutos) | ~$70 |
| **Total infraestructura IA** | **~$20/mes** |

---

## 2. ORM para PostgreSQL — Tortoise ORM GANADOR

### Comparativa

| ORM | ActiveRecord-like | Async nativo | Migraciones auto | Estabilidad |
|-----|-------------------|-------------|-------------------|-------------|
| **Tortoise ORM** | **9/10** | Sí | Sí (built-in) | Alpha |
| Piccolo ORM | 7/10 | Sí | Sí (built-in) | v1.x estable |
| SQLModel | 4/10 | Parcial | Alembic | 0.0.x beta |
| SQLAlchemy 2.0 | 3/10 | Wrapper | Alembic | Gold standard |
| Peewee | 6/10 | Bolted-on | Manual | Maduro |

### Comparación de sintaxis

**Rails ActiveRecord:**
```ruby
User.where(active: true).order(created_at: :desc).limit(10)
User.create!(name: "Nolan", email: "nolan@x.com")
user.posts
```

**Tortoise ORM (casi idéntico):**
```python
await User.filter(active=True).order_by("-created_at").limit(10)
await User.create(name="Nolan", email="nolan@x.com")
await user.posts.all()
```

**SQLAlchemy (verbose):**
```python
result = await session.exec(select(User).where(User.active == True).order_by(User.created_at.desc()).limit(10))
session.add(User(name="Nolan", email="nolan@x.com")); await session.commit()
```

### Tortoise ORM — modelo ejemplo

```python
from tortoise.models import Model
from tortoise import fields

class Tenant(Model):
    id = fields.CharField(max_length=50, primary_key=True)
    name = fields.CharField(max_length=200)
    active = fields.BooleanField(default=True)
    config = fields.JSONField(default={})
    created_at = fields.DatetimeField(auto_now_add=True)

    api_keys: fields.ReverseRelation["ApiKey"]
    conversations: fields.ReverseRelation["Conversation"]

class ApiKey(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="api_keys")
    key_hash = fields.CharField(max_length=64)
    key_prefix = fields.CharField(max_length=20)
    active = fields.BooleanField(default=True)
    last_used_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
```

### Migraciones
```bash
# Generar migración automática desde cambios en modelos
tortoise makemigrations --name "add_tenant_table"
# Aplicar
tortoise migrate
```

**Decisión:** Tortoise ORM. La sintaxis es la más cercana a ActiveRecord que existe en Python. Async nativo. Migraciones auto-detectadas. El riesgo "Alpha" es aceptable para un MVP — si falla, migrar a Piccolo (v1.x, sintaxis similar) es directo.

**Runner-up:** Piccolo ORM si Tortoise da problemas de estabilidad.

---

## 3. Métricas y Usage Tracking

### Por request (tabla `events`)

| Campo | Descripción |
|-------|-------------|
| tenant_id | Quién |
| conversation_id | Contexto |
| event_type | llm_call, stt, tts, whatsapp_msg, voice_call |
| provider | groq, openrouter, edge_tts, twilio |
| model | whisper-turbo, nova-nano, etc. |
| input_tokens / output_tokens | Para LLM |
| audio_duration_s | Para STT/TTS |
| characters | Para TTS |
| latency_ms | Cuánto tardó |
| cost_usd | Costo calculado |
| status | success, error, timeout |
| created_at | Cuándo |

### Por conversación

| Campo | Descripción |
|-------|-------------|
| total_turns | Mensajes ida y vuelta |
| total_cost_usd | Suma de todos los events |
| resolution_status | resolved, escalated, abandoned |
| channel | api, whatsapp, voice_call |
| duration_s | Duración total |
| tools_used | Qué herramientas se ejecutaron |
| voice_turns | Cuántos fueron por audio |

### Agregado diario (tabla `usage_daily`)

| Campo | Descripción |
|-------|-------------|
| tenant_id + date | PK compuesta |
| total_conversations | Volumen |
| text_requests / audio_requests | Por tipo |
| voice_call_minutes | Minutos Twilio |
| tokens_in / tokens_out | Consumo LLM |
| tts_characters | Consumo TTS |
| stt_seconds | Consumo STT |
| total_cost_usd | Costo total del día |

### Alertas (cuándo algo va mal)

| Métrica | Warning | Crítico |
|---------|---------|---------|
| Latencia p95 (voz) | >3s | >6s |
| Error rate | >2% | >5% |
| Resolution rate | <80% | <60% |
| Costo/conversación | >2x baseline | >4x baseline |

### Modelo de cobro recomendado (restaurantes)

**Flat fee + overage:**
```
$200-500/mes por restaurante
Incluye: 500 conversaciones o 300 minutos de voz
Overage: $0.50-1.00 por conversación extra
```

**Por qué:** Restaurantes odian costos variables. Flat fee es predecible. Tu costo real por conversación es ~$0.10-0.40, margen >60%.

---

## 4. Producción — PostgreSQL

### Docker para desarrollo (en setup.sh)

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agente_ia
      POSTGRES_USER: agente
      POSTGRES_PASSWORD: dev_password
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Producción

| Opción | Costo | Pros |
|--------|-------|------|
| Supabase (free tier) | $0 → $25/mes | PostgreSQL managed, API gratis, 500MB |
| Railway | $5/mes | Simple, auto-backup |
| Neon | $0 → $19/mes | Serverless PG, auto-scale |
| AWS RDS | $15+/mes | SLA, enterprise |
| Self-hosted (VPS) | $5/mes | Control total |

**Para MVP:** Supabase free tier o Railway. Para producción con 10 tenants: Neon o Railway ($20-25/mes).

---

## 5. Credential Encryption

```python
from cryptography.fernet import Fernet

# Master key en env: CREDENTIAL_ENCRYPTION_KEY
key = settings.credential_encryption_key

def encrypt(plaintext: str) -> str:
    return Fernet(key).encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    return Fernet(key).decrypt(ciphertext.encode()).decode()
```

**Qué se encripta:** WhatsApp tokens, Twilio auth tokens, LLM API keys de cada tenant.
**Dónde se guarda el master key:** Variable de entorno, nunca en código ni DB.

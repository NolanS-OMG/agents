from tortoise import fields
from tortoise.models import Model


class Tenant(Model):
    id = fields.CharField(max_length=50, primary_key=True)
    name = fields.CharField(max_length=200)
    active = fields.BooleanField(default=True)
    config = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "tenants"


class ApiKey(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="api_keys")
    key_hash = fields.CharField(max_length=64, unique=True)
    key_prefix = fields.CharField(max_length=20)
    scopes = fields.JSONField(default=lambda: ["converse", "knowledge", "conversations"])
    active = fields.BooleanField(default=True)
    last_used_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "api_keys"


class TenantCredentials(Model):
    tenant = fields.OneToOneField("models.Tenant", related_name="credentials", primary_key=True)
    whatsapp_access_token_enc = fields.TextField(default="")
    whatsapp_phone_number_id = fields.CharField(max_length=50, default="")
    whatsapp_verify_token = fields.CharField(max_length=100, default="")
    twilio_account_sid = fields.CharField(max_length=50, default="")
    twilio_auth_token_enc = fields.TextField(default="")
    twilio_phone_number = fields.CharField(max_length=20, default="")
    llm_api_key_enc = fields.TextField(default="")
    llm_model = fields.CharField(max_length=100, default="")
    tts_voice = fields.CharField(max_length=100, default="es-MX-DaliaNeural")

    class Meta:
        table = "tenant_credentials"


class KnowledgeDocument(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="documents")
    slug = fields.CharField(max_length=200)
    doc_type = fields.CharField(max_length=50)
    title = fields.CharField(max_length=300)
    description = fields.TextField(default="")
    file_path = fields.CharField(max_length=500)
    file_format = fields.CharField(max_length=10, default="md")
    file_hash = fields.CharField(max_length=64, default="")
    tags = fields.JSONField(default=list)
    status = fields.CharField(max_length=20, default="stable")
    campos_requeridos = fields.JSONField(default=list)
    campos_opcionales = fields.JSONField(default=list)
    confirmacion_requerida = fields.BooleanField(default=False)
    channels = fields.JSONField(default=lambda: ["web", "whatsapp", "call"])
    frontend_action = fields.BooleanField(default=False)
    frontend_tool = fields.CharField(max_length=100, default="")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "knowledge_documents"
        unique_together = [("tenant_id", "slug")]


class TenantPrompt(Model):
    id = fields.IntField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="prompts")
    estilo = fields.CharField(max_length=50)
    system_prompt = fields.TextField()
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


class Conversation(Model):
    id = fields.CharField(max_length=50, primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="conversations")
    conversant_id = fields.CharField(max_length=200)
    channel = fields.CharField(max_length=20, default="api")
    started_at = fields.DatetimeField(auto_now_add=True)
    last_message_at = fields.DatetimeField(auto_now=True)
    total_turns = fields.IntField(default=0)
    total_cost_usd = fields.FloatField(default=0.0)
    resolution_status = fields.CharField(max_length=20, default="active")
    metadata = fields.JSONField(default=dict)

    class Meta:
        table = "conversations"


class Message(Model):
    id = fields.IntField(primary_key=True)
    conversation = fields.ForeignKeyField("models.Conversation", related_name="messages")
    tenant_id = fields.CharField(max_length=50)
    role = fields.CharField(max_length=20)
    content = fields.TextField()
    input_type = fields.CharField(max_length=10, default="text")
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


class Event(Model):
    id = fields.IntField(primary_key=True)
    tenant_id = fields.CharField(max_length=50, index=True)
    conversation_id = fields.CharField(max_length=50, null=True)
    event_type = fields.CharField(max_length=20)
    provider = fields.CharField(max_length=30)
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


class ChatSession(Model):
    id = fields.UUIDField(primary_key=True)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="chat_sessions")
    session_id = fields.CharField(max_length=128, unique=True, index=True)
    ip_address = fields.CharField(max_length=45, null=True)
    user_agent = fields.TextField(null=True)
    referrer = fields.CharField(max_length=500, null=True)
    country = fields.CharField(max_length=2, null=True)
    region = fields.CharField(max_length=100, null=True)
    city = fields.CharField(max_length=100, null=True)
    device_type = fields.CharField(max_length=20, null=True)
    browser = fields.CharField(max_length=50, null=True)
    os = fields.CharField(max_length=50, null=True)
    screen_resolution = fields.CharField(max_length=20, null=True)
    language = fields.CharField(max_length=10, null=True)
    timezone = fields.CharField(max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_active = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "chat_sessions"


class ChatMessage(Model):
    id = fields.BigIntField(primary_key=True)
    session = fields.ForeignKeyField("models.ChatSession", related_name="messages")
    role = fields.CharField(max_length=20)
    content = fields.TextField()
    model_used = fields.CharField(max_length=100, null=True)
    tokens_used = fields.IntField(null=True)
    cost_usd = fields.DecimalField(max_digits=10, decimal_places=6, null=True)
    tool_calls = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"
        ordering = ["created_at"]

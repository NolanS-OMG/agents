from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "events" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "tenant_id" VARCHAR(50) NOT NULL,
    "conversation_id" VARCHAR(50),
    "event_type" VARCHAR(20) NOT NULL,
    "provider" VARCHAR(30) NOT NULL,
    "model" VARCHAR(100) NOT NULL  DEFAULT '',
    "input_tokens" INT NOT NULL  DEFAULT 0,
    "output_tokens" INT NOT NULL  DEFAULT 0,
    "audio_duration_s" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    "characters" INT NOT NULL  DEFAULT 0,
    "latency_ms" INT NOT NULL  DEFAULT 0,
    "cost_usd" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    "status" VARCHAR(20) NOT NULL  DEFAULT 'success',
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "idx_events_tenant__bdb739" ON "events" ("tenant_id");
CREATE TABLE IF NOT EXISTS "tenants" (
    "id" VARCHAR(50) NOT NULL  PRIMARY KEY,
    "name" VARCHAR(200) NOT NULL,
    "active" BOOL NOT NULL  DEFAULT True,
    "config" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "api_keys" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "key_hash" VARCHAR(64) NOT NULL UNIQUE,
    "key_prefix" VARCHAR(20) NOT NULL,
    "scopes" JSONB NOT NULL,
    "active" BOOL NOT NULL  DEFAULT True,
    "last_used_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "tenant_id" VARCHAR(50) NOT NULL REFERENCES "tenants" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "chat_sessions" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "session_id" VARCHAR(128) NOT NULL UNIQUE,
    "ip_address" VARCHAR(45),
    "user_agent" TEXT,
    "referrer" VARCHAR(500),
    "country" VARCHAR(2),
    "region" VARCHAR(100),
    "city" VARCHAR(100),
    "device_type" VARCHAR(20),
    "browser" VARCHAR(50),
    "os" VARCHAR(50),
    "screen_resolution" VARCHAR(20),
    "language" VARCHAR(10),
    "timezone" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "last_active" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "tenant_id" VARCHAR(50) NOT NULL REFERENCES "tenants" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_chat_sessio_session_a5c17d" ON "chat_sessions" ("session_id");
CREATE TABLE IF NOT EXISTS "chat_messages" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "role" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL,
    "model_used" VARCHAR(100),
    "tokens_used" INT,
    "cost_usd" DECIMAL(10,6),
    "tool_calls" JSONB,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "session_id" UUID NOT NULL REFERENCES "chat_sessions" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conversations" (
    "id" VARCHAR(50) NOT NULL  PRIMARY KEY,
    "conversant_id" VARCHAR(200) NOT NULL,
    "channel" VARCHAR(20) NOT NULL  DEFAULT 'api',
    "started_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "last_message_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "total_turns" INT NOT NULL  DEFAULT 0,
    "total_cost_usd" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    "resolution_status" VARCHAR(20) NOT NULL  DEFAULT 'active',
    "metadata" JSONB NOT NULL,
    "tenant_id" VARCHAR(50) NOT NULL REFERENCES "tenants" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "knowledge_documents" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "slug" VARCHAR(200) NOT NULL,
    "doc_type" VARCHAR(50) NOT NULL,
    "title" VARCHAR(300) NOT NULL,
    "description" TEXT NOT NULL,
    "file_path" VARCHAR(500) NOT NULL,
    "file_format" VARCHAR(10) NOT NULL  DEFAULT 'md',
    "file_hash" VARCHAR(64) NOT NULL  DEFAULT '',
    "tags" JSONB NOT NULL,
    "status" VARCHAR(20) NOT NULL  DEFAULT 'stable',
    "campos_requeridos" JSONB NOT NULL,
    "campos_opcionales" JSONB NOT NULL,
    "confirmacion_requerida" BOOL NOT NULL  DEFAULT False,
    "channels" JSONB NOT NULL,
    "frontend_action" BOOL NOT NULL  DEFAULT False,
    "frontend_tool" VARCHAR(100) NOT NULL  DEFAULT '',
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "tenant_id" VARCHAR(50) NOT NULL REFERENCES "tenants" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_knowledge_d_tenant__15ddfe" UNIQUE ("tenant_id", "slug")
);
CREATE TABLE IF NOT EXISTS "messages" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "tenant_id" VARCHAR(50) NOT NULL,
    "role" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL,
    "input_type" VARCHAR(10) NOT NULL  DEFAULT 'text',
    "audio_duration_ms" INT NOT NULL  DEFAULT 0,
    "transcription_ms" INT NOT NULL  DEFAULT 0,
    "tts_ms" INT NOT NULL  DEFAULT 0,
    "tokens_in" INT NOT NULL  DEFAULT 0,
    "tokens_out" INT NOT NULL  DEFAULT 0,
    "response_latency_ms" INT NOT NULL  DEFAULT 0,
    "model_used" VARCHAR(100) NOT NULL  DEFAULT '',
    "tool_used" VARCHAR(50),
    "cost_usd" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "conversation_id" VARCHAR(50) NOT NULL REFERENCES "conversations" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "tenant_credentials" (
    "whatsapp_access_token_enc" TEXT NOT NULL,
    "whatsapp_phone_number_id" VARCHAR(50) NOT NULL  DEFAULT '',
    "whatsapp_verify_token" VARCHAR(100) NOT NULL  DEFAULT '',
    "twilio_account_sid" VARCHAR(50) NOT NULL  DEFAULT '',
    "twilio_auth_token_enc" TEXT NOT NULL,
    "twilio_phone_number" VARCHAR(20) NOT NULL  DEFAULT '',
    "llm_api_key_enc" TEXT NOT NULL,
    "llm_model" VARCHAR(100) NOT NULL  DEFAULT '',
    "tts_voice" VARCHAR(100) NOT NULL  DEFAULT 'es-MX-DaliaNeural',
    "tenant_id" VARCHAR(50) NOT NULL  PRIMARY KEY REFERENCES "tenants" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "tenant_prompts" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "estilo" VARCHAR(50) NOT NULL,
    "system_prompt" TEXT NOT NULL,
    "tono" TEXT NOT NULL,
    "formato" TEXT NOT NULL,
    "vocabulario" TEXT NOT NULL,
    "ejemplos" TEXT NOT NULL,
    "restricciones" TEXT NOT NULL,
    "active" BOOL NOT NULL  DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "tenant_id" VARCHAR(50) NOT NULL REFERENCES "tenants" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_tenant_prom_tenant__3c7197" UNIQUE ("tenant_id", "estilo")
);
CREATE TABLE IF NOT EXISTS "usage_daily" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "tenant_id" VARCHAR(50) NOT NULL,
    "date" DATE NOT NULL,
    "total_conversations" INT NOT NULL  DEFAULT 0,
    "text_requests" INT NOT NULL  DEFAULT 0,
    "audio_requests" INT NOT NULL  DEFAULT 0,
    "voice_call_minutes" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    "tokens_in" INT NOT NULL  DEFAULT 0,
    "tokens_out" INT NOT NULL  DEFAULT 0,
    "tts_characters" INT NOT NULL  DEFAULT 0,
    "stt_seconds" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    "total_cost_usd" DOUBLE PRECISION NOT NULL  DEFAULT 0,
    CONSTRAINT "uid_usage_daily_tenant__1969bf" UNIQUE ("tenant_id", "date")
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """

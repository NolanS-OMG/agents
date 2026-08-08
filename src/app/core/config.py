from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "agente-ia"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    redis_url: str = Field(default="redis://redis:6379/0")
    tenant_id: str = Field(default="santa_lena")
    estilo: str = Field(default="chat")

    whatsapp_access_token: str = Field(default="")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_verify_token: str = Field(default="agente_ia_verify_2026")

    rate_limit_messages: int = Field(default=10)
    rate_limit_window: int = Field(default=60)

    history_compression_threshold: int = Field(default=16)
    history_keep_recent: int = Field(default=10)

    llm_provider: str = Field(default="openrouter")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="meta-llama/llama-3.3-70b-instruct:free")
    llm_base_url: str = Field(default="")
    llm_timeout: int = Field(default=30)
    llm_max_retries: int = Field(default=2)

    deepseek_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    openrouter_api_key: str = Field(default="")

    voice_enabled: bool = Field(default=False)
    whisper_model: str = Field(default="large-v3")
    whisper_device: str = Field(default="cuda")

    stt_model: str = Field(default="openai/whisper-large-v3")
    tts_model: str = Field(default="microsoft/mai-voice-2")
    tts_voice: str = Field(default="es-MX-Valeria:MAI-Voice-2")
    tts_speed: float = Field(default=1.15)

    twilio_enabled: bool = Field(default=False)
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_phone_number: str = Field(default="")
    vad_silence_ms: int = Field(default=700)

    database_url: str = Field(default="")
    credential_encryption_key: str = Field(default="")

    groq_api_key: str = Field(default="")


settings = Settings()

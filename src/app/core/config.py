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

    llm_provider: str = Field(default="openrouter")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="meta-llama/llama-3.3-70b-instruct:free")
    llm_base_url: str = Field(default="https://openrouter.ai/api/v1")
    llm_timeout: int = Field(default=30)
    llm_max_retries: int = Field(default=2)


settings = Settings()

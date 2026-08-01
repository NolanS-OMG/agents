from __future__ import annotations

from typing import TYPE_CHECKING

from src.app.core.config import settings
from src.app.services.llm.openai_compatible import OpenAICompatibleProvider

if TYPE_CHECKING:
    from httpx import AsyncClient

    from src.app.db.models import TenantCredentials
    from src.app.services.llm.base import LLMProvider


PROVIDER_CONFIGS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
}


def get_llm_provider(
    http_client: AsyncClient,
    tenant_creds: TenantCredentials | None = None,
    decrypted_api_key: str = "",
) -> LLMProvider:
    provider = settings.llm_provider
    api_key = decrypted_api_key or settings.llm_api_key
    model = settings.llm_model
    base_url = settings.llm_base_url

    if tenant_creds:
        if decrypted_api_key:
            api_key = decrypted_api_key
        if tenant_creds.llm_model:
            model = tenant_creds.llm_model

    if provider in PROVIDER_CONFIGS and not base_url:
        config = PROVIDER_CONFIGS[provider]
        base_url = config["base_url"]
        if not model:
            model = config["default_model"]

    if not base_url:
        base_url = "https://openrouter.ai/api/v1"

    return OpenAICompatibleProvider(
        http_client=http_client,
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_retries=settings.llm_max_retries,
    )

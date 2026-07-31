from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import AsyncClient

from src.app.core.config import settings
from src.app.services.llm.base import LLMProvider
from src.app.services.llm.openai_compatible import OpenAICompatibleProvider

if TYPE_CHECKING:
    from src.app.db.models import TenantCredentials


def get_llm_provider(
    http_client: AsyncClient,
    tenant_creds: TenantCredentials | None = None,
    decrypted_api_key: str = "",
) -> LLMProvider:
    api_key = decrypted_api_key or settings.llm_api_key
    model = settings.llm_model

    if tenant_creds:
        if decrypted_api_key:
            api_key = decrypted_api_key
        if tenant_creds.llm_model:
            model = tenant_creds.llm_model

    return OpenAICompatibleProvider(
        http_client=http_client,
        api_key=api_key,
        base_url=settings.llm_base_url,
        model=model,
        max_retries=settings.llm_max_retries,
    )

from httpx import AsyncClient

from src.app.core.config import settings
from src.app.services.llm.base import LLMProvider
from src.app.services.llm.openai_compatible import OpenAICompatibleProvider


def get_llm_provider(http_client: AsyncClient) -> LLMProvider:
    return OpenAICompatibleProvider(
        http_client=http_client,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_retries=settings.llm_max_retries,
    )

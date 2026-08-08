import logging

from httpx import AsyncClient

logger = logging.getLogger(__name__)

OPENROUTER_TTS_URL = "https://openrouter.ai/api/v1/audio/speech"
DEFAULT_MODEL = "microsoft/mai-voice-2"
DEFAULT_VOICE = "es-MX-Valeria:MAI-Voice-2"
DEFAULT_SPEED = 1.15


class OpenRouterTTS:
    def __init__(
        self,
        http_client: AsyncClient,
        api_key: str,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
    ) -> None:
        self._client = http_client
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._speed = speed

    async def synthesize(self, text: str, response_format: str = "mp3") -> bytes | None:
        payload: dict = {
            "model": self._model,
            "input": text,
            "voice": self._voice,
            "response_format": response_format,
        }
        if self._speed != 1.0:
            payload["speed"] = self._speed

        response = await self._client.post(
            OPENROUTER_TTS_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        if response.status_code != 200:
            logger.error(f"OpenRouter TTS error {response.status_code}: {response.text[:200]}")
            return None
        return response.content

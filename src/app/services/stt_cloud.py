import logging

from httpx import AsyncClient

logger = logging.getLogger(__name__)

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"


class GroqSTT:
    def __init__(self, http_client: AsyncClient, api_key: str) -> None:
        self._client = http_client
        self._api_key = api_key

    async def transcribe(
        self, audio_bytes: bytes, filename: str = "audio.ogg", language: str = "es"
    ) -> str:
        from httpx import HTTPStatusError

        response = await self._client.post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            files={"file": (filename, audio_bytes)},
            data={"model": GROQ_MODEL, "language": language},
            timeout=30.0,
        )
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"Groq STT error {response.status_code}: {response.text[:200]}")
            raise RuntimeError(f"STT transcription failed: {response.status_code}") from e
        return response.json()["text"]

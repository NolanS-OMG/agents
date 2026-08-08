import base64
import logging

from httpx import AsyncClient

logger = logging.getLogger(__name__)

OPENROUTER_STT_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
DEFAULT_MODEL = "openai/whisper-large-v3"


class OpenRouterSTT:
    def __init__(self, http_client: AsyncClient, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = http_client
        self._api_key = api_key
        self._model = model

    async def transcribe(
        self, audio_bytes: bytes, audio_format: str = "wav", language: str = "es"
    ) -> str:
        audio_b64 = base64.b64encode(audio_bytes).decode()
        response = await self._client.post(
            OPENROUTER_STT_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "input_audio": {"data": audio_b64, "format": audio_format},
                "language": language,
                "temperature": 0.0,
                "response_format": "json",
            },
            timeout=30.0,
        )
        if response.status_code != 200:
            logger.error(f"OpenRouter STT error {response.status_code}: {response.text[:200]}")
            return ""
        return response.json().get("text", "")

    async def transcribe_pcm(
        self, pcm_bytes: bytes, sample_rate: int = 16000, language: str = "es"
    ) -> str:
        """Transcribe raw PCM int16 mono by wrapping in WAV header."""
        import struct

        data_size = len(pcm_bytes)
        wav = bytearray()
        wav.extend(b"RIFF")
        wav.extend(struct.pack("<I", 36 + data_size))
        wav.extend(b"WAVE")
        wav.extend(b"fmt ")
        wav.extend(struct.pack("<I", 16))
        wav.extend(struct.pack("<H", 1))  # PCM
        wav.extend(struct.pack("<H", 1))  # mono
        wav.extend(struct.pack("<I", sample_rate))
        wav.extend(struct.pack("<I", sample_rate * 2))
        wav.extend(struct.pack("<H", 2))
        wav.extend(struct.pack("<H", 16))
        wav.extend(b"data")
        wav.extend(struct.pack("<I", data_size))
        wav.extend(pcm_bytes)

        return await self.transcribe(bytes(wav), audio_format="wav", language=language)

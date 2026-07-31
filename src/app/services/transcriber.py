import tempfile
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

HALLUCINATION_PATTERNS = [
    "thanks for watching",
    "thank you for watching",
    "subtítulos",
    "suscríbete",
    "subscribe",
]


class Transcriber:
    def __init__(self, model_size: str = "large-v3", device: str = "cuda") -> None:
        compute_type = "int8_float16" if device == "cuda" else "int8"
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_bytes: bytes, language: str = "es") -> str:
        """Transcribe from file bytes (OGG, MP3, WAV, etc.)."""
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            segments, _ = self._model.transcribe(tmp_path, language=language, beam_size=5)
            text = " ".join(s.text.strip() for s in segments).strip()
            return self._filter_hallucinations(text)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def transcribe_pcm(
        self, pcm_bytes: bytes, sample_rate: int = 16000, language: str = "es"
    ) -> str:
        """Transcribe from raw PCM int16 bytes (for real-time pipeline)."""
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(samples, language=language, beam_size=5)
        text = " ".join(s.text.strip() for s in segments).strip()
        return self._filter_hallucinations(text)

    @staticmethod
    def _filter_hallucinations(text: str) -> str:
        lower = text.lower()
        for pattern in HALLUCINATION_PATTERNS:
            if pattern in lower:
                return ""
        return text

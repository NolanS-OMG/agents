import tempfile
from pathlib import Path

from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size: str = "large-v3", device: str = "cuda") -> None:
        compute_type = "int8_float16" if device == "cuda" else "int8"
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_bytes: bytes, language: str = "es") -> str:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            segments, _ = self._model.transcribe(tmp_path, language=language, beam_size=5)
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

import tempfile
from pathlib import Path

import edge_tts


class Synthesizer:
    def __init__(self, voice: str = "es-MX-DaliaNeural") -> None:
        self._voice = voice

    async def synthesize(self, text: str) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        try:
            communicate = edge_tts.Communicate(text, self._voice)
            await communicate.save(tmp_path)
            return Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

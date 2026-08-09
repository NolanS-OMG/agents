from __future__ import annotations

import warnings
from collections import deque
from typing import TYPE_CHECKING

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

import numpy as np

if TYPE_CHECKING:
    import onnxruntime

_VAD_MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
_vad_session: "onnxruntime.InferenceSession | None" = None


def _get_vad_session() -> "onnxruntime.InferenceSession":
    """Load Silero VAD ONNX model (cached after first call)."""
    global _vad_session
    if _vad_session is not None:
        return _vad_session

    import urllib.request
    from pathlib import Path

    import onnxruntime

    cache_dir = Path("/tmp/silero_vad")
    cache_dir.mkdir(exist_ok=True)
    model_path = cache_dir / "silero_vad.onnx"

    if not model_path.exists():
        urllib.request.urlretrieve(_VAD_MODEL_URL, str(model_path))

    _vad_session = onnxruntime.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"]
    )
    return _vad_session


class SileroVAD:
    """Streaming Voice Activity Detection using Silero VAD v5 (ONNX)."""

    SAMPLE_RATE = 16000
    WINDOW_SAMPLES = 512

    def __init__(self, threshold: float = 0.5, sample_rate: int = 8000) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate

        self._session = _get_vad_session()

        # Silero v5 state: single tensor (2, 1, 128)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._sr = np.array([self.SAMPLE_RATE], dtype=np.int64)
        self._accumulator = np.array([], dtype=np.float32)

    def process_chunk(self, mulaw_bytes: bytes) -> float | None:
        """Feed mulaw 8kHz audio. Returns speech probability when a frame is ready."""
        pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
        pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, self.SAMPLE_RATE, None)
        samples = np.frombuffer(pcm_16k, dtype=np.int16).astype(np.float32) / 32768.0
        self._accumulator = np.concatenate([self._accumulator, samples])

        if len(self._accumulator) < self.WINDOW_SAMPLES:
            return None

        frame = self._accumulator[: self.WINDOW_SAMPLES]
        self._accumulator = self._accumulator[self.WINDOW_SAMPLES :]
        return self._run_inference(frame)

    def _run_inference(self, frame: np.ndarray) -> float:
        input_data = frame.reshape(1, self.WINDOW_SAMPLES)

        output, self._state = self._session.run(
            None,
            {"input": input_data, "state": self._state, "sr": self._sr},
        )
        return float(output[0][0])

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._accumulator = np.array([], dtype=np.float32)


class TurnDetector:
    """Detects end-of-turn using Silero VAD with pre-buffering."""

    def __init__(
        self,
        vad: SileroVAD,
        end_of_turn_ms: int = 700,
        min_speech_ms: int = 150,
        prefix_padding_ms: int = 300,
    ) -> None:
        self._vad = vad
        self._end_of_turn_ms = end_of_turn_ms
        self._min_speech_ms = min_speech_ms

        # Each Twilio chunk = 20ms
        self._chunk_ms = 20
        pre_chunks = max(1, prefix_padding_ms // self._chunk_ms)
        self._pre_buffer: deque[bytes] = deque(maxlen=pre_chunks)

        self._speech_buffer = bytearray()
        self._is_speaking = False
        self._speech_ms = 0
        self._silence_ms = 0

    _log_counter: int = 0

    def feed(self, mulaw_chunk: bytes) -> bytes | None:
        """Feed a 20ms mulaw chunk. Returns audio when end-of-turn detected."""
        prob = self._vad.process_chunk(mulaw_chunk)
        if prob is None:
            if self._is_speaking:
                self._speech_buffer.extend(mulaw_chunk)
            else:
                self._pre_buffer.append(mulaw_chunk)
            return None

        self._log_counter += 1
        if self._log_counter <= 5 or (prob > 0.1 and self._log_counter % 10 == 0):
            import logging
            logging.getLogger(__name__).info(
                f"[VAD] prob={prob:.4f} speaking={self._is_speaking} "
                f"speech_ms={self._speech_ms} silence_ms={self._silence_ms}"
            )

        is_speech = prob >= self._vad.threshold

        if not self._is_speaking:
            self._pre_buffer.append(mulaw_chunk)
            if is_speech:
                self._speech_ms += self._chunk_ms
                if self._speech_ms >= self._min_speech_ms:
                    self._is_speaking = True
                    for frame in self._pre_buffer:
                        self._speech_buffer.extend(frame)
            else:
                self._speech_ms = 0
        else:
            self._speech_buffer.extend(mulaw_chunk)
            if is_speech:
                self._silence_ms = 0
            else:
                self._silence_ms += self._chunk_ms
                if self._silence_ms >= self._end_of_turn_ms:
                    audio = bytes(self._speech_buffer)
                    self.reset_turn()
                    return audio

        return None

    def flush(self) -> bytes | None:
        """Force-flush whatever is in the buffer."""
        if self._speech_buffer:
            audio = bytes(self._speech_buffer)
            self.reset_turn()
            return audio
        return None

    def reset_turn(self) -> None:
        self._speech_buffer.clear()
        self._is_speaking = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._vad.reset()

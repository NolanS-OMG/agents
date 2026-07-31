from __future__ import annotations

import audioop
from collections import deque
from typing import TYPE_CHECKING

import numpy as np
from faster_whisper.vad import get_vad_model

if TYPE_CHECKING:
    import onnxruntime


class SileroVAD:
    """Streaming Voice Activity Detection using Silero VAD v6 (from faster-whisper)."""

    def __init__(self, threshold: float = 0.5, sample_rate: int = 8000) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate
        self._num_samples = 512
        self._context_size = 64

        model = get_vad_model()
        self._session: onnxruntime.InferenceSession = model.session

        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._context_size), dtype=np.float32)
        self._accumulator = np.array([], dtype=np.float32)

    def process_chunk(self, mulaw_bytes: bytes) -> float | None:
        """Feed mulaw 8kHz audio. Returns speech probability when a frame is ready."""
        pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
        pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
        samples = np.frombuffer(pcm_16k, dtype=np.int16).astype(np.float32) / 32768.0
        self._accumulator = np.concatenate([self._accumulator, samples])

        if len(self._accumulator) < self._num_samples:
            return None

        frame = self._accumulator[: self._num_samples]
        self._accumulator = self._accumulator[self._num_samples :]
        return self._run_inference(frame)

    def _run_inference(self, frame: np.ndarray) -> float:
        input_data = np.concatenate([self._context.flatten(), frame]).reshape(
            1, self._num_samples + self._context_size
        )

        self._context = frame[-self._context_size :].reshape(1, self._context_size)

        output, self._h, self._c = self._session.run(
            None,
            {"input": input_data, "h": self._h, "c": self._c},
        )
        return float(output[0])

    def reset(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._context_size), dtype=np.float32)
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

    def feed(self, mulaw_chunk: bytes) -> bytes | None:
        """Feed a 20ms mulaw chunk. Returns audio when end-of-turn detected."""
        prob = self._vad.process_chunk(mulaw_chunk)
        if prob is None:
            # Not enough samples for a VAD frame yet, buffer anyway
            if self._is_speaking:
                self._speech_buffer.extend(mulaw_chunk)
            else:
                self._pre_buffer.append(mulaw_chunk)
            return None

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

from pathlib import Path

import pytest

from src.app.services.transcriber import Transcriber

AUDIO_PATH = Path(__file__).parent.parent / "archives" / "AUDIO.mp3"
EXPECTED_TEXT = (
    "Esto es una prueba de transcripción, vamos a darnos cuenta si todo el flujo "
    "que estamos realizando funciona o no funciona, espero que los servicios "
    "funcionen en orden."
)

MIN_MATCH_RATIO = 0.75


def word_match_ratio(transcribed: str, expected: str) -> float:
    t_words = set(transcribed.lower().split())
    e_words = set(expected.lower().split())
    if not e_words:
        return 1.0 if not t_words else 0.0
    return len(t_words & e_words) / len(e_words)


@pytest.fixture(scope="module")
def transcriber() -> Transcriber:
    return Transcriber(model_size="base", device="cpu")


@pytest.mark.skipif(not AUDIO_PATH.exists(), reason="archives/AUDIO.mp3 not found")
def test_transcribe_audio(transcriber: Transcriber) -> None:
    audio_bytes = AUDIO_PATH.read_bytes()
    result = transcriber.transcribe(audio_bytes)

    assert result, "Transcription returned empty string"

    ratio = word_match_ratio(result, EXPECTED_TEXT)
    assert ratio >= MIN_MATCH_RATIO, (
        f"Word match ratio {ratio:.2%} below threshold {MIN_MATCH_RATIO:.0%}.\n"
        f"Expected: {EXPECTED_TEXT}\n"
        f"Got: {result}"
    )


@pytest.mark.skipif(not AUDIO_PATH.exists(), reason="archives/AUDIO.mp3 not found")
def test_transcribe_returns_string(transcriber: Transcriber) -> None:
    audio_bytes = AUDIO_PATH.read_bytes()
    result = transcriber.transcribe(audio_bytes)
    assert isinstance(result, str)


def test_transcribe_empty_audio(transcriber: Transcriber) -> None:
    with pytest.raises((ValueError, RuntimeError, OSError)):
        transcriber.transcribe(b"")

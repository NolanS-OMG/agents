import pytest

from src.app.services.synthesizer import Synthesizer


@pytest.fixture
def synthesizer() -> Synthesizer:
    return Synthesizer(voice="es-MX-DaliaNeural")


@pytest.mark.anyio
async def test_synthesize_returns_bytes(synthesizer: Synthesizer) -> None:
    audio = await synthesizer.synthesize("Hola, esto es una prueba.")
    assert isinstance(audio, bytes)
    assert len(audio) > 1000, "Audio output too small, likely empty"


@pytest.mark.anyio
async def test_synthesize_mp3_header(synthesizer: Synthesizer) -> None:
    audio = await synthesizer.synthesize("Prueba de formato.")
    # MP3: ID3 tag, or MPEG sync word (0xFF 0xFB/0xF3/0xF2)
    has_id3 = audio[:3] == b"ID3"
    has_sync = len(audio) >= 2 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0
    assert has_id3 or has_sync, "Output does not appear to be MP3 format"


@pytest.mark.anyio
async def test_synthesize_longer_text(synthesizer: Synthesizer) -> None:
    text = (
        "Bienvenido a nuestro servicio de atención al cliente. "
        "Estamos aquí para ayudarte con cualquier duda o pedido que tengas."
    )
    audio = await synthesizer.synthesize(text)
    assert len(audio) > 5000, "Longer text should produce larger audio"


@pytest.mark.anyio
async def test_synthesize_empty_text(synthesizer: Synthesizer) -> None:
    audio = await synthesizer.synthesize("")
    # Edge-TTS generates silence or very small output for empty text
    assert isinstance(audio, bytes)

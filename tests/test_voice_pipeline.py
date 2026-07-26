from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.services.agent_router import AgentResult
from src.app.services.voice_pipeline import VoicePipeline

AUDIO_PATH = Path(__file__).parent.parent / "archives" / "AUDIO.mp3"


def make_mock_transcriber(return_text: str = "hola mundo") -> MagicMock:
    t = MagicMock()
    t.transcribe.return_value = return_text
    return t


def make_mock_synthesizer(return_bytes: bytes = b"\xff\xf3audio") -> AsyncMock:
    s = AsyncMock()
    s.synthesize.return_value = return_bytes
    return s


def make_mock_agent(response: str = "Respuesta del bot") -> AsyncMock:
    agent = AsyncMock()
    agent.run.return_value = AgentResult(
        response=response,
        tool_used=None,
        messages=[],
        usage={},
    )
    return agent


@pytest.mark.anyio
async def test_audio_to_response_text_only() -> None:
    transcriber = make_mock_transcriber("quiero hacer un pedido")
    pipeline = VoicePipeline(transcriber=transcriber, synthesizer=None)
    agent = make_mock_agent("Claro, qué deseas ordenar?")

    result = await pipeline.audio_to_response(
        audio_bytes=b"fake_audio",
        agent=agent,
        respond_with_audio=False,
    )

    assert result.transcription == "quiero hacer un pedido"
    assert result.agent_result.response == "Claro, qué deseas ordenar?"
    assert result.audio_response is None
    agent.run.assert_called_once_with(user_message="quiero hacer un pedido", history=None)


@pytest.mark.anyio
async def test_audio_to_response_with_audio() -> None:
    transcriber = make_mock_transcriber("hola")
    synthesizer = make_mock_synthesizer(b"\xff\xf3synthesized")
    pipeline = VoicePipeline(transcriber=transcriber, synthesizer=synthesizer)
    agent = make_mock_agent("Hola, en qué puedo ayudarte?")

    result = await pipeline.audio_to_response(
        audio_bytes=b"fake_audio",
        agent=agent,
        respond_with_audio=True,
    )

    assert result.transcription == "hola"
    assert result.audio_response == b"\xff\xf3synthesized"
    synthesizer.synthesize.assert_called_once_with("Hola, en qué puedo ayudarte?")


@pytest.mark.anyio
async def test_empty_transcription_returns_fallback() -> None:
    transcriber = make_mock_transcriber("   ")
    pipeline = VoicePipeline(transcriber=transcriber, synthesizer=None)
    agent = make_mock_agent()

    result = await pipeline.audio_to_response(audio_bytes=b"silence", agent=agent)

    assert "No pude entender" in result.agent_result.response
    agent.run.assert_not_called()


@pytest.mark.skipif(not AUDIO_PATH.exists(), reason="archives/AUDIO.mp3 not found")
def test_transcribe_real_audio() -> None:
    from src.app.services.transcriber import Transcriber

    transcriber = Transcriber(model_size="base", device="cpu")
    pipeline = VoicePipeline(transcriber=transcriber)

    text = pipeline.transcribe(AUDIO_PATH.read_bytes())
    assert "prueba" in text.lower()
    assert "transcripción" in text.lower() or "transcripcion" in text.lower()

import logging

from src.app.services.agent_router import AgentResult, AgentRouter
from src.app.services.synthesizer import Synthesizer
from src.app.services.transcriber import Transcriber

logger = logging.getLogger(__name__)


class VoiceResult:
    def __init__(
        self,
        transcription: str,
        agent_result: AgentResult,
        audio_response: bytes | None = None,
    ) -> None:
        self.transcription = transcription
        self.agent_result = agent_result
        self.audio_response = audio_response


class VoicePipeline:
    def __init__(
        self,
        transcriber: Transcriber,
        synthesizer: Synthesizer | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._synthesizer = synthesizer

    def transcribe(self, audio_bytes: bytes, language: str = "es") -> str:
        return self._transcriber.transcribe(audio_bytes, language=language)

    def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000, language: str = "es") -> str:
        return self._transcriber.transcribe_pcm(pcm_bytes, sample_rate=sample_rate, language=language)

    async def synthesize(self, text: str) -> bytes | None:
        if not self._synthesizer:
            return None
        return await self._synthesizer.synthesize(text)

    async def audio_to_response(
        self,
        audio_bytes: bytes,
        agent: AgentRouter,
        history: list | None = None,
        respond_with_audio: bool = False,
        language: str = "es",
    ) -> VoiceResult:
        text = self.transcribe(audio_bytes, language=language)
        logger.info(f"[Voice] Transcribed: {text[:80]}")

        if not text.strip():
            fallback = AgentResult(
                response="No pude entender el audio. ¿Puedes repetir?",
                tool_used=None,
                messages=[],
                usage={},
            )
            return VoiceResult(transcription="", agent_result=fallback)

        result = await agent.run(user_message=text, history=history)

        audio_response = None
        if respond_with_audio and self._synthesizer:
            audio_response = await self._synthesizer.synthesize(result.response)

        return VoiceResult(
            transcription=text,
            agent_result=result,
            audio_response=audio_response,
        )

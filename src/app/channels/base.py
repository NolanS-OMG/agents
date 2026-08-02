from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    CALL = "call"


class IncomingMessage(BaseModel):
    channel: str
    sender_id: str
    message: str
    message_id: str = ""
    media_id: str = ""
    media_type: str = ""
    raw: dict[str, Any] = {}

    @property
    def is_audio(self) -> bool:
        return self.media_type == "audio"


class OutgoingMessage(BaseModel):
    channel: str
    recipient_id: str
    message: str
    audio_bytes: bytes | None = None
    audio_mime: str = "audio/mpeg"


class ChannelAdapter(ABC):
    @property
    @abstractmethod
    def channel_name(self) -> str: ...

    @abstractmethod
    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None: ...

    @abstractmethod
    async def send_reply(self, message: OutgoingMessage) -> tuple[bool, int]: ...

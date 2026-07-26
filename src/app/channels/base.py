from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class IncomingMessage(BaseModel):
    channel: str
    sender_id: str
    message: str
    message_id: str = ""
    raw: dict[str, Any] = {}


class OutgoingMessage(BaseModel):
    channel: str
    recipient_id: str
    message: str


class ChannelAdapter(ABC):
    @property
    @abstractmethod
    def channel_name(self) -> str: ...

    @abstractmethod
    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None: ...

    @abstractmethod
    async def send_reply(self, message: OutgoingMessage) -> tuple[bool, int]: ...

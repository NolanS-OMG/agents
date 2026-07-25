from typing import Any

from httpx import AsyncClient

from src.app.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage

GRAPH_API_URL = "https://graph.facebook.com/v25.0"


class WhatsAppAdapter(ChannelAdapter):
    def __init__(self, access_token: str, phone_number_id: str, http_client: AsyncClient) -> None:
        self._token = access_token
        self._phone_id = phone_number_id
        self._client = http_client

    @property
    def channel_name(self) -> str:
        return "whatsapp"

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None:
        try:
            entry = payload["entry"][0]
            changes = entry["changes"][0]["value"]
            messages = changes.get("messages")
            if not messages:
                return None
            msg = messages[0]
            if msg.get("type") != "text":
                return None
            return IncomingMessage(
                channel="whatsapp",
                sender_id=msg["from"],
                message=msg["text"]["body"],
                raw=payload,
            )
        except (KeyError, IndexError):
            return None

    async def send_reply(self, message: OutgoingMessage) -> bool:
        response = await self._client.post(
            f"{GRAPH_API_URL}/{self._phone_id}/messages",
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": message.recipient_id,
                "type": "text",
                "text": {"preview_url": False, "body": message.message},
            },
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        return response.status_code == 200

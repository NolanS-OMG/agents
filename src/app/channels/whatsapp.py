import asyncio
import logging
import time
from typing import Any

from httpx import AsyncClient

from src.app.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage

logger = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v25.0"
SEND_MAX_RETRIES = 3


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
            msg_type = msg.get("type")
            sender = self._normalize_mx_number(msg["from"])

            if msg_type == "text":
                return IncomingMessage(
                    channel="whatsapp",
                    sender_id=sender,
                    message=msg["text"]["body"],
                    message_id=msg.get("id", ""),
                    raw=payload,
                )

            if msg_type == "audio":
                audio_info = msg.get("audio", {})
                return IncomingMessage(
                    channel="whatsapp",
                    sender_id=sender,
                    message="",
                    message_id=msg.get("id", ""),
                    media_id=audio_info.get("id", ""),
                    media_type="audio",
                    raw=payload,
                )

            return None
        except (KeyError, IndexError):
            return None

    @staticmethod
    def _normalize_mx_number(phone: str) -> str:
        if phone.startswith("521") and len(phone) == 13:
            return "52" + phone[3:]
        return phone

    async def download_media(self, media_id: str) -> bytes | None:
        try:
            resp = await self._client.get(
                f"{GRAPH_API_URL}/{media_id}",
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if resp.status_code != 200:
                logger.error(f"[WA] Error obteniendo URL media: {resp.status_code}")
                return None
            url = resp.json().get("url")
            if not url:
                return None
            media_resp = await self._client.get(
                url, headers={"Authorization": f"Bearer {self._token}"}
            )
            if media_resp.status_code != 200:
                logger.error(f"[WA] Error descargando media: {media_resp.status_code}")
                return None
            return media_resp.content
        except Exception as e:
            logger.error(f"[WA] Error en download_media: {e}")
            return None

    async def send_audio(self, recipient_id: str, audio_bytes: bytes) -> tuple[bool, int]:
        t0 = time.time()
        upload_resp = await self._client.post(
            f"{GRAPH_API_URL}/{self._phone_id}/media",
            headers={"Authorization": f"Bearer {self._token}"},
            files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
            data={"messaging_product": "whatsapp", "type": "audio/mpeg"},
        )
        if upload_resp.status_code != 200:
            send_ms = int((time.time() - t0) * 1000)
            logger.error(f"[WA] Error subiendo audio: {upload_resp.status_code}")
            return False, send_ms

        media_id = upload_resp.json().get("id")
        resp = await self._client.post(
            f"{GRAPH_API_URL}/{self._phone_id}/messages",
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient_id,
                "type": "audio",
                "audio": {"id": media_id},
            },
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        send_ms = int((time.time() - t0) * 1000)
        if resp.status_code == 200:
            return True, send_ms
        logger.error(f"[WA] Error enviando audio: {resp.status_code}")
        return False, send_ms

    async def send_reply(self, message: OutgoingMessage) -> tuple[bool, int]:
        t0 = time.time()

        for attempt in range(SEND_MAX_RETRIES):
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

            if response.status_code == 200:
                send_ms = int((time.time() - t0) * 1000)
                logger.info(f"[WA] Mensaje enviado OK a {message.recipient_id} ({send_ms}ms)")
                return True, send_ms

            if response.status_code >= 500 and attempt < SEND_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                continue

            break

        send_ms = int((time.time() - t0) * 1000)
        logger.error(f"[WA] Error enviando mensaje: {response.status_code} {response.text}")
        return False, send_ms

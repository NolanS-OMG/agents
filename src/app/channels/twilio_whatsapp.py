from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx import AsyncClient

from src.app.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/Accounts"


class TwilioWhatsAppAdapter(ChannelAdapter):
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        http_client: AsyncClient,
    ) -> None:
        self._sid = account_sid
        self._token = auth_token
        self._from = f"whatsapp:{from_number}"
        self._client = http_client
        self._auth = (account_sid, auth_token)

    @property
    def channel_name(self) -> str:
        return "twilio_whatsapp"

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None:
        body = payload.get("Body", "")
        from_raw = payload.get("From", "")
        sender = from_raw.removeprefix("whatsapp:").lstrip("+")
        message_sid = payload.get("MessageSid", "")

        if not sender or (not body and int(payload.get("NumMedia", "0")) == 0):
            return None

        num_media = int(payload.get("NumMedia", "0"))
        media_id = ""
        media_type = ""
        if num_media > 0:
            media_id = payload.get("MediaUrl0", "")
            content_type = payload.get("MediaContentType0", "")
            media_type = "audio" if "audio" in content_type else content_type

        return IncomingMessage(
            channel="twilio_whatsapp",
            sender_id=sender,
            message=body,
            message_id=message_sid,
            media_id=media_id,
            media_type=media_type,
        )

    async def send_reply(self, message: OutgoingMessage) -> tuple[bool, int]:
        url = f"{TWILIO_API_BASE}/{self._sid}/Messages.json"
        to = f"whatsapp:+{message.recipient_id.lstrip('+')}"

        start = time.time()
        try:
            resp = await self._client.post(
                url,
                auth=self._auth,
                data={"From": self._from, "To": to, "Body": message.message},
                timeout=15.0,
            )
            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code >= 400:
                logger.error(f"[TwilioWA] Send failed {resp.status_code}: {resp.text[:200]}")
                return False, latency_ms
            return True, latency_ms
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"[TwilioWA] Send error: {e}")
            return False, latency_ms

    async def download_media(self, media_url: str) -> bytes | None:
        if not media_url:
            return None
        try:
            resp = await self._client.get(media_url, auth=self._auth, timeout=30.0)
            if resp.status_code == 200:
                return resp.content
            logger.error(f"[TwilioWA] Media download failed: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"[TwilioWA] Media download error: {e}")
            return None


def validate_twilio_signature(
    url: str,
    post_params: dict[str, str],
    signature: str,
    auth_token: str,
) -> bool:
    data = url
    for key in sorted(post_params.keys()):
        data += key + post_params[key]

    expected = base64.b64encode(
        hmac.new(
            auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    return hmac.compare_digest(expected, signature)

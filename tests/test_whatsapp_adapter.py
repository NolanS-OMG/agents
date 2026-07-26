from unittest.mock import AsyncMock

import pytest

from src.app.channels.whatsapp import WhatsAppAdapter


@pytest.fixture
def adapter() -> WhatsAppAdapter:
    return WhatsAppAdapter(
        access_token="test_token",
        phone_number_id="123456",
        http_client=AsyncMock(),
    )


def test_parse_audio_message(adapter: WhatsAppAdapter) -> None:
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5215551234567",
                        "id": "wamid.abc123",
                        "type": "audio",
                        "audio": {
                            "id": "media_id_999",
                            "mime_type": "audio/ogg; codecs=opus",
                        },
                    }]
                }
            }]
        }]
    }

    incoming = adapter.parse_incoming(payload)

    assert incoming is not None
    assert incoming.is_audio
    assert incoming.media_id == "media_id_999"
    assert incoming.media_type == "audio"
    assert incoming.sender_id == "525551234567"
    assert incoming.message == ""


def test_parse_text_message_still_works(adapter: WhatsAppAdapter) -> None:
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "525551234567",
                        "id": "wamid.xyz",
                        "type": "text",
                        "text": {"body": "Hola"},
                    }]
                }
            }]
        }]
    }

    incoming = adapter.parse_incoming(payload)

    assert incoming is not None
    assert not incoming.is_audio
    assert incoming.message == "Hola"
    assert incoming.media_id == ""


def test_parse_unsupported_type_returns_none(adapter: WhatsAppAdapter) -> None:
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "525551234567",
                        "id": "wamid.xyz",
                        "type": "image",
                        "image": {"id": "img_123"},
                    }]
                }
            }]
        }]
    }

    assert adapter.parse_incoming(payload) is None


@pytest.mark.anyio
async def test_download_media_success() -> None:
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        AsyncMock(status_code=200, json=lambda: {"url": "https://cdn.meta.com/audio.ogg"}),
        AsyncMock(status_code=200, content=b"audio_bytes_here"),
    ]

    adapter = WhatsAppAdapter(
        access_token="tok", phone_number_id="123", http_client=mock_client
    )

    result = await adapter.download_media("media_999")

    assert result == b"audio_bytes_here"
    assert mock_client.get.call_count == 2


@pytest.mark.anyio
async def test_download_media_failure_returns_none() -> None:
    mock_client = AsyncMock()
    mock_client.get.return_value = AsyncMock(status_code=404)

    adapter = WhatsAppAdapter(
        access_token="tok", phone_number_id="123", http_client=mock_client
    )

    result = await adapter.download_media("bad_id")

    assert result is None

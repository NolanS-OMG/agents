from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from redis.asyncio import Redis

from src.app.services.llm.base import LLMMessage, LLMProvider

SESSION_TTL = 3600
MAX_HISTORY_MESSAGES = 20

SUMMARY_PROMPT = (
    "Resume la siguiente conversación entre un cliente y un asistente en máximo 2 oraciones. "
    "Incluye: qué pidió el cliente, qué se le respondió, y datos relevantes (nombre, teléfono, etc). "
    "Responde SOLO con el resumen, nada más."
)

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(
        self, redis: Any, llm: LLMProvider | None = None, tenant_id: str | None = None
    ) -> None:
        self._redis: Redis = redis
        self._llm = llm
        self._tenant_id = tenant_id

    async def get_history(self, session_id: str) -> list[LLMMessage]:
        key = f"session:{session_id}:history"
        summary_key = f"session:{session_id}:summary"

        messages: list[LLMMessage] = []

        summary = await self._redis.get(summary_key)
        if summary:
            messages.append(
                LLMMessage(
                    role="system",
                    content=f"[Resumen de conversación anterior]: {summary.decode() if isinstance(summary, bytes) else summary}",
                )
            )

        raw = await self._redis.get(key)
        if raw:
            messages_data: list[dict[str, str]] = json.loads(raw)
            messages.extend([LLMMessage(**m) for m in messages_data])

        return messages

    async def save_history(
        self,
        session_id: str,
        messages: list[LLMMessage],
        compression_threshold: int = 16,
        keep_recent: int = 10,
        model_used: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        key = f"session:{session_id}:history"

        if len(messages) > compression_threshold and self._llm:
            old_msgs = messages[:-keep_recent]
            recent_msgs = messages[-keep_recent:]
            await self._compress_and_save(session_id, old_msgs)
            data = json.dumps([m.model_dump() for m in recent_msgs])
        else:
            trimmed = messages[-MAX_HISTORY_MESSAGES:]
            data = json.dumps([m.model_dump() for m in trimmed])

        await self._redis.set(key, data, ex=SESSION_TTL)

        if self._tenant_id:
            logger.info(f"[Session] Persisting {len(messages)} messages to DB for session {session_id}")
            await self._persist_to_db(session_id, messages, model_used, metadata)

    async def _compress_and_save(self, session_id: str, old_msgs: list[LLMMessage]) -> None:
        summary_key = f"session:{session_id}:summary"

        existing_summary = await self._redis.get(summary_key)
        conversation = ""
        if existing_summary:
            s = (
                existing_summary.decode()
                if isinstance(existing_summary, bytes)
                else existing_summary
            )
            conversation += f"[Contexto previo]: {s}\n\n"

        for msg in old_msgs:
            role = "Cliente" if msg.role == "user" else "Asistente"
            if msg.content and msg.role in ("user", "assistant"):
                conversation += f"{role}: {msg.content}\n"

        if not conversation.strip():
            return

        if not self._llm:
            return

        try:
            response = await self._llm.complete(
                messages=[
                    LLMMessage(role="system", content=SUMMARY_PROMPT),
                    LLMMessage(role="user", content=conversation),
                ],
                temperature=0.1,
            )
            if response.content:
                await self._redis.set(summary_key, response.content, ex=SESSION_TTL)
                logger.info(f"[Session] Historial comprimido para {session_id}")
        except Exception as e:
            logger.warning(f"[Session] Error comprimiendo historial: {e}")

    async def mark_needs_human(self, session_id: str) -> None:
        key = f"session:{session_id}:needs_human"
        await self._redis.set(key, "1", ex=SESSION_TTL)

    async def is_needs_human(self, session_id: str) -> bool:
        key = f"session:{session_id}:needs_human"
        return await self._redis.exists(key) > 0

    async def release_human(self, session_id: str) -> None:
        key = f"session:{session_id}:needs_human"
        await self._redis.delete(key)

    async def _persist_to_db(
        self,
        session_id: str,
        messages: list[LLMMessage],
        model_used: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        from src.app.db.models import ChatMessage, ChatSession, Tenant

        tenant = await Tenant.get(id=self._tenant_id)

        session, created = await ChatSession.get_or_create(
            session_id=session_id, defaults={"tenant": tenant}
        )

        if not created:
            session.last_active = datetime.utcnow()
            await session.save()

        if metadata and created:
            session.ip_address = metadata.get("ip_address")
            session.user_agent = metadata.get("user_agent")
            session.referrer = metadata.get("referrer")
            session.country = metadata.get("country")
            session.region = metadata.get("region")
            session.city = metadata.get("city")
            session.device_type = metadata.get("device_type")
            session.browser = metadata.get("browser")
            session.os = metadata.get("os")
            session.screen_resolution = metadata.get("screen_resolution")
            session.language = metadata.get("language")
            session.timezone = metadata.get("timezone")
            await session.save()

        existing_count = await ChatMessage.filter(session=session).count()

        for idx, msg in enumerate(messages):
            if msg.role in ("user", "assistant") and idx >= existing_count:
                await ChatMessage.create(
                    session=session,
                    role=msg.role,
                    content=msg.content or "",
                    model_used=model_used if msg.role == "assistant" else None,
                    tool_calls=getattr(msg, "tool_calls", None),
                )

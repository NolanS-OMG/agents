from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from src.app.api.deps import CurrentTenant
from src.app.db.models import ChatMessage, ChatSession

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/sessions/stats")
async def get_session_stats(tenant_ctx: CurrentTenant) -> dict:
    """Stats de sesiones por tenant"""
    total_sessions = await ChatSession.filter(tenant_id=tenant_ctx.tenant_id).count()
    total_messages = await ChatMessage.filter(
        session__tenant_id=tenant_ctx.tenant_id
    ).count()

    yesterday = datetime.utcnow() - timedelta(days=1)
    active_sessions = await ChatSession.filter(
        tenant_id=tenant_ctx.tenant_id, last_active__gte=yesterday
    ).count()

    week_ago = datetime.utcnow() - timedelta(days=7)
    sessions_7d = await ChatSession.filter(
        tenant_id=tenant_ctx.tenant_id, created_at__gte=week_ago
    ).count()

    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "active_sessions_24h": active_sessions,
        "sessions_last_7_days": sessions_7d,
    }


@router.get("/sessions/{session_id}/history")
async def get_full_history(session_id: str, tenant_ctx: CurrentTenant) -> dict:
    """Ver TODO el historial de una sesión (no solo últimos 20)"""
    session = await ChatSession.get(
        session_id=session_id, tenant__id=tenant_ctx.tenant_id
    )
    messages = await ChatMessage.filter(session=session).order_by("created_at")

    return {
        "session_id": session_id,
        "created_at": session.created_at,
        "last_active": session.last_active,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "country": session.country,
        "city": session.city,
        "device_type": session.device_type,
        "browser": session.browser,
        "os": session.os,
        "language": session.language,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
                "model_used": m.model_used,
                "tokens_used": m.tokens_used,
            }
            for m in messages
        ],
    }


@router.get("/sessions")
async def list_sessions(
    tenant_ctx: CurrentTenant,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Lista sesiones recientes con paginación"""
    sessions = (
        await ChatSession.filter(tenant__id=tenant_ctx.tenant_id)
        .order_by("-last_active")
        .limit(limit)
        .offset(offset)
        .prefetch_related("messages")
    )

    total = await ChatSession.filter(tenant__id=tenant_ctx.tenant_id).count()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sessions": [
            {
                "session_id": s.session_id,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "messages_count": len(s.messages),
                "ip_address": s.ip_address,
                "country": s.country,
                "city": s.city,
                "device_type": s.device_type,
                "browser": s.browser,
            }
            for s in sessions
        ],
    }

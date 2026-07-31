import asyncio
import hashlib
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.app.db.models import ApiKey

logger = logging.getLogger(__name__)

EXCLUDED_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/webhook/whatsapp",
    "/incoming-call",
    "/ws/",
    "/api/v1/sessions/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return JSONResponse({"detail": "API key required"}, status_code=401)

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            record = await ApiKey.get_or_none(
                key_hash=key_hash, active=True
            ).select_related("tenant")
        except Exception:
            return JSONResponse({"detail": "Auth service unavailable"}, status_code=503)

        if not record or not record.tenant.active:
            return JSONResponse({"detail": "Invalid API key"}, status_code=401)

        request.state.tenant_id = record.tenant.id
        request.state.tenant_name = record.tenant.name
        request.state.api_key_scopes = record.scopes

        task = asyncio.create_task(self._update_last_used(record))
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        return await call_next(request)

    @staticmethod
    async def _update_last_used(record: ApiKey) -> None:
        from datetime import UTC, datetime

        record.last_used_at = datetime.now(UTC)
        await record.save(update_fields=["last_used_at"])

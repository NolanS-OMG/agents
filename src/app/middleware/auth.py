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
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/webhook/whatsapp",
    "/webhook/twilio-whatsapp",
    "/incoming-call",
    "/ws/",
    "/api/v1/sessions/",
    "/static/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return JSONResponse(
                {"error": "missing_api_key", "message": "API key required"}, status_code=401
            )

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            record = await ApiKey.get_or_none(key_hash=key_hash, active=True).select_related(
                "tenant"
            )
        except Exception as e:
            logger.error(f"Auth DB query failed: {e}", exc_info=True)
            return JSONResponse(
                {"error": "service_unavailable", "message": "Auth service unavailable"},
                status_code=503,
            )

        if not record or not record.tenant.active:
            return JSONResponse(
                {"error": "invalid_api_key", "message": "Invalid API key"}, status_code=401
            )

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

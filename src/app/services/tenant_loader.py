import json
import logging
from typing import Any

from redis.asyncio import Redis

from src.app.db.models import KnowledgeDocument, TenantPrompt
from src.app.services.tenant import TenantConfig

logger = logging.getLogger(__name__)

CACHE_TTL = 300


async def load_tenant_from_db(tenant_id: str, redis: Redis | None = None) -> TenantConfig | None:
    if redis:
        cached = await redis.get(f"tenant_config:{tenant_id}")
        if cached:
            logger.debug(f"Tenant {tenant_id} loaded from cache")
            data = json.loads(cached)
            return _deserialize_tenant_config(data)

    try:
        docs = await KnowledgeDocument.filter(tenant_id=tenant_id, status="stable").all()
        prompts = await TenantPrompt.filter(tenant_id=tenant_id, active=True).all()
    except Exception as e:
        logger.warning(f"Failed to load tenant {tenant_id} from DB: {e}")
        return None

    if not docs:
        return None

    config = TenantConfig(tenant_id=tenant_id, docs=docs, prompts=prompts)

    if redis:
        try:
            serialized = _serialize_tenant_config(config)
            await redis.setex(f"tenant_config:{tenant_id}", CACHE_TTL, json.dumps(serialized))
        except Exception as e:
            logger.warning(f"Failed to cache tenant {tenant_id}: {e}")

    return config


async def invalidate_tenant_cache(tenant_id: str, redis: Redis) -> None:
    await redis.delete(f"tenant_config:{tenant_id}")


async def load_tenant_async(tenant_id: str, redis: Redis | None = None) -> TenantConfig:
    config = await load_tenant_from_db(tenant_id, redis)
    if config:
        return config
    return TenantConfig.from_filesystem(tenant_id)


def _serialize_tenant_config(config: TenantConfig) -> dict:
    return {
        "tenant_id": config.tenant_id,
        "docs": [
            {
                "slug": d.slug,
                "doc_type": d.doc_type,
                "title": d.title,
                "description": d.description,
                "body": d.body,
                "campos_requeridos": d.campos_requeridos,
                "campos_opcionales": d.campos_opcionales,
                "confirmacion_requerida": d.confirmacion_requerida,
            }
            for d in config._docs
        ],
        "prompts": [
            {"estilo": p.estilo, "system_prompt": p.system_prompt}
            for p in config._prompts
        ],
    }


class _CachedDoc:
    __slots__ = (
        "slug", "doc_type", "title", "description",
        "body", "campos_requeridos", "campos_opcionales", "confirmacion_requerida",
    )

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _CachedPrompt:
    __slots__ = ("estilo", "system_prompt")

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


def _deserialize_tenant_config(data: dict) -> TenantConfig:
    docs = [_CachedDoc(**d) for d in data["docs"]]
    prompts = [_CachedPrompt(**p) for p in data["prompts"]]
    return TenantConfig(tenant_id=data["tenant_id"], docs=docs, prompts=prompts)

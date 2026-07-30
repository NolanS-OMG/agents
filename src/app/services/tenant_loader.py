import json
import logging

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
        prompt = await TenantPrompt.filter(tenant_id=tenant_id, active=True).first()
    except Exception as e:
        logger.warning(f"Failed to load tenant {tenant_id} from DB: {e}")
        return None

    if not docs:
        return None

    config = TenantConfig(tenant_id=tenant_id, docs=docs, prompt=prompt)

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
        "prompt": {
            "estilo": config._prompt.estilo,
            "system_prompt": config._prompt.system_prompt,
        }
        if config._prompt
        else None,
    }


def _deserialize_tenant_config(data: dict) -> TenantConfig:
    class FakeDoc:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class FakePrompt:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    docs = [FakeDoc(**d) for d in data["docs"]]
    prompt = FakePrompt(**data["prompt"]) if data["prompt"] else None
    return TenantConfig(tenant_id=data["tenant_id"], docs=docs, prompt=prompt)

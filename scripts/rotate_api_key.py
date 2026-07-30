"""Rotate API key for a tenant.

Usage:
    uv run python scripts/rotate_api_key.py --tenant santa_lena
"""

import asyncio
import hashlib
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings
from src.app.db.models import ApiKey, Tenant


async def rotate(tenant_id: str) -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    tenant = await Tenant.get_or_none(id=tenant_id)
    if not tenant:
        print(f"  ERROR: Tenant '{tenant_id}' not found")
        await Tortoise.close_connections()
        return

    deactivated = await ApiKey.filter(tenant_id=tenant_id, active=True).update(active=False)
    print(f"  Deactivated {deactivated} existing key(s)")

    prefix = f"sk_{tenant_id[:8]}_"
    random_part = secrets.token_urlsafe(24)
    raw_key = prefix + random_part
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    await ApiKey.create(
        tenant_id=tenant_id,
        key_hash=key_hash,
        key_prefix=raw_key[:12],
    )

    print(f"  New API Key: {raw_key}")
    print("  (save it now — cannot be recovered)")

    await Tortoise.close_connections()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rotate API key for a tenant")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    args = parser.parse_args()

    print(f"Rotating key for: {args.tenant}")
    asyncio.run(rotate(args.tenant))

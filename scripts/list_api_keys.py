#!/usr/bin/env python3
"""List all API keys or generate a new one for a tenant.

Usage:
    # List all keys
    uv run python scripts/list_api_keys.py

    # List keys for specific tenant
    uv run python scripts/list_api_keys.py --tenant portfolio

    # Generate new key for tenant (deactivates old ones)
    uv run python scripts/list_api_keys.py --tenant portfolio --generate
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


def generate_api_key(tenant_id: str) -> tuple[str, str]:
    prefix = f"sk_{tenant_id[:8]}_"
    random_part = secrets.token_urlsafe(24)
    raw_key = prefix + random_part
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def list_keys(tenant_id: str | None = None) -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    query = ApiKey.all().prefetch_related("tenant")
    if tenant_id:
        query = query.filter(tenant_id=tenant_id)

    keys = await query.order_by("-created_at")

    if not keys:
        print("❌ No API keys found")
        if tenant_id:
            print(f"   Tenant '{tenant_id}' has no keys. Use --generate to create one.")
        await Tortoise.close_connections()
        return

    print("\n📋 API KEYS\n")
    print(f"{'TENANT':<15} {'PREFIX':<20} {'STATUS':<10} {'LAST USED':<20} {'CREATED'}")
    print("=" * 90)

    for key in keys:
        status = "✅ active" if key.active else "❌ inactive"
        last_used = key.last_used_at.strftime("%Y-%m-%d %H:%M") if key.last_used_at else "never"
        created = key.created_at.strftime("%Y-%m-%d %H:%M")
        print(f"{key.tenant_id:<15} {key.key_prefix:<20} {status:<10} {last_used:<20} {created}")

    print()
    await Tortoise.close_connections()


async def generate_new_key(tenant_id: str) -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    tenant = await Tenant.get_or_none(id=tenant_id)
    if not tenant:
        print(f"❌ Tenant '{tenant_id}' not found")
        print("   Available tenants:")
        tenants = await Tenant.all()
        for t in tenants:
            print(f"     - {t.id} ({t.name})")
        await Tortoise.close_connections()
        return

    old_keys = await ApiKey.filter(tenant_id=tenant_id, active=True).count()
    if old_keys:
        print(f"⚠️  Deactivating {old_keys} existing key(s) for '{tenant_id}'...")
        await ApiKey.filter(tenant_id=tenant_id, active=True).update(active=False)

    raw_key, key_hash = generate_api_key(tenant_id)
    await ApiKey.create(
        tenant_id=tenant_id,
        key_hash=key_hash,
        key_prefix=raw_key[:12],
    )

    print(f"\n✅ New API Key for '{tenant_id}':")
    print(f"\n   {raw_key}\n")
    print("   ⚠️  SAVE THIS NOW — it cannot be recovered later!\n")

    await Tortoise.close_connections()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="List or generate API keys")
    parser.add_argument("--tenant", help="Filter by tenant ID")
    parser.add_argument("--generate", action="store_true", help="Generate new key for tenant")
    args = parser.parse_args()

    if args.generate:
        if not args.tenant:
            print("❌ --generate requires --tenant")
            sys.exit(1)
        asyncio.run(generate_new_key(args.tenant))
    else:
        asyncio.run(list_keys(args.tenant))

#!/usr/bin/env python3
"""Seed production database with Santa Leña tenant data.

Reads knowledge docs from storage/knowledge/santa_lena/ and prompts from
a JSON export file. Idempotent: safe to run multiple times.

Usage:
    # Export prompts from local DB first (run once locally):
    uv run python scripts/seed_santa_lena.py --export-prompts

    # Seed production (with DATABASE_URL pointing to prod):
    DATABASE_URL=postgres://user:pass@host:5432/db uv run python scripts/seed_santa_lena.py

    # With Twilio credentials:
    uv run python scripts/seed_santa_lena.py \
        --twilio-sid ACxxx --twilio-token xxx --twilio-number +1234567890
"""

import argparse
import asyncio
import hashlib
import json
import secrets
import sys
from pathlib import Path

import yaml
from tortoise import Tortoise

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.core.config import settings

TENANT_ID = "santa_lena"
TENANT_NAME = "Restaurant Santa Lena"
TENANT_CONFIG = {"estilo": "chat"}

KNOWLEDGE_DIR = Path("storage/knowledge/santa_lena")
PROMPTS_EXPORT = Path("storage/santa_lena_prompts.json")


def generate_api_key() -> tuple[str, str]:
    prefix = f"sk_{TENANT_ID[:8]}_"
    random_part = secrets.token_urlsafe(24)
    raw_key = prefix + random_part
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def export_prompts() -> None:
    """Export current prompts from DB to JSON file."""
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )
    from src.app.db.models import TenantPrompt

    prompts = await TenantPrompt.filter(tenant_id=TENANT_ID).all()
    data = [{"estilo": p.estilo, "system_prompt": p.system_prompt} for p in prompts]

    PROMPTS_EXPORT.parent.mkdir(parents=True, exist_ok=True)
    PROMPTS_EXPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"✅ Exported {len(data)} prompts to {PROMPTS_EXPORT}")

    await Tortoise.close_connections()


async def seed() -> None:
    """Seed tenant, prompts, knowledge docs, and optionally credentials."""
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas(safe=True)

    from src.app.db.models import ApiKey, KnowledgeDocument, Tenant, TenantPrompt

    # 1. Tenant
    tenant, created = await Tenant.get_or_create(
        id=TENANT_ID, defaults={"name": TENANT_NAME, "config": TENANT_CONFIG}
    )
    if not created:
        tenant.name = TENANT_NAME
        tenant.config = TENANT_CONFIG
        tenant.active = True
        await tenant.save()
    print(f"{'✅ Created' if created else '✏️  Updated'} tenant: {TENANT_ID}")

    # 2. Prompts (from exported JSON)
    if PROMPTS_EXPORT.exists():
        prompts_data = json.loads(PROMPTS_EXPORT.read_text())
        for p in prompts_data:
            prompt, p_created = await TenantPrompt.get_or_create(
                tenant=tenant, estilo=p["estilo"],
                defaults={"system_prompt": p["system_prompt"]},
            )
            if not p_created:
                prompt.system_prompt = p["system_prompt"]
                await prompt.save()
            status = "✅ new" if p_created else "✏️  updated"
            print(f"  {status}: prompt '{p['estilo']}' ({len(p['system_prompt'])} chars)")
    else:
        print(f"  ⚠️  {PROMPTS_EXPORT} not found. Run with --export-prompts first.")

    # 3. Knowledge documents
    if KNOWLEDGE_DIR.exists():
        indexed = 0
        for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            file_hash = hashlib.sha256(content.encode()).hexdigest()

            frontmatter: dict = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                    except yaml.YAMLError:
                        pass

            relative_path = md_file.resolve().relative_to(Path.cwd().resolve())
            slug = frontmatter.get("slug", str(md_file.relative_to(KNOWLEDGE_DIR)).replace(".md", ""))
            doc_type = frontmatter.get("doc_type", "info")
            title = frontmatter.get("title", md_file.stem.replace("-", " ").title())
            description = frontmatter.get("description", "")

            doc_data = {
                "doc_type": doc_type,
                "title": title,
                "description": description,
                "file_path": str(relative_path),
                "file_format": "md",
                "file_hash": file_hash,
                "tags": frontmatter.get("tags", []),
                "status": frontmatter.get("status", "stable"),
                "campos_requeridos": frontmatter.get("campos_requeridos", []),
                "campos_opcionales": frontmatter.get("campos_opcionales", []),
                "confirmacion_requerida": frontmatter.get("confirmacion_requerida", False),
                "channels": frontmatter.get("channels", ["web", "whatsapp", "call"]),
                "frontend_action": frontmatter.get("frontend_action", False),
                "frontend_tool": frontmatter.get("frontend_tool", ""),
            }

            doc, doc_created = await KnowledgeDocument.get_or_create(
                tenant=tenant, slug=slug, defaults=doc_data
            )
            if not doc_created:
                for key, val in doc_data.items():
                    setattr(doc, key, val)
                await doc.save()

            status = "✅ new" if doc_created else "✏️  updated"
            print(f"  {status}: {slug}")
            indexed += 1

        print(f"📚 Knowledge documents: {indexed}")
    else:
        print(f"⚠️  {KNOWLEDGE_DIR} not found")

    # 4. API Key
    existing_keys = await ApiKey.filter(tenant_id=TENANT_ID, active=True).count()
    if existing_keys == 0:
        raw_key, key_hash = generate_api_key()
        await ApiKey.create(
            tenant_id=TENANT_ID,
            key_hash=key_hash,
            key_prefix=raw_key[:12],
        )
        print(f"\n🔑 API Key created: {raw_key}")
        print("   (save it now — cannot be recovered)")
    else:
        print(f"\n🔑 API Key: {existing_keys} active key(s) exist, skipping")

    # 5. Twilio credentials (if provided via args)
    if hasattr(seed, "_twilio_args") and seed._twilio_args:
        args = seed._twilio_args
        from src.app.db.models import TenantCredentials
        from src.app.services.credential_vault import CredentialVault

        vault = CredentialVault()
        await TenantCredentials.update_or_create(
            tenant_id=TENANT_ID,
            defaults={
                "twilio_account_sid": args.twilio_sid,
                "twilio_auth_token_enc": vault.encrypt(args.twilio_token),
                "twilio_phone_number": args.twilio_number,
            },
        )
        print(f"🔐 Twilio credentials saved for {TENANT_ID}")

    await Tortoise.close_connections()
    print("\n✅ Santa Leña seed complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Santa Leña tenant data")
    parser.add_argument("--export-prompts", action="store_true", help="Export prompts from local DB")
    parser.add_argument("--twilio-sid", help="Twilio Account SID")
    parser.add_argument("--twilio-token", help="Twilio Auth Token")
    parser.add_argument("--twilio-number", help="Twilio Phone Number")
    args = parser.parse_args()

    if args.export_prompts:
        asyncio.run(export_prompts())
    else:
        if args.twilio_sid:
            seed._twilio_args = args
        asyncio.run(seed())

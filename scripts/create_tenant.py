"""Create a new tenant with credentials and API key.

Usage:
    uv run python scripts/create_tenant.py --id santa_lena --name "Santa Leña"
    uv run python scripts/create_tenant.py --id santa_lena --name "Santa Leña" \
        --whatsapp-token "EAABxxx" --whatsapp-phone-id "12345" \
        --whatsapp-verify-token "verify_123" \
        --twilio-sid "ACxxx" --twilio-token "xxx" --twilio-number "+523321016770"
"""

import asyncio
import hashlib
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings
from src.app.db.models import ApiKey, Tenant, TenantCredentials


def generate_api_key(tenant_id: str) -> tuple[str, str]:
    prefix = f"sk_{tenant_id[:8]}_"
    random_part = secrets.token_urlsafe(24)
    raw_key = prefix + random_part
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def create(args) -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    tenant, created = await Tenant.get_or_create(
        id=args.id, defaults={"name": args.name}
    )
    print(f"  Tenant '{args.id}': {'created' if created else 'already exists'}")

    if any([args.whatsapp_token, args.whatsapp_phone_id, args.twilio_sid]):
        from src.app.services.credential_vault import CredentialVault

        vault = CredentialVault()
        creds_data = {
            "whatsapp_phone_number_id": args.whatsapp_phone_id or "",
            "whatsapp_verify_token": args.whatsapp_verify_token or "",
            "twilio_account_sid": args.twilio_sid or "",
            "twilio_phone_number": args.twilio_number or "",
            "whatsapp_access_token_enc": vault.encrypt(args.whatsapp_token) if args.whatsapp_token else "",
            "twilio_auth_token_enc": vault.encrypt(args.twilio_token) if args.twilio_token else "",
        }
        await TenantCredentials.update_or_create(
            tenant_id=args.id, defaults=creds_data
        )
        print("  Credentials encrypted and saved")

    existing_keys = await ApiKey.filter(tenant_id=args.id, active=True).count()
    if existing_keys:
        print(f"  Warning: tenant already has {existing_keys} active key(s)")

    raw_key, key_hash = generate_api_key(args.id)
    await ApiKey.create(
        tenant_id=args.id,
        key_hash=key_hash,
        key_prefix=raw_key[:12],
    )
    print(f"  API Key: {raw_key}")
    print("  (save it now — cannot be recovered)")

    await Tortoise.close_connections()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create a new tenant")
    parser.add_argument("--id", required=True, help="Tenant ID (slug)")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--whatsapp-token", default="", help="WhatsApp access token")
    parser.add_argument("--whatsapp-phone-id", default="", help="WhatsApp phone number ID")
    parser.add_argument("--whatsapp-verify-token", default="", help="WhatsApp verify token")
    parser.add_argument("--twilio-sid", default="", help="Twilio account SID")
    parser.add_argument("--twilio-token", default="", help="Twilio auth token")
    parser.add_argument("--twilio-number", default="", help="Twilio phone number")
    args = parser.parse_args()

    print(f"Creating tenant: {args.id}")
    asyncio.run(create(args))

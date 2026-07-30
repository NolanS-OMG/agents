"""Migrate OKF filesystem documents to PostgreSQL.

Usage:
    uv run python scripts/migrate_okf_to_db.py --tenant santa_lena
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings
from src.app.db.models import KnowledgeDocument, Tenant, TenantPrompt
from src.app.services.tenant import TENANTS_DIR, OKFDocument


def extract_table_column(body: str, section: str, col: int) -> list[str]:
    in_section = False
    values: list[str] = []
    for line in body.split("\n"):
        if section.lower() in line.lower() and "#" in line:
            in_section = True
            continue
        if in_section and line.startswith("#"):
            break
        if in_section and "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) > col and not cells[col].startswith("-"):
                val = cells[col]
                if val != "Campo":
                    values.append(val)
    return values


def slug_from_path(tenant_path: Path, file_path: Path) -> str:
    relative = file_path.relative_to(tenant_path)
    return str(relative.with_suffix("")).replace("\\", "/")


def doc_type_from_okf(doc: OKFDocument) -> str:
    type_map = {
        "Negocio": "negocio",
        "Promociones": "promociones",
        "Menú": "menu",
        "Acción": "accion",
        "Estilo": "estilo",
        "Bundle": "bundle",
    }
    return type_map.get(doc.type, "otro")


async def migrate(tenant_id: str) -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()

    tenant, created = await Tenant.get_or_create(
        id=tenant_id, defaults={"name": tenant_id.replace("_", " ").title()}
    )
    action = "created" if created else "exists"
    print(f"  Tenant '{tenant_id}': {action}")

    path = TENANTS_DIR / tenant_id
    if not path.exists():
        print(f"  ERROR: Path not found: {path}")
        return

    doc_count = 0
    prompt_count = 0

    for md_file in sorted(path.rglob("*.md")):
        if md_file.name in ("log.md",):
            continue

        try:
            okf = OKFDocument(md_file)
        except Exception as e:
            print(f"  SKIP {md_file.name}: {e}")
            continue

        slug = slug_from_path(path, md_file)
        dtype = doc_type_from_okf(okf)

        if dtype == "estilo":
            await TenantPrompt.update_or_create(
                tenant_id=tenant_id,
                estilo=md_file.stem,
                defaults={
                    "system_prompt": okf.body,
                    "active": True,
                },
            )
            prompt_count += 1
            print(f"  PROMPT {md_file.stem}")
            continue

        if dtype == "bundle":
            continue

        campos_req: list[str] = []
        campos_opt: list[str] = []
        confirmacion = False

        if dtype == "accion":
            campos_req = extract_table_column(okf.body, "Campos requeridos", 0)
            campos_opt = extract_table_column(okf.body, "Campos opcionales", 0)
            confirmacion = "confirmación" in okf.body.lower()

        tags = okf.frontmatter.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        await KnowledgeDocument.update_or_create(
            tenant_id=tenant_id,
            slug=slug,
            defaults={
                "doc_type": dtype,
                "title": okf.title or md_file.stem,
                "description": str(okf.frontmatter.get("description", "")),
                "body": okf.body,
                "tags": tags,
                "status": "stable",
                "campos_requeridos": campos_req,
                "campos_opcionales": campos_opt,
                "confirmacion_requerida": confirmacion,
            },
        )
        doc_count += 1
        print(f"  DOC  {slug} ({dtype})")

    print(f"\nDone: {doc_count} documents, {prompt_count} prompts migrated.")
    await Tortoise.close_connections()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate OKF to PostgreSQL")
    parser.add_argument("--tenant", required=True, help="Tenant ID to migrate")
    args = parser.parse_args()

    print(f"Migrating tenant: {args.tenant}")
    asyncio.run(migrate(args.tenant))

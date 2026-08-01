#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings
from src.app.db.models import KnowledgeDocument, Tenant
from src.app.utils.file_parsers import calculate_file_hash, write_markdown_with_frontmatter

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage" / "knowledge"
DATA_DIR = PROJECT_ROOT / "data" / "tenants"


async def migrate_documents_to_files() -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    tenants = await Tenant.filter(active=True).all()
    print(f"Found {len(tenants)} active tenants")

    for tenant in tenants:
        print(f"\n=== Migrating tenant: {tenant.id} ===")
        tenant_dir = STORAGE_DIR / tenant.id
        tenant_dir.mkdir(parents=True, exist_ok=True)

        docs = await KnowledgeDocument.filter(tenant_id=tenant.id, status="stable").all()
        print(f"  Documents to migrate: {len(docs)}")

        for doc in docs:
            slug_path = doc.slug
            file_path = tenant_dir / f"{slug_path}.md"
            file_path.parent.mkdir(parents=True, exist_ok=True)

            frontmatter = {
                "slug": doc.slug,
                "doc_type": doc.doc_type,
                "title": doc.title,
                "description": doc.description,
                "tags": doc.tags,
                "status": doc.status,
            }

            if doc.doc_type == "accion":
                frontmatter["campos_requeridos"] = doc.campos_requeridos
                frontmatter["campos_opcionales"] = doc.campos_opcionales
                frontmatter["confirmacion_requerida"] = doc.confirmacion_requerida

            body = getattr(doc, "body", "")
            content = write_markdown_with_frontmatter(frontmatter, body)
            file_path.write_text(content, encoding="utf-8")

            file_hash = calculate_file_hash(file_path)
            relative_path = str(file_path.relative_to(PROJECT_ROOT))

            doc.file_path = relative_path
            doc.file_format = "md"
            doc.file_hash = file_hash
            await doc.save(update_fields=["file_path", "file_format", "file_hash"])

            print(f"  ✓ {doc.slug} → {relative_path}")

    print("\n=== Migration complete ===")
    print(f"Files created in: {STORAGE_DIR}")
    print("\nNext steps:")
    print("1. Verify files were created correctly")
    print("2. Run: ALTER TABLE knowledge_documents DROP COLUMN body;")
    print("3. Restart server")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(migrate_documents_to_files())

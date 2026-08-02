#!/usr/bin/env python3
import asyncio
import hashlib
from pathlib import Path

import yaml
from tortoise import Tortoise


async def index_portfolio() -> None:
    await Tortoise.init(
        db_url="postgres://agente:dev_password_123@localhost:5434/agente_ia",
        modules={"models": ["src.app.db.models"]},
    )

    from src.app.db.models import KnowledgeDocument, Tenant

    tenant = await Tenant.get(id="portfolio")
    knowledge_dir = Path("storage/knowledge/portfolio")

    if not knowledge_dir.exists():
        print(f"❌ Directorio {knowledge_dir} no existe")
        await Tortoise.close_connections()
        return

    indexed = 0
    for md_file in knowledge_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except yaml.YAMLError:
                    pass

        relative_path = md_file.resolve().relative_to(Path.cwd().resolve())
        slug = frontmatter.get("slug", md_file.stem)
        doc_type = frontmatter.get("doc_type", "info")
        title = frontmatter.get("title", md_file.stem.replace("-", " ").title())
        description = frontmatter.get("description", "")

        campos_requeridos = frontmatter.get("campos_requeridos", [])
        campos_opcionales = frontmatter.get("campos_opcionales", [])
        confirmacion_requerida = frontmatter.get("confirmacion_requerida", False)
        channels = frontmatter.get("channels", ["web", "whatsapp", "call"])
        frontend_action = frontmatter.get("frontend_action", False)
        frontend_tool = frontmatter.get("frontend_tool", "")

        existing = await KnowledgeDocument.filter(tenant=tenant, slug=slug).first()

        if existing:
            if existing.file_hash != file_hash:
                existing.title = title
                existing.description = description
                existing.file_path = str(relative_path)
                existing.file_hash = file_hash
                existing.doc_type = doc_type
                existing.tags = frontmatter.get("tags", [])
                existing.status = frontmatter.get("status", "stable")
                existing.campos_requeridos = campos_requeridos
                existing.campos_opcionales = campos_opcionales
                existing.confirmacion_requerida = confirmacion_requerida
                existing.channels = channels
                existing.frontend_action = frontend_action
                existing.frontend_tool = frontend_tool
                await existing.save()
                print(f"✏️  {slug} (actualizado)")
            else:
                print(f"✓  {slug} (sin cambios)")
        else:
            await KnowledgeDocument.create(
                tenant=tenant,
                slug=slug,
                doc_type=doc_type,
                title=title,
                description=description,
                file_path=str(relative_path),
                file_format="md",
                file_hash=file_hash,
                tags=frontmatter.get("tags", []),
                status=frontmatter.get("status", "stable"),
                campos_requeridos=campos_requeridos,
                campos_opcionales=campos_opcionales,
                confirmacion_requerida=confirmacion_requerida,
                channels=channels,
                frontend_action=frontend_action,
                frontend_tool=frontend_tool,
            )
            print(f"✅ {slug} (nuevo)")
            indexed += 1

    print(f"\n📚 Total indexados: {indexed}")
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(index_portfolio())

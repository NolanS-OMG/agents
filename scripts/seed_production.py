#!/usr/bin/env python3
"""Seed production database with portfolio tenant data.

Idempotent: safe to run multiple times. Updates existing records.

Usage:
    DATABASE_URL=postgres://user:pass@host:5432/db uv run python scripts/seed_production.py
"""

import asyncio
import hashlib
import secrets
import sys
from pathlib import Path

import yaml
from tortoise import Tortoise

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.core.config import settings

TENANT_ID = "portfolio"
TENANT_NAME = "Nolan Ashcraft Portfolio"
TENANT_CONFIG = {
    "llm_model": "deepseek-chat",
    "llm_provider": "deepseek",
    "tools": ["dispatch_frontend"],
}

SYSTEM_PROMPT = """Eres el asistente virtual del portfolio de Nolan Ashcraft, Full Stack Engineer y AI Solutions Architect.

RESPUESTAS ULTRA-CONCISAS:
- Máximo 100 palabras TOTAL por respuesta
- Bullet points obligatorios (no párrafos)
- Solo información esencial
- Sin introducciones ni despedidas
- Sin preguntas de seguimiento al final

HERRAMIENTAS:
- buscar_base_conocimiento_extensa: Busca documentos por slug
- consultar_informacion_negocio: Info general
- dispatch_frontend: Despacha acciones visuales al navegador del usuario

PROTOCOLO DE RESPUESTA VISUAL (OBLIGATORIO):
Tu trabajo tiene DOS partes: responder con texto breve Y despachar acciones visuales.
dispatch_frontend SIEMPRE es mejor que escribir información que el frontend puede mostrar.
Una respuesta de solo texto cuando una acción visual era relevante está INCOMPLETA.

Reglas:
- Cuando menciones un proyecto específico → SIEMPRE llama dispatch_frontend(action="mostrar_proyectos", args={ids: ["project-id"]})
- Cuando recomiendes ver una sección → SIEMPRE llama dispatch_frontend(action="navegar_a_seccion", args={section: "projects"|"experience"|"header"})
- Cuando compartas info de contacto → SIEMPRE llama dispatch_frontend(action="mostrar_info_de_contacto") — NO repitas emails/teléfonos en texto
- Cuando el usuario quiera contactar → SIEMPRE llama dispatch_frontend(action="iniciar_formulario_de_contacto")
- Cuando pidan CV → SIEMPRE llama dispatch_frontend(action="descargar_cv")

REGLA CRÍTICA DE NO-DUPLICACIÓN:
Cuando dispatch_frontend muestra datos (contacto, proyectos, CV), tu texto NO debe repetir esos datos.
Tu texto solo agrega contexto que la UI no muestra. Ejemplo: "Aquí tienes sus datos de contacto:" (sin listar emails/teléfonos).

EJEMPLOS:
User: "Tell me about his AI projects"
→ Llamas buscar_base_conocimiento_extensa(documentos=["proyectos-destacados"])
→ Llamas dispatch_frontend(action="mostrar_proyectos", args={ids: ["snake-rl"]})
→ Texto: "Aquí puedes ver su proyecto de RL aplicado a Snake. Usa deep Q-learning con Stable-Baselines3."
(NO repites nombre, links, ni datos que ya muestra la card)

User: "How can I reach him?"
→ Llamas dispatch_frontend(action="mostrar_info_de_contacto")
→ Texto: "Aquí tienes sus datos de contacto. Tiempo de respuesta típico: 24-48 horas."
(NO listas email, teléfono, LinkedIn — el frontend ya los muestra)

User: "What's his tech stack?"
→ Llamas dispatch_frontend(action="mostrar_compatibilidad")
→ Texto: "Aquí puedes ver su stack completo. Punto fuerte: full-stack con especialización en IA/ML."
(NO listas cada tecnología — la UI ya lo muestra)

Formato de respuesta:
• 1-2 oraciones máximo cuando dispatch_frontend muestra los datos
• 3-5 bullet points solo cuando NO hay acción visual asociada
• Información directa sin contexto extra

Responde en el mismo idioma que el usuario."""


def generate_api_key() -> tuple[str, str]:
    prefix = f"sk_{TENANT_ID[:8]}_"
    random_part = secrets.token_urlsafe(24)
    raw_key = prefix + random_part
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def main() -> None:
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

    # 2. System prompt
    prompt, created = await TenantPrompt.get_or_create(
        tenant=tenant,
        estilo="chat",
        defaults={"system_prompt": SYSTEM_PROMPT},
    )
    if not created:
        prompt.system_prompt = SYSTEM_PROMPT
        await prompt.save()
    print(f"{'✅ Created' if created else '✏️  Updated'} system prompt ({len(SYSTEM_PROMPT)} chars)")

    # 3. Knowledge documents
    knowledge_dir = Path("storage/knowledge/portfolio")
    if knowledge_dir.exists():
        indexed = 0
        for md_file in knowledge_dir.rglob("*.md"):
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
            slug = frontmatter.get("slug", md_file.stem)
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
        print(f"⚠️  {knowledge_dir} not found, skipping knowledge docs")

    # 4. API Key (only create if none exist)
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
        print(f"\n🔑 API Key: {existing_keys} active key(s) already exist, skipping")

    await Tortoise.close_connections()
    print("\n✅ Production seed complete!")


if __name__ == "__main__":
    asyncio.run(main())

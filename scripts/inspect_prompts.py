"""Inspect all prompts and tool schemas that the LLM sees for a tenant.

Usage:
    uv run python scripts/inspect_prompts.py --tenant santa_lena
    uv run python scripts/inspect_prompts.py --tenant santa_lena --output docs/prompts-santa-lena.md
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings
from src.app.services.agent_router import BASE_SYSTEM_PROMPT
from src.app.services.tenant_loader import load_tenant_async
from src.app.tools.registry import get_tools_for_tenant


async def inspect(tenant_id: str, output_path: str | None = None) -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    tenant_config = await load_tenant_async(tenant_id)

    sections: list[str] = []

    sections.append(f"# Prompts & Tools — Tenant: {tenant_id}\n")
    sections.append(f"> Generado automáticamente. Esto es lo que el LLM recibe.\n")

    # 1. BASE SYSTEM PROMPT
    filled_prompt = BASE_SYSTEM_PROMPT.format(sender_id="<SENDER_ID>")
    sections.append("---\n## 1. Base System Prompt (hardcoded)\n")
    sections.append(f"**Archivo:** `src/app/services/agent_router.py` línea 12\n")
    sections.append(f"**Tokens estimados:** ~{len(filled_prompt) // 3}\n")
    sections.append(f"```\n{filled_prompt}\n```\n")

    # 2. TENANT PROMPT (from DB)
    tenant_prompt = tenant_config.get_prompt("chat")
    sections.append("---\n## 2. Tenant Prompt — get_prompt('chat')\n")
    sections.append(f"**Fuente:** DB (knowledge_documents + tenant_prompts)\n")
    sections.append(f"**Tokens estimados:** ~{len(tenant_prompt) // 3}\n")
    sections.append(f"```\n{tenant_prompt}\n```\n")

    # 3. TOOL SCHEMAS
    tools = get_tools_for_tenant(tenant_config)
    sections.append("---\n## 3. Tool Schemas (se envían en cada llamada)\n")
    sections.append(f"**Total tools:** {len(tools)}\n")

    total_tool_tokens = 0
    for tool in tools:
        schema = tool.schema()
        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
        tool_tokens = len(schema_json) // 3
        total_tool_tokens += tool_tokens
        sections.append(f"\n### Tool: `{tool.name}`\n")
        sections.append(f"**Tokens estimados:** ~{tool_tokens}\n")
        sections.append(f"```json\n{schema_json}\n```\n")

    sections.append(f"\n**Total tokens en tools:** ~{total_tool_tokens}\n")

    # 4. RESUMEN
    system_total = len(filled_prompt) // 3 + len(tenant_prompt) // 3
    grand_total = system_total + total_tool_tokens
    sections.append("---\n## 4. Resumen de tokens fijos por request\n")
    sections.append(f"| Componente | Tokens |\n")
    sections.append(f"|-----------|--------|\n")
    sections.append(f"| Base system prompt | ~{len(filled_prompt) // 3} |\n")
    sections.append(f"| Tenant prompt (negocio + promos + índice + estilo) | ~{len(tenant_prompt) // 3} |\n")
    sections.append(f"| Tool schemas ({len(tools)} tools) | ~{total_tool_tokens} |\n")
    sections.append(f"| **TOTAL FIJO** | **~{grand_total}** |\n")

    # 5. DOCUMENTS AVAILABLE
    sections.append("---\n## 5. Documentos disponibles (se leen bajo demanda)\n")
    sections.append("| Slug | Tipo | Título | Tokens body |\n")
    sections.append("|------|------|--------|-------------|\n")
    for doc in tenant_config.docs:
        body_tokens = len(doc.body) // 3 if hasattr(doc, 'body') and doc.body else 0
        sections.append(f"| `{doc.slug}` | {doc.doc_type} | {doc.title} | ~{body_tokens} |\n")

    # Output
    full_output = "\n".join(sections)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(full_output, encoding="utf-8")
        print(f"Written to: {output_path}")
    else:
        print(full_output)

    await Tortoise.close_connections()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect LLM prompts for a tenant")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--output", default=None, help="Output .md file path (prints to stdout if omitted)")
    args = parser.parse_args()

    asyncio.run(inspect(args.tenant, args.output))

#!/usr/bin/env python3
"""Update portfolio tenant: config.tools + system prompt with Response Protocol."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings

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
Tu trabajo tiene DOS partes: responder con información Y orquestar la experiencia visual.
Una respuesta de solo texto cuando una acción visual era relevante está INCOMPLETA.

Reglas:
- Cuando menciones un proyecto específico → SIEMPRE llama dispatch_frontend(action="mostrar_proyectos", args={ids: ["project-id"]})
- Cuando recomiendes ver una sección → SIEMPRE llama dispatch_frontend(action="navegar_a_seccion", args={section: "projects"|"experience"|"header"})
- Cuando compartas info de contacto → SIEMPRE llama dispatch_frontend(action="mostrar_info_de_contacto")
- Cuando el usuario quiera contactar → SIEMPRE llama dispatch_frontend(action="iniciar_formulario_de_contacto")
- Cuando pidan CV → SIEMPRE llama dispatch_frontend(action="descargar_cv")

EJEMPLOS:
User: "Tell me about his AI projects"
→ Llamas buscar_base_conocimiento_extensa(documentos=["proyectos-destacados"])
→ Llamas dispatch_frontend(action="mostrar_proyectos", args={ids: ["snake-rl"]})
→ Respondes con bullet points sobre el proyecto

User: "How can I reach him?"
→ Llamas dispatch_frontend(action="mostrar_info_de_contacto")
→ Respondes con los datos de contacto en bullet points

Formato de respuesta:
• 3-5 bullet points máximo
• Información directa sin contexto extra
• No expandir más allá de lo preguntado

Responde en el mismo idioma que el usuario."""


async def main() -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )

    from src.app.db.models import Tenant, TenantPrompt

    # Update tenant config to use dispatch_frontend
    tenant = await Tenant.get(id="portfolio")
    tenant.config = {
        **tenant.config,
        "tools": ["dispatch_frontend"],
    }
    await tenant.save()
    print(f"✅ Tenant config updated: {json.dumps(tenant.config)}")

    # Update system prompt
    prompt = await TenantPrompt.get(tenant_id="portfolio", estilo="chat")
    prompt.system_prompt = SYSTEM_PROMPT
    await prompt.save()
    print(f"✅ System prompt updated ({len(SYSTEM_PROMPT)} chars)")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())

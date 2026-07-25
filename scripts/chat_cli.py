#!/usr/bin/env python3
"""CLI para probar el agente en terminal. Ejecutar: uv run python scripts/chat_cli.py"""

import asyncio
import sys
import uuid

from httpx import AsyncClient

from src.app.core.config import settings
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.base import LLMMessage
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.tenant import load_tenant
from src.app.tools.registry import get_tools_for_tenant


async def main() -> None:
    tenant = load_tenant(settings.tenant_id)
    print(f"\n{'='*60}")
    print(f"  {tenant.negocio.get('title', 'Agente')} - Chat CLI")
    print(f"  Tenant: {settings.tenant_id} | Estilo: {settings.estilo}")
    print(f"  Modelo: {settings.llm_model}")
    print(f"{'='*60}")
    print("  Escribe 'salir' para terminar.\n")

    session_id = str(uuid.uuid4())[:8]
    history: list[LLMMessage] = []

    async with AsyncClient(timeout=settings.llm_timeout) as http_client:
        llm = get_llm_provider(http_client)
        tools = get_tools_for_tenant(tenant)

        while True:
            try:
                user_input = input("\n🧑 Tú: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nHasta luego!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("salir", "exit", "quit"):
                print("\nHasta luego!")
                break

            agent = AgentRouter(llm=llm, tools=tools, tenant_prompt=tenant.get_prompt(settings.estilo))

            try:
                result = await agent.run(user_message=user_input, history=history)
            except Exception as e:
                print(f"\n❌ Error: {e}")
                continue

            print(f"\n🤖 Agente: {result.response}")

            history = [
                m for m in result.messages
                if m.role in ("user", "assistant") and m.content
            ][-20:]

            if settings.debug:
                print(f"   [debug] tokens: {result.usage}")
                print(f"   [debug] session: {session_id}")


if __name__ == "__main__":
    if not settings.llm_api_key:
        print("ERROR: LLM_API_KEY no configurada. Edita .env")
        sys.exit(1)
    asyncio.run(main())

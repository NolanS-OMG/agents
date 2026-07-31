#!/usr/bin/env python3
"""CLI para probar el agente en terminal.

Uso:
    uv run python scripts/chat_cli.py                       # usa tenant de .env
    uv run python scripts/chat_cli.py --tenant portfolio    # tenant especifico de DB
"""

import argparse
import asyncio
import sys

from httpx import AsyncClient
from tortoise import Tortoise

from src.app.core.config import settings
from src.app.services.agent_router import AgentRouter
from src.app.services.llm.base import LLMMessage
from src.app.services.llm.provider_factory import get_llm_provider
from src.app.services.tenant import load_tenant
from src.app.services.tenant_loader import load_tenant_from_db
from src.app.tools.registry import get_tools_for_tenant


async def main(tenant_id: str | None = None) -> None:
    use_db = tenant_id is not None
    if use_db:
        await Tortoise.init(
            db_url=settings.database_url,
            modules={"models": ["src.app.db.models"]},
        )
        tenant = await load_tenant_from_db(tenant_id)
        if not tenant:
            print(f"ERROR: Tenant '{tenant_id}' no encontrado en la DB.")
            await Tortoise.close_connections()
            sys.exit(1)
    else:
        tenant_id = settings.tenant_id
        tenant = load_tenant(tenant_id)

    print(f"\n{'=' * 60}")
    print("  Agente IA - Chat CLI")
    print(f"  Tenant: {tenant_id}")
    print(f"  Modelo: {settings.llm_model}")
    print(f"  Fuente: {'DB' if use_db else 'filesystem'}")
    print(f"{'=' * 60}")
    print("  Escribe 'salir' para terminar.\n")

    history: list[LLMMessage] = []

    async with AsyncClient(timeout=settings.llm_timeout) as http_client:
        llm = get_llm_provider(http_client)
        tools = get_tools_for_tenant(tenant)

        while True:
            try:
                user_input = input("\nTu: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nHasta luego!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("salir", "exit", "quit"):
                print("\nHasta luego!")
                break

            agent = AgentRouter(llm=llm, tools=tools, tenant_prompt=tenant.get_prompt("chat"))

            try:
                result = await agent.run(user_message=user_input, history=history)
            except Exception as e:
                print(f"\nError: {e}")
                continue

            print(f"\nAgente: {result.response}")
            if result.tool_used:
                print(f"  [tool: {result.tool_used}]")

            history = [m for m in result.messages if m.role in ("user", "assistant") and m.content][
                -20:
            ]

    if use_db:
        await Tortoise.close_connections()


if __name__ == "__main__":
    if not settings.llm_api_key:
        print("ERROR: LLM_API_KEY no configurada. Edita .env")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Chat CLI para probar el agente")
    parser.add_argument("--tenant", default=None, help="Tenant ID (carga de DB)")
    args = parser.parse_args()

    asyncio.run(main(args.tenant))

import json
from typing import Any

from src.app.services.llm.base import LLMMessage, LLMProvider
from src.app.tools.base import BaseTool, ToolError, ToolResult

BASE_SYSTEM_PROMPT = """Eres un asistente virtual de atención al cliente. Tu trabajo es ayudar al usuario de forma clara, amable y eficiente.

REGLAS:
1. Para CONSULTAS (menú, recomendaciones, precios, horarios): responde directo con la información. Recomienda opciones concretas sin preguntar de más.
2. Para ACCIONES (pedidos, reservaciones): SOLO en este caso asegúrate de tener los datos necesarios antes de ejecutar. Si recibes un error de campos faltantes, solicita SOLO esos datos.
3. Responde SIEMPRE en el mismo idioma que el usuario.
4. Sé conciso y directo. No repitas información que el usuario ya proporcionó.
5. Si no puedes resolver algo, indica que transferirás al usuario con un agente humano.
6. Cuando recomiendes, da 2-3 opciones concretas con nombre y precio. No pidas preferencias que no te pidieron.

HERRAMIENTAS DISPONIBLES:
- ejecutar_accion: Para acciones con efecto secundario (pedidos, reservaciones). SOLO esta requiere confirmar datos.
- consultar_informacion_negocio: Para horarios, ubicación, promociones, info general.
- buscar_base_conocimiento_extensa: Para buscar en el menú por categoría, nombre o ingrediente. Devuelve la sección completa relevante.
"""

MAX_TOOL_ITERATIONS = 5


class AgentResult:
    def __init__(
        self,
        response: str,
        tool_used: str | None,
        messages: list[LLMMessage],
        usage: dict[str, Any],
    ) -> None:
        self.response = response
        self.tool_used = tool_used
        self.messages = messages
        self.usage = usage


class AgentRouter:
    def __init__(
        self,
        llm: LLMProvider,
        tools: list[BaseTool],
        tenant_prompt: str = "",
    ) -> None:
        self._llm = llm
        self._tools = {tool.name: tool for tool in tools}
        self._tool_schemas = [tool.schema() for tool in tools]
        self._system_prompt = BASE_SYSTEM_PROMPT
        if tenant_prompt:
            self._system_prompt += f"\n\nCONTEXTO DEL NEGOCIO:\n{tenant_prompt}"

    async def run(
        self,
        user_message: str,
        history: list[LLMMessage] | None = None,
    ) -> AgentResult:
        messages = self._build_messages(user_message, history)

        for _ in range(MAX_TOOL_ITERATIONS):
            response = await self._llm.complete(
                messages=messages,
                tools=self._tool_schemas,
            )

            if not response.tool_calls:
                return AgentResult(
                    response=response.content,
                    tool_used=None,
                    messages=messages,
                    usage=response.usage,
                )

            tool_call = response.tool_calls[0]
            function_data = tool_call["function"]
            tool_name = function_data["name"]
            tool_args = json.loads(function_data.get("arguments", "{}"))
            call_id = tool_call.get("id", "call_0")

            messages.append(LLMMessage(
                role="assistant",
                content=json.dumps({"tool_calls": [tool_call]}),
            ))

            tool_result = await self._execute_tool(tool_name, tool_args)

            messages.append(LLMMessage(
                role="tool",
                content=json.dumps({
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "result": tool_result.model_dump(),
                }),
            ))

            if isinstance(tool_result, ToolError):
                messages.append(LLMMessage(
                    role="system",
                    content=(
                        f"La herramienta '{tool_name}' reportó campos faltantes: "
                        f"{tool_result.campos_faltantes}. "
                        "Solicita amablemente SOLO estos datos al usuario."
                    ),
                ))

        return AgentResult(
            response="Lo siento, no pude completar la operación. ¿Puedo ayudarte de otra forma?",
            tool_used=None,
            messages=messages,
            usage={},
        )

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> ToolResult | ToolError:
        tool = self._tools.get(name)
        if not tool:
            return ToolError(
                error="TOOL_NOT_FOUND",
                categoria="sistema",
                campos_faltantes=[],
                mensaje_sistema=f"Herramienta '{name}' no existe.",
            )
        return await tool.execute(**args)

    def _build_messages(
        self,
        user_message: str,
        history: list[LLMMessage] | None,
    ) -> list[LLMMessage]:
        messages = [LLMMessage(role="system", content=self._system_prompt)]
        if history:
            messages.extend(history)
        messages.append(LLMMessage(role="user", content=user_message))
        return messages

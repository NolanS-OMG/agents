import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.app.services.llm.base import LLMMessage, LLMProvider, LLMResponse
from src.app.tools.base import BaseTool, ToolError, ToolResult

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = """REGLAS:
1. CONSULTAS (menú, precios, horarios): responde directo. Recomienda 2-3 opciones con precio.
2. ACCIONES (pedidos, reservaciones): recopila los datos necesarios antes de ejecutar.
3. Responde en el idioma del usuario. No repitas información ya proporcionada.
4. El teléfono del cliente es "{sender_id}" — no lo pidas.
"""

MAX_TOOL_ITERATIONS = 5


@dataclass(slots=True)
class AgentResult:
    response: str
    tool_used: str | None
    messages: list[LLMMessage]
    usage: dict[str, Any] = field(default_factory=dict)
    needs_human: bool = False
    total_llm_calls: int = 1
    tool_execution_ms: int = 0
    model_actual: str = ""
    cost_usd: float = 0.0
    context_tokens: int = 0
    generation_id: str = ""
    finish_reason: str = ""
    tokens_per_second: float = 0.0
    ttft_ms: int = 0
    retry_count: int = 0


class AgentRouter:
    def __init__(
        self,
        llm: LLMProvider,
        tools: list[BaseTool],
        tenant_prompt: str = "",
        sender_id: str = "",
    ) -> None:
        self._llm = llm
        self._tools = {tool.name: tool for tool in tools}
        self._tool_schemas = [tool.schema() for tool in tools]
        self._system_prompt = BASE_SYSTEM_PROMPT.format(sender_id=sender_id or "desconocido")
        if tenant_prompt:
            self._system_prompt += f"\n\nCONTEXTO DEL NEGOCIO:\n{tenant_prompt}"

    async def run(
        self,
        user_message: str,
        history: list[LLMMessage] | None = None,
    ) -> AgentResult:
        messages = self._build_messages(user_message, history)

        total_llm_calls = 0
        total_tool_ms = 0
        total_cost = 0.0
        last_response: LLMResponse | None = None

        for _ in range(MAX_TOOL_ITERATIONS):
            response = await self._llm.complete(
                messages=messages,
                tools=self._tool_schemas,
            )
            total_llm_calls += 1
            total_cost += response.cost_usd
            last_response = response

            if not response.tool_calls:
                content = response.content or "Lo siento, no pude generar una respuesta."
                messages.append(LLMMessage(role="assistant", content=content))
                return self._build_result(
                    response=content,
                    tool_used=None,
                    messages=messages,
                    llm_response=response,
                    total_llm_calls=total_llm_calls,
                    tool_execution_ms=total_tool_ms,
                    total_cost=total_cost,
                )

            tool_call = response.tool_calls[0]
            function_data = tool_call.get("function", {})
            tool_name = function_data.get("name", "")
            try:
                tool_args = json.loads(function_data.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                tool_args = {}
            call_id = tool_call.get("id", "call_0")

            messages.append(
                LLMMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[tool_call],
                )
            )

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
            t0 = time.time()
            tool_result = await self._execute_tool(tool_name, tool_args)
            total_tool_ms += int((time.time() - t0) * 1000)
            logger.info(f"Tool result: status={getattr(tool_result, 'status', 'N/A')}, error={getattr(tool_result, 'error', None)}")

            if tool_name == "transferir_a_humano" and isinstance(tool_result, ToolResult):
                return self._build_result(
                    response=tool_result.data.get("mensaje", "Te transfiero con un agente humano."),
                    tool_used=tool_name,
                    messages=messages,
                    llm_response=response,
                    total_llm_calls=total_llm_calls,
                    tool_execution_ms=total_tool_ms,
                    total_cost=total_cost,
                    needs_human=True,
                )

            messages.append(
                LLMMessage(
                    role="tool",
                    tool_call_id=call_id,
                    name=tool_name,
                    content=json.dumps(tool_result.model_dump()),
                )
            )

            if isinstance(tool_result, ToolError):
                messages.append(
                    LLMMessage(
                        role="system",
                        content=(
                            f"La herramienta '{tool_name}' reportó campos faltantes: "
                            f"{tool_result.campos_faltantes}. "
                            "Solicita amablemente SOLO estos datos al usuario."
                        ),
                    )
                )

        return AgentResult(
            response="Lo siento, no pude completar la operación. ¿Puedo ayudarte de otra forma?",
            tool_used=None,
            messages=messages,
            usage=last_response.usage if last_response else {},
            total_llm_calls=total_llm_calls,
            tool_execution_ms=total_tool_ms,
            cost_usd=total_cost,
        )

    def _build_result(
        self,
        response: str,
        tool_used: str | None,
        messages: list[LLMMessage],
        llm_response: LLMResponse,
        total_llm_calls: int,
        tool_execution_ms: int,
        total_cost: float,
        needs_human: bool = False,
    ) -> AgentResult:
        return AgentResult(
            response=response,
            tool_used=tool_used,
            messages=messages,
            usage=llm_response.usage,
            needs_human=needs_human,
            total_llm_calls=total_llm_calls,
            tool_execution_ms=tool_execution_ms,
            model_actual=llm_response.model,
            cost_usd=total_cost,
            context_tokens=llm_response.usage.get("prompt_tokens", 0),
            generation_id=llm_response.generation_id,
            finish_reason=llm_response.finish_reason,
            tokens_per_second=llm_response.tokens_per_second,
            ttft_ms=llm_response.ttft_ms,
            retry_count=llm_response.retry_count,
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

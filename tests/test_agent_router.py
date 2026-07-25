import json

import pytest

from src.app.services.agent_router import AgentResult, AgentRouter
from src.app.services.llm.base import LLMMessage, LLMProvider, LLMResponse
from src.app.tools.base import BaseTool, ToolError, ToolResult


class MockLLMProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.calls: list[dict] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "tools": tools})
        response = self._responses[self._call_count]
        self._call_count += 1
        return response


class MockTool(BaseTool):
    def __init__(self, name: str, result: ToolResult | ToolError) -> None:
        self._name = name
        self._result = result
        self.execute_calls: list[dict] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool: {self._name}"

    async def execute(self, **kwargs) -> ToolResult | ToolError:  # type: ignore[override]
        self.execute_calls.append(kwargs)
        return self._result

    def schema(self) -> dict:  # type: ignore[type-arg]
        return {
            "type": "function",
            "function": {
                "name": self._name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}},
            },
        }


def _make_text_response(content: str) -> LLMResponse:
    return LLMResponse(content=content, model="test", usage={"total_tokens": 10})


def _make_tool_call_response(tool_name: str, arguments: dict) -> LLMResponse:
    return LLMResponse(
        content="",
        model="test",
        usage={"total_tokens": 15},
        tool_calls=[{
            "id": "call_test_1",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments),
            },
        }],
    )


@pytest.mark.anyio
async def test_simple_response_without_tools() -> None:
    llm = MockLLMProvider([_make_text_response("Hola, ¿en qué puedo ayudarte?")])
    router = AgentRouter(llm=llm, tools=[])

    result = await router.run("Hola")

    assert isinstance(result, AgentResult)
    assert result.response == "Hola, ¿en qué puedo ayudarte?"
    assert result.tool_used is None
    assert len(llm.calls) == 1


@pytest.mark.anyio
async def test_system_prompt_is_first_message() -> None:
    llm = MockLLMProvider([_make_text_response("Ok")])
    router = AgentRouter(llm=llm, tools=[])

    await router.run("test")

    messages = llm.calls[0]["messages"]
    assert messages[0].role == "system"
    assert "asistente virtual" in messages[0].content


@pytest.mark.anyio
async def test_history_is_included_in_messages() -> None:
    llm = MockLLMProvider([_make_text_response("Entendido")])
    router = AgentRouter(llm=llm, tools=[])
    history = [
        LLMMessage(role="user", content="Quiero agendar una cita"),
        LLMMessage(role="assistant", content="¿Para qué fecha?"),
    ]

    await router.run("Para mañana a las 10", history=history)

    messages = llm.calls[0]["messages"]
    assert messages[1].content == "Quiero agendar una cita"
    assert messages[2].content == "¿Para qué fecha?"
    assert messages[3].content == "Para mañana a las 10"


@pytest.mark.anyio
async def test_tool_call_executes_and_returns_final_response() -> None:
    tool = MockTool("consultar_informacion_negocio", ToolResult(
        status=200,
        data={"horario": "Lunes a Viernes 9-18h"},
    ))
    llm = MockLLMProvider([
        _make_tool_call_response("consultar_informacion_negocio", {"consulta": "horarios"}),
        _make_text_response("Nuestro horario es Lunes a Viernes de 9 a 18h."),
    ])
    router = AgentRouter(llm=llm, tools=[tool])

    result = await router.run("¿Cuál es el horario?")

    assert result.response == "Nuestro horario es Lunes a Viernes de 9 a 18h."
    assert len(tool.execute_calls) == 1
    assert tool.execute_calls[0] == {"consulta": "horarios"}
    assert len(llm.calls) == 2


@pytest.mark.anyio
async def test_tool_error_400_adds_instruction_to_ask_for_fields() -> None:
    tool = MockTool("ejecutar_accion", ToolError(
        error="MISSING_REQUIRED_FIELDS",
        categoria="agenda",
        campos_faltantes=["fecha", "hora"],
        campos_opcionales=["acompanante"],
        mensaje_sistema="Faltan datos para agendar.",
    ))
    llm = MockLLMProvider([
        _make_tool_call_response("ejecutar_accion", {
            "categoria": "agenda",
            "accion_solicitada": "agendar cita",
        }),
        _make_text_response("¿Para qué fecha y hora te gustaría la cita?"),
    ])
    router = AgentRouter(llm=llm, tools=[tool])

    result = await router.run("Quiero agendar una cita")

    assert "fecha" in result.response.lower()
    second_call_messages = llm.calls[1]["messages"]
    system_hints = [
        m for m in second_call_messages
        if m.role == "system" and "reportó campos faltantes" in m.content
    ]
    assert len(system_hints) == 1
    assert "fecha" in system_hints[0].content
    assert "hora" in system_hints[0].content


@pytest.mark.anyio
async def test_unknown_tool_returns_tool_not_found_error() -> None:
    llm = MockLLMProvider([
        _make_tool_call_response("herramienta_inexistente", {}),
        _make_text_response("Lo siento, hubo un problema interno."),
    ])
    router = AgentRouter(llm=llm, tools=[])

    await router.run("Haz algo raro")

    assert len(llm.calls) == 2
    second_messages = llm.calls[1]["messages"]
    tool_msg = [m for m in second_messages if m.role == "tool"]
    assert len(tool_msg) == 1
    assert "TOOL_NOT_FOUND" in tool_msg[0].content


@pytest.mark.anyio
async def test_max_iterations_prevents_infinite_loop() -> None:
    tool = MockTool("ejecutar_accion", ToolResult(status=200, data={}))
    responses = [
        _make_tool_call_response("ejecutar_accion", {"categoria": "test", "accion_solicitada": "loop"})
        for _ in range(10)
    ]
    llm = MockLLMProvider(responses)
    router = AgentRouter(llm=llm, tools=[tool])

    result = await router.run("Loop forever")

    assert "no pude completar" in result.response
    assert llm._call_count <= 5


@pytest.mark.anyio
async def test_tool_schemas_are_passed_to_llm() -> None:
    tool = MockTool("mi_tool", ToolResult(status=200, data={}))
    llm = MockLLMProvider([_make_text_response("ok")])
    router = AgentRouter(llm=llm, tools=[tool])

    await router.run("test")

    assert llm.calls[0]["tools"] is not None
    assert llm.calls[0]["tools"][0]["function"]["name"] == "mi_tool"


@pytest.mark.anyio
async def test_multiple_tools_available_correct_one_is_called() -> None:
    tool_info = MockTool("consultar_informacion_negocio", ToolResult(
        status=200, data={"info": "Estamos en Av. Principal 123"},
    ))
    tool_accion = MockTool("ejecutar_accion", ToolResult(status=200, data={}))
    llm = MockLLMProvider([
        _make_tool_call_response("consultar_informacion_negocio", {"consulta": "ubicación"}),
        _make_text_response("Estamos ubicados en Av. Principal 123."),
    ])
    router = AgentRouter(llm=llm, tools=[tool_info, tool_accion])

    result = await router.run("¿Dónde están ubicados?")

    assert len(tool_info.execute_calls) == 1
    assert len(tool_accion.execute_calls) == 0
    assert "123" in result.response

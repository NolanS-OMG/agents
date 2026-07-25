import pytest

from src.app.tools.base import ToolError, ToolResult
from src.app.tools.buscar_conocimiento import BuscarConocimiento
from src.app.tools.consultar_info_negocio import ConsultarInfoNegocio
from src.app.tools.ejecutar_accion import EjecutarAccion


@pytest.mark.anyio
async def test_ejecutar_accion_missing_categoria() -> None:
    tool = EjecutarAccion()
    result = await tool.execute(accion_solicitada="agendar cita")

    assert isinstance(result, ToolError)
    assert result.status == 400
    assert "categoria" in result.campos_faltantes


@pytest.mark.anyio
async def test_ejecutar_accion_missing_accion_solicitada() -> None:
    tool = EjecutarAccion()
    result = await tool.execute(categoria="agenda")

    assert isinstance(result, ToolError)
    assert result.status == 400
    assert "accion_solicitada" in result.campos_faltantes


@pytest.mark.anyio
async def test_ejecutar_accion_success() -> None:
    from src.app.services.tenant import load_tenant

    tenant = load_tenant("santa_lena")
    tool = EjecutarAccion(tenant=tenant)
    result = await tool.execute(
        categoria="reservacion",
        accion_solicitada="reservar mesa",
        parametros_extra={
            "nombre_cliente": "Juan",
            "telefono": "8112345678",
            "fecha": "2026-07-30",
            "hora": "20:00",
            "numero_personas": "4",
        },
    )

    assert isinstance(result, ToolResult)
    assert result.status == 200
    assert "registrada" in result.data["mensaje"]


@pytest.mark.anyio
async def test_consultar_info_negocio_returns_result() -> None:
    tool = ConsultarInfoNegocio()
    result = await tool.execute(consulta="horarios")

    assert isinstance(result, ToolResult)
    assert result.status == 200


@pytest.mark.anyio
async def test_buscar_conocimiento_returns_result() -> None:
    tool = BuscarConocimiento()
    result = await tool.execute(documentos=["menu/hamburguesas.md"])

    assert isinstance(result, ToolResult)
    assert result.status == 200
    assert result.data["contenido"] == ""


@pytest.mark.anyio
async def test_ejecutar_accion_schema_is_valid_openai_format() -> None:
    tool = EjecutarAccion()
    schema = tool.schema()

    assert schema["type"] == "function"
    assert "function" in schema
    assert schema["function"]["name"] == "ejecutar_accion"
    assert "parameters" in schema["function"]
    assert "categoria" in schema["function"]["parameters"]["properties"]


@pytest.mark.anyio
async def test_all_tools_have_consistent_schema_format() -> None:
    tools = [EjecutarAccion(), ConsultarInfoNegocio(), BuscarConocimiento()]

    for tool in tools:
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool.name
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"]["type"] == "object"

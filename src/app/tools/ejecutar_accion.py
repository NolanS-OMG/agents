from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.app.tools.base import BaseTool, ToolError, ToolResult

if TYPE_CHECKING:
    from src.app.services.tenant import TenantConfig


class EjecutarAccion(BaseTool):
    def __init__(self, tenant: TenantConfig | None = None) -> None:
        self._tenant = tenant

    @property
    def name(self) -> str:
        return "ejecutar_accion"

    @property
    def description(self) -> str:
        return (
            "Ejecuta acciones con efecto secundario: "
            "pedidos a domicilio, pedidos para recoger, reservaciones."
        )

    async def execute(self, **kwargs: Any) -> ToolResult | ToolError:
        categoria = kwargs.get("categoria")
        accion_solicitada = kwargs.get("accion_solicitada")
        parametros = kwargs.get("parametros_extra") or {}

        if not categoria or not accion_solicitada:
            return ToolError(
                error="MISSING_REQUIRED_FIELDS",
                categoria=categoria or "desconocida",
                campos_faltantes=[
                    f for f in ["categoria", "accion_solicitada"] if not kwargs.get(f)
                ],
                mensaje_sistema="Faltan datos requeridos para ejecutar la acción.",
            )

        accion_config = self._find_accion(categoria)
        if not accion_config:
            categorias_validas = [a["categoria"] for a in self._get_acciones()]
            return ToolError(
                error="CATEGORIA_NO_VALIDA",
                categoria=categoria,
                campos_faltantes=[],
                mensaje_sistema=f"Categoría '{categoria}' no existe. Válidas: {categorias_validas}",
            )

        campos_faltantes = [
            campo
            for campo in accion_config.get("campos_requeridos", [])
            if campo not in parametros or not parametros[campo]
        ]

        if campos_faltantes:
            return ToolError(
                error="MISSING_REQUIRED_FIELDS",
                categoria=categoria,
                campos_faltantes=campos_faltantes,
                campos_opcionales=accion_config.get("campos_opcionales", []),
                mensaje_sistema=f"Faltan datos para completar: {accion_config['nombre']}.",
            )

        return ToolResult(
            status=200,
            data={
                "mensaje": f"Acción '{accion_config['nombre']}' registrada exitosamente.",
                "categoria": categoria,
                "parametros": parametros,
                "confirmacion_requerida": accion_config.get("confirmacion_requerida", False),
            },
        )

    def _get_acciones(self) -> list[dict[str, Any]]:
        if not self._tenant:
            return []
        return self._tenant.get_acciones_config()

    def _find_accion(self, categoria: str) -> dict[str, Any] | None:
        for accion in self._get_acciones():
            if accion["categoria"] == categoria:
                return accion
        return None

    def schema(self) -> dict[str, Any]:
        categorias = [a["categoria"] for a in self._get_acciones()]
        cat_desc = (
            ", ".join(categorias)
            if categorias
            else "pedido_a_domicilio, pedido_recoger, reservacion"
        )

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "categoria": {
                            "type": "string",
                            "enum": categorias or None,
                            "description": f"Tipo de acción. Valores exactos: {cat_desc}",
                        },
                        "accion_solicitada": {
                            "type": "string",
                            "description": "Descripción de lo que el cliente quiere hacer",
                        },
                        "parametros_extra": {
                            "type": "object",
                            "description": "Datos del cliente: nombre, direccion, items, fecha, hora, num_personas, etc. El teléfono NO es necesario si ya se tiene del canal.",
                        },
                    },
                    "required": ["categoria", "accion_solicitada"],
                },
            },
        }

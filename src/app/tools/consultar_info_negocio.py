from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.app.tools.base import BaseTool, ToolResult

if TYPE_CHECKING:
    from src.app.services.tenant import TenantConfig


class ConsultarInfoNegocio(BaseTool):
    def __init__(self, tenant: TenantConfig | None = None) -> None:
        self._tenant = tenant

    @property
    def name(self) -> str:
        return "consultar_informacion_negocio"

    @property
    def description(self) -> str:
        return (
            "Provee información del negocio: "
            "menú, horarios, ubicación, políticas, promociones."
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        consulta = kwargs.get("consulta", "").lower()
        if not self._tenant:
            return ToolResult(status=200, data={"info": "Sin configuración de negocio."})

        if "menu" in consulta or "carta" in consulta or "platillo" in consulta:
            return ToolResult(status=200, data={"menu": self._tenant.get_menu_as_text()})

        if "horario" in consulta:
            horarios = self._tenant.negocio.get("horarios", {})
            return ToolResult(status=200, data={"horarios": horarios})

        if "ubicacion" in consulta or "direccion" in consulta or "donde" in consulta:
            return ToolResult(status=200, data={
                "direccion": self._tenant.negocio.get("direccion", ""),
                "telefono": self._tenant.negocio.get("telefono", ""),
            })

        if "promocion" in consulta or "oferta" in consulta or "descuento" in consulta:
            promos = self._tenant.negocio.get("promociones", [])
            return ToolResult(status=200, data={"promociones": promos})

        negocio = self._tenant.negocio
        return ToolResult(status=200, data={
            "nombre": negocio.get("nombre", ""),
            "descripcion": negocio.get("descripcion", ""),
            "horarios": negocio.get("horarios", {}),
            "direccion": negocio.get("direccion", ""),
            "telefono": negocio.get("telefono", ""),
            "promociones": negocio.get("promociones", []),
        })

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "consulta": {
                            "type": "string",
                            "description": "Qué consultar: menu, horarios, ubicacion, promociones, o general",
                        },
                    },
                    "required": ["consulta"],
                },
            },
        }

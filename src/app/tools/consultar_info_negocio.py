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
            return ToolResult(status=200, data={"info": self._tenant.get_menu_as_text()})

        if "horario" in consulta or "ubicacion" in consulta or "direccion" in consulta or "donde" in consulta:
            return ToolResult(status=200, data={"info": self._tenant.get_info_general()})

        if "promocion" in consulta or "oferta" in consulta or "descuento" in consulta:
            return ToolResult(status=200, data={"info": self._tenant.get_promociones()})

        return ToolResult(status=200, data={"info": self._tenant.get_info_general()})

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

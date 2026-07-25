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
            "Consulta información general del negocio que ya tienes en contexto: "
            "horarios, ubicación, contacto, promociones. Usa esta tool solo si "
            "necesitas confirmar un dato que no recuerdas del contexto."
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        consulta = kwargs.get("consulta", "")
        if not self._tenant:
            return ToolResult(status=200, data={"info": "Sin configuración."})

        doc = self._tenant.read_doc("negocio/info-general.md")
        promos = self._tenant.read_doc("negocio/promociones.md")
        contenido = f"{doc or ''}\n\n{promos or ''}"
        return ToolResult(status=200, data={"info": contenido, "consulta": consulta})

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
                            "description": "Qué dato necesitas verificar",
                        },
                    },
                    "required": ["consulta"],
                },
            },
        }

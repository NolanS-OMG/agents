from typing import Any

from src.app.tools.base import BaseTool, ToolResult


class ConsultarInfoNegocio(BaseTool):
    @property
    def name(self) -> str:
        return "consultar_informacion_negocio"

    @property
    def description(self) -> str:
        return (
            "Provee información estática del negocio: "
            "horarios, ubicaciones, políticas, servicios principales."
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        # TODO: load from OKF/structured config per tenant
        return ToolResult(
            status=200,
            data={"info": "Información del negocio no configurada aún."},
        )

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
                            "description": "Aspecto específico a consultar (horarios, ubicación, políticas, servicios)",
                        },
                    },
                    "required": ["consulta"],
                },
            },
        }

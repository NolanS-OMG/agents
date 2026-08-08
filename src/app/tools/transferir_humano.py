from typing import Any

from src.app.tools.base import BaseTool, ToolResult


class TransferirHumano(BaseTool):
    @property
    def name(self) -> str:
        return "transferir_a_humano"

    @property
    def description(self) -> str:
        return "Transfiere a un agente humano cuando el cliente está frustrado o el problema no se puede resolver."

    async def execute(self, **kwargs: Any) -> ToolResult:
        motivo = kwargs.get("motivo", "No especificado")
        return ToolResult(
            status=200,
            data={
                "mensaje": "Entendido, te transfiero con un agente humano. Te atenderán en breve.",
                "motivo": motivo,
            },
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
                        "motivo": {
                            "type": "string",
                            "description": "Razón de la transferencia",
                        },
                    },
                    "required": ["motivo"],
                },
            },
        }

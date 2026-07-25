from typing import Any

from src.app.tools.base import BaseTool, ToolError, ToolResult


class EjecutarAccion(BaseTool):
    @property
    def name(self) -> str:
        return "ejecutar_accion"

    @property
    def description(self) -> str:
        return (
            "Ejecuta acciones con efecto secundario: "
            "agendar citas, crear registros CRM, enviar notificaciones."
        )

    async def execute(self, **kwargs: Any) -> ToolResult | ToolError:
        categoria = kwargs.get("categoria")
        accion_solicitada = kwargs.get("accion_solicitada")

        if not categoria or not accion_solicitada:
            return ToolError(
                error="MISSING_REQUIRED_FIELDS",
                categoria=categoria or "desconocida",
                campos_faltantes=[
                    f for f in ["categoria", "accion_solicitada"]
                    if not kwargs.get(f)
                ],
                mensaje_sistema="Faltan datos requeridos para ejecutar la acción.",
            )

        # TODO: dispatch to sub-workflow based on categoria
        return ToolResult(
            status=200,
            data={"mensaje": f"Acción '{accion_solicitada}' en categoría '{categoria}' recibida."},
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
                        "categoria": {
                            "type": "string",
                            "description": "Clasificación: agenda, crm, pagos, notificaciones",
                        },
                        "accion_solicitada": {
                            "type": "string",
                            "description": "Descripción textual del requerimiento del cliente",
                        },
                        "parametros_extra": {
                            "type": "object",
                            "description": "Datos adicionales extraídos de la conversación",
                        },
                    },
                    "required": ["categoria", "accion_solicitada"],
                },
            },
        }

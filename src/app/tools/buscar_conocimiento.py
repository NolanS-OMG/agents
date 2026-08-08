from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.app.tools.base import BaseTool, ToolResult

if TYPE_CHECKING:
    from src.app.services.tenant import TenantConfig


class BuscarConocimiento(BaseTool):
    def __init__(self, tenant: TenantConfig | None = None) -> None:
        self._tenant = tenant

    @property
    def name(self) -> str:
        return "buscar_base_conocimiento_extensa"

    @property
    def description(self) -> str:
        return (
            "Lee documentos por slug. Usa siempre antes de responder sobre platillos específicos."
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        rutas = kwargs.get("documentos", [])
        if not self._tenant or not rutas:
            return ToolResult(status=200, data={"contenido": ""})

        contenidos: dict[str, str] = {}
        for ruta in rutas:
            doc = self._tenant.read_doc(ruta)
            contenidos[ruta] = doc if doc else f"[Documento '{ruta}' no encontrado]"

        return ToolResult(status=200, data={"contenido": contenidos})

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "documentos": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Rutas de documentos a leer (ej: ['menu/hamburguesas.md', 'menu/pizzas.md'])",
                        },
                    },
                    "required": ["documentos"],
                },
            },
        }

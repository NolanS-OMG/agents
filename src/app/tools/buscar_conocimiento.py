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
            "Busca en el menú y catálogo completo del negocio. "
            "Útil para encontrar platillos por nombre, ingrediente o categoría."
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        if not self._tenant:
            return ToolResult(status=200, data={"resultados": [], "query": query})

        resultados = self._tenant.search_menu(query)
        return ToolResult(status=200, data={"resultados": resultados, "query": query})

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Búsqueda: nombre de platillo, ingrediente, o categoría",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

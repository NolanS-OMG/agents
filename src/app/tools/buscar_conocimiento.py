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
        query = kwargs.get("query", "").lower()
        if not self._tenant:
            return ToolResult(status=200, data={"resultados": [], "query": query})

        resultados = self._search_menu(query)
        return ToolResult(status=200, data={"resultados": resultados, "query": query})

    def _search_menu(self, query: str) -> list[dict[str, Any]]:
        if not self._tenant:
            return []
        resultados: list[dict[str, Any]] = []
        for seccion, contenido in self._tenant.menu.items():
            items = self._extract_items(contenido)
            for item in items:
                nombre = item.get("nombre", "").lower()
                desc = item.get("descripcion", "").lower()
                if query in nombre or query in desc:
                    resultados.append({**item, "seccion": seccion})
        return resultados[:10]

    def _extract_items(self, contenido: Any) -> list[dict[str, Any]]:
        if isinstance(contenido, list):
            return contenido
        if isinstance(contenido, dict):
            items: list[dict[str, Any]] = []
            for key in ("items", "especialidades", "res", "pollo", "samplers",
                        "aguas_frescas", "cervezas", "cocteles", "vinos"):
                if key in contenido:
                    items.extend(contenido[key])
            return items
        return []

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

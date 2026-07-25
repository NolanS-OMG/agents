from typing import Any

from src.app.tools.base import BaseTool, ToolResult


class BuscarConocimiento(BaseTool):
    @property
    def name(self) -> str:
        return "buscar_base_conocimiento_extensa"

    @property
    def description(self) -> str:
        return (
            "Busca en bases de datos extensas, catálogos o documentación técnica "
            "usando búsqueda híbrida (keyword + embeddings vectoriales)."
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        # TODO: implement RAG pipeline (vector search + keyword)
        return ToolResult(
            status=200,
            data={"resultados": [], "query": query},
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
                        "query": {
                            "type": "string",
                            "description": "Consulta de búsqueda en lenguaje natural",
                        },
                        "categoria": {
                            "type": "string",
                            "description": "Filtro opcional por categoría de documento",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

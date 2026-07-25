from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    status: int
    data: dict[str, Any] = {}
    error: str | None = None


class ToolError(BaseModel):
    status: int = 400
    error: str
    categoria: str
    campos_faltantes: list[str] = []
    campos_opcionales: list[str] = []
    mensaje_sistema: str


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult | ToolError: ...

    @abstractmethod
    def schema(self) -> dict[str, Any]: ...

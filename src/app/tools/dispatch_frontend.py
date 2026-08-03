from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.app.channels.base import Channel
from src.app.tools.base import BaseTool, ToolError, ToolResult

if TYPE_CHECKING:
    from src.app.services.tenant import TenantConfig


class DispatchFrontend(BaseTool):
    def __init__(self, tenant: TenantConfig | None = None, channel: Channel = Channel.WEB) -> None:
        self._tenant = tenant
        self._channel = channel

    @property
    def name(self) -> str:
        return "dispatch_frontend"

    @property
    def description(self) -> str:
        acciones = self._get_frontend_acciones()
        if acciones:
            triggers = " ".join(
                f"{a['nombre']} → action='{a['categoria']}'." for a in acciones
            )
        else:
            triggers = ""

        return (
            "Dispatches a visual/interactive action to the user's browser. "
            "WHEN TO USE (mandatory, not optional): "
            "whenever your response discusses content that has a visual representation, "
            "you MUST call this tool to enrich the user experience. "
            f"Available actions: {triggers} "
            "IMPORTANT: A response that discusses a project without showing it visually "
            "is INCOMPLETE. Call this tool ALONGSIDE your text response. "
            "Do NOT wait for the user to explicitly ask 'show me' — trigger proactively "
            "when contextually relevant."
        )

    async def execute(self, **kwargs: Any) -> ToolResult | ToolError:
        action = kwargs.get("action")

        if not action:
            return ToolError(
                error="MISSING_ACTION",
                categoria="dispatch_frontend",
                campos_faltantes=["action"],
                mensaje_sistema="Missing required field: action.",
            )

        accion_config = self._find_accion(action)
        if not accion_config:
            valid_actions = [a["categoria"] for a in self._get_frontend_acciones()]
            return ToolError(
                error="INVALID_ACTION",
                categoria=action,
                campos_faltantes=[],
                mensaje_sistema=f"Action '{action}' not valid. Options: {valid_actions}",
            )

        args = kwargs.get("args") or {}

        campos_faltantes = [
            campo
            for campo in accion_config.get("campos_requeridos", [])
            if campo not in args or not args[campo]
        ]

        if campos_faltantes:
            return ToolError(
                error="MISSING_REQUIRED_FIELDS",
                categoria=action,
                campos_faltantes=campos_faltantes,
                mensaje_sistema=f"Missing required args: {campos_faltantes}",
            )

        return ToolResult(
            status=200,
            data={
                "status": "dispatched",
                "frontend_tool": accion_config.get("frontend_tool", action),
                "args": args,
            },
        )

    def _get_frontend_acciones(self) -> list[dict[str, Any]]:
        if not self._tenant:
            return []
        all_acciones = self._tenant.get_acciones_config()
        return [
            a for a in all_acciones
            if a.get("frontend_action", False)
            and self._channel.value in a.get("channels", ["web", "whatsapp", "call"])
        ]

    def _find_accion(self, action: str) -> dict[str, Any] | None:
        for accion in self._get_frontend_acciones():
            if accion["categoria"] == action:
                return accion
        return None

    def schema(self) -> dict[str, Any]:
        acciones = self._get_frontend_acciones()
        action_enum = [a["categoria"] for a in acciones]

        action_prop: dict[str, Any] = {
            "type": "string",
            "description": "Frontend action to trigger",
        }
        if action_enum:
            action_prop["enum"] = action_enum

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": action_prop,
                        "args": {
                            "type": "object",
                            "description": (
                                "Arguments for the action: "
                                "ids (array of project IDs), section (string), etc."
                            ),
                        },
                    },
                    "required": ["action"],
                },
            },
        }

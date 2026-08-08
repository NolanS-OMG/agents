from src.app.channels.base import Channel
from src.app.services.tenant import TenantConfig
from src.app.tools.base import BaseTool
from src.app.tools.buscar_conocimiento import BuscarConocimiento
from src.app.tools.dispatch_frontend import DispatchFrontend
from src.app.tools.ejecutar_accion import EjecutarAccion
from src.app.tools.transferir_humano import TransferirHumano


def get_tools_for_tenant(tenant: TenantConfig, channel: Channel = Channel.WEB) -> list[BaseTool]:
    tools: list[BaseTool] = []
    enabled = tenant.enabled_tools

    if "ejecutar_accion" in enabled:
        tools.append(EjecutarAccion(tenant=tenant, channel=channel))
    if "dispatch_frontend" in enabled:
        tools.append(DispatchFrontend(tenant=tenant, channel=channel))

    tools.append(BuscarConocimiento(tenant=tenant))
    tools.append(TransferirHumano())
    return tools

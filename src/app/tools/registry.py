from src.app.channels.base import Channel
from src.app.services.tenant import TenantConfig
from src.app.tools.base import BaseTool
from src.app.tools.buscar_conocimiento import BuscarConocimiento
from src.app.tools.consultar_info_negocio import ConsultarInfoNegocio
from src.app.tools.ejecutar_accion import EjecutarAccion
from src.app.tools.transferir_humano import TransferirHumano


def get_tools_for_tenant(tenant: TenantConfig, channel: Channel = Channel.WEB) -> list[BaseTool]:
    return [
        EjecutarAccion(tenant=tenant, channel=channel),
        ConsultarInfoNegocio(tenant=tenant),
        BuscarConocimiento(tenant=tenant),
        TransferirHumano(),
    ]

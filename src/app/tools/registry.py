from src.app.services.tenant import TenantConfig
from src.app.tools.base import BaseTool
from src.app.tools.buscar_conocimiento import BuscarConocimiento
from src.app.tools.consultar_info_negocio import ConsultarInfoNegocio
from src.app.tools.ejecutar_accion import EjecutarAccion


def get_tools_for_tenant(tenant: TenantConfig) -> list[BaseTool]:
    return [
        EjecutarAccion(tenant=tenant),
        ConsultarInfoNegocio(tenant=tenant),
        BuscarConocimiento(tenant=tenant),
    ]

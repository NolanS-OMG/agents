from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Request


@dataclass
class TenantContext:
    tenant_id: str
    tenant_name: str
    scopes: list[str] = field(default_factory=list)


async def get_current_tenant(request: Request) -> TenantContext:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="API key required")
    return TenantContext(
        tenant_id=request.state.tenant_id,
        tenant_name=request.state.tenant_name,
        scopes=request.state.api_key_scopes,
    )


CurrentTenant = Annotated[TenantContext, Depends(get_current_tenant)]

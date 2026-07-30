from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.api.deps import CurrentTenant
from src.app.db.models import TenantPrompt
from src.app.services.tenant_loader import invalidate_tenant_cache

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


class CreatePromptRequest(BaseModel):
    estilo: str = Field(min_length=1, max_length=50)
    system_prompt: str = Field(min_length=1)
    tono: str = ""
    formato: str = ""
    vocabulario: str = ""
    ejemplos: str = ""
    restricciones: str = ""


class UpdatePromptRequest(BaseModel):
    system_prompt: str | None = None
    tono: str | None = None
    formato: str | None = None
    vocabulario: str | None = None
    ejemplos: str | None = None
    restricciones: str | None = None


class PromptResponse(BaseModel):
    estilo: str
    system_prompt: str
    tono: str
    formato: str
    vocabulario: str
    ejemplos: str
    restricciones: str
    active: bool


@router.post("", response_model=PromptResponse, status_code=201)
async def create_prompt(request: Request, tenant: CurrentTenant, body: CreatePromptRequest) -> Any:
    existing = await TenantPrompt.get_or_none(tenant_id=tenant.tenant_id, estilo=body.estilo)
    if existing:
        raise HTTPException(409, f"Prompt '{body.estilo}' already exists")

    prompt = await TenantPrompt.create(
        tenant_id=tenant.tenant_id,
        estilo=body.estilo,
        system_prompt=body.system_prompt,
        tono=body.tono,
        formato=body.formato,
        vocabulario=body.vocabulario,
        ejemplos=body.ejemplos,
        restricciones=body.restricciones,
    )
    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)
    return _prompt_to_response(prompt)


@router.get("", response_model=list[PromptResponse])
async def list_prompts(tenant: CurrentTenant) -> Any:
    prompts = await TenantPrompt.filter(tenant_id=tenant.tenant_id, active=True).all()
    return [_prompt_to_response(p) for p in prompts]


@router.get("/{estilo}", response_model=PromptResponse)
async def get_prompt(tenant: CurrentTenant, estilo: str) -> Any:
    prompt = await TenantPrompt.get_or_none(tenant_id=tenant.tenant_id, estilo=estilo)
    if not prompt:
        raise HTTPException(404, f"Prompt '{estilo}' not found")
    return _prompt_to_response(prompt)


@router.put("/{estilo}", response_model=PromptResponse)
async def update_prompt(
    request: Request, tenant: CurrentTenant, estilo: str, body: UpdatePromptRequest
) -> Any:
    prompt = await TenantPrompt.get_or_none(tenant_id=tenant.tenant_id, estilo=estilo)
    if not prompt:
        raise HTTPException(404, f"Prompt '{estilo}' not found")

    update_data = body.model_dump(exclude_none=True)
    if update_data:
        for field, value in update_data.items():
            setattr(prompt, field, value)
        await prompt.save(update_fields=list(update_data.keys()))

    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)
    return _prompt_to_response(prompt)


@router.delete("/{estilo}", status_code=204)
async def delete_prompt(request: Request, tenant: CurrentTenant, estilo: str) -> None:
    prompt = await TenantPrompt.get_or_none(tenant_id=tenant.tenant_id, estilo=estilo)
    if not prompt:
        raise HTTPException(404, f"Prompt '{estilo}' not found")
    prompt.active = False
    await prompt.save(update_fields=["active"])
    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)


def _prompt_to_response(prompt: TenantPrompt) -> PromptResponse:
    return PromptResponse(
        estilo=prompt.estilo,
        system_prompt=prompt.system_prompt,
        tono=prompt.tono,
        formato=prompt.formato,
        vocabulario=prompt.vocabulario,
        ejemplos=prompt.ejemplos,
        restricciones=prompt.restricciones,
        active=prompt.active,
    )

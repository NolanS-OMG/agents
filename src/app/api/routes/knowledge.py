from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.api.deps import CurrentTenant
from src.app.db.models import KnowledgeDocument
from src.app.services.tenant_loader import invalidate_tenant_cache

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class CreateDocRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9_\-/]*[a-z0-9]$")
    doc_type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    body: str = Field(min_length=1)
    tags: list[str] = []
    campos_requeridos: list[str] = []
    campos_opcionales: list[str] = []
    confirmacion_requerida: bool = False


class UpdateDocRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    campos_requeridos: list[str] | None = None
    campos_opcionales: list[str] | None = None
    confirmacion_requerida: bool | None = None


class DocResponse(BaseModel):
    slug: str
    doc_type: str
    title: str
    description: str
    body: str
    tags: list[str]
    status: str
    campos_requeridos: list[str]
    campos_opcionales: list[str]
    confirmacion_requerida: bool


@router.post("", response_model=DocResponse, status_code=201)
async def create_document(request: Request, tenant: CurrentTenant, body: CreateDocRequest) -> Any:
    existing = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=body.slug)
    if existing:
        raise HTTPException(409, f"Document '{body.slug}' already exists")

    doc = await KnowledgeDocument.create(
        tenant_id=tenant.tenant_id,
        slug=body.slug,
        doc_type=body.doc_type,
        title=body.title,
        description=body.description,
        body=body.body,
        tags=body.tags,
        campos_requeridos=body.campos_requeridos,
        campos_opcionales=body.campos_opcionales,
        confirmacion_requerida=body.confirmacion_requerida,
    )
    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)
    return _doc_to_response(doc)


@router.get("", response_model=list[DocResponse])
async def list_documents(
    tenant: CurrentTenant,
    doc_type: str | None = None,
    status: str = "stable",
) -> Any:
    filters: dict[str, Any] = {"tenant_id": tenant.tenant_id, "status": status}
    if doc_type:
        filters["doc_type"] = doc_type
    docs = await KnowledgeDocument.filter(**filters).all()
    return [_doc_to_response(d) for d in docs]


@router.get("/{slug:path}", response_model=DocResponse)
async def get_document(tenant: CurrentTenant, slug: str) -> Any:
    if not slug:
        raise HTTPException(400, "Slug is required")
    doc = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=slug)
    if not doc:
        raise HTTPException(404, f"Document '{slug}' not found")
    return _doc_to_response(doc)


@router.put("/{slug:path}", response_model=DocResponse)
async def update_document(
    request: Request, tenant: CurrentTenant, slug: str, body: UpdateDocRequest
) -> Any:
    doc = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=slug)
    if not doc:
        raise HTTPException(404, f"Document '{slug}' not found")

    update_data = body.model_dump(exclude_none=True)
    if update_data:
        for field, value in update_data.items():
            setattr(doc, field, value)
        await doc.save(update_fields=list(update_data.keys()))

    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)
    return _doc_to_response(doc)


@router.delete("/{slug:path}", status_code=204)
async def delete_document(request: Request, tenant: CurrentTenant, slug: str) -> None:
    doc = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=slug)
    if not doc:
        raise HTTPException(404, f"Document '{slug}' not found")
    doc.status = "archived"
    await doc.save(update_fields=["status"])
    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)


def _doc_to_response(doc: KnowledgeDocument) -> DocResponse:
    return DocResponse(
        slug=doc.slug,
        doc_type=doc.doc_type,
        title=doc.title,
        description=doc.description,
        body=doc.body,
        tags=doc.tags,
        status=doc.status,
        campos_requeridos=doc.campos_requeridos,
        campos_opcionales=doc.campos_opcionales,
        confirmacion_requerida=doc.confirmacion_requerida,
    )

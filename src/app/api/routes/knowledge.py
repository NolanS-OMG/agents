import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.app.api.deps import CurrentTenant
from src.app.db.models import KnowledgeDocument
from src.app.services.tenant_loader import invalidate_tenant_cache
from src.app.utils.file_parsers import (
    calculate_file_hash,
    parse_markdown_frontmatter,
    write_markdown_with_frontmatter,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage" / "knowledge"

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
    logger.info(f"Creating document: tenant={tenant.tenant_id}, slug={body.slug}")
    existing = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=body.slug)
    if existing:
        raise HTTPException(409, f"Document '{body.slug}' already exists")

    file_path = STORAGE_DIR / tenant.tenant_id / f"{body.slug}.md"
    logger.info(f"File path: {file_path}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directory created/verified: {file_path.parent}")

    frontmatter = {
        "slug": body.slug,
        "doc_type": body.doc_type,
        "title": body.title,
        "description": body.description,
        "tags": body.tags,
        "status": "stable",
    }
    if body.doc_type == "accion":
        frontmatter["campos_requeridos"] = body.campos_requeridos
        frontmatter["campos_opcionales"] = body.campos_opcionales
        frontmatter["confirmacion_requerida"] = body.confirmacion_requerida

    content = write_markdown_with_frontmatter(frontmatter, body.body)
    logger.info(f"Writing {len(content)} chars to {file_path}")
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"File written successfully")
    file_hash = calculate_file_hash(file_path)
    relative_path = str(file_path.relative_to(PROJECT_ROOT))
    logger.info(f"Relative path: {relative_path}, hash: {file_hash[:16]}...")

    doc = await KnowledgeDocument.create(
        tenant_id=tenant.tenant_id,
        slug=body.slug,
        doc_type=body.doc_type,
        title=body.title,
        description=body.description,
        file_path=relative_path,
        file_format="md",
        file_hash=file_hash,
        tags=body.tags,
        campos_requeridos=body.campos_requeridos,
        campos_opcionales=body.campos_opcionales,
        confirmacion_requerida=body.confirmacion_requerida,
    )
    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)
    return _doc_to_response(doc, file_path)


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
    return [_doc_to_response(d, None) for d in docs]


@router.get("/{slug:path}", response_model=DocResponse)
async def get_document(tenant: CurrentTenant, slug: str) -> Any:
    if not slug:
        raise HTTPException(400, "Slug is required")
    doc = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=slug)
    if not doc:
        raise HTTPException(404, f"Document '{slug}' not found")
    return _doc_to_response(doc, None)


@router.put("/{slug:path}", response_model=DocResponse)
async def update_document(
    request: Request, tenant: CurrentTenant, slug: str, body: UpdateDocRequest
) -> Any:
    doc = await KnowledgeDocument.get_or_none(tenant_id=tenant.tenant_id, slug=slug)
    if not doc:
        raise HTTPException(404, f"Document '{slug}' not found")

    file_path = PROJECT_ROOT / doc.file_path
    if not file_path.exists():
        raise HTTPException(500, f"Document file not found: {doc.file_path}")

    raw_content = file_path.read_text(encoding="utf-8")
    frontmatter, current_body = parse_markdown_frontmatter(raw_content)

    update_data = body.model_dump(exclude_none=True)
    db_updates = {}

    if "body" in update_data:
        current_body = update_data.pop("body")

    for field, value in update_data.items():
        frontmatter[field] = value
        db_updates[field] = value

    new_content = write_markdown_with_frontmatter(frontmatter, current_body)
    file_path.write_text(new_content, encoding="utf-8")
    file_hash = calculate_file_hash(file_path)
    db_updates["file_hash"] = file_hash

    if db_updates:
        for field, value in db_updates.items():
            setattr(doc, field, value)
        await doc.save(update_fields=list(db_updates.keys()))

    redis = getattr(request.app.state, "redis", None)
    if redis:
        await invalidate_tenant_cache(tenant.tenant_id, redis)
    return _doc_to_response(doc, file_path)


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


def _doc_to_response(doc: KnowledgeDocument, file_path: Path | None = None) -> DocResponse:
    if file_path is None:
        file_path = PROJECT_ROOT / doc.file_path

    body = ""
    if file_path.exists():
        _, body = parse_markdown_frontmatter(file_path.read_text(encoding="utf-8"))

    return DocResponse(
        slug=doc.slug,
        doc_type=doc.doc_type,
        title=doc.title,
        description=doc.description,
        body=body,
        tags=doc.tags,
        status=doc.status,
        campos_requeridos=doc.campos_requeridos,
        campos_opcionales=doc.campos_opcionales,
        confirmacion_requerida=doc.confirmacion_requerida,
    )

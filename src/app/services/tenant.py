from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from src.app.db.models import KnowledgeDocument, TenantPrompt

logger = logging.getLogger(__name__)

TENANTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "tenants"


class OKFDocument:
    """Legacy filesystem document parser (for migration script)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        raw = path.read_text(encoding="utf-8")
        self.frontmatter, self.body = self._parse(raw)

    @property
    def type(self) -> str:
        return str(self.frontmatter.get("type", ""))

    @property
    def title(self) -> str:
        return str(self.frontmatter.get("title", ""))

    def _parse(self, raw: str) -> tuple[dict[str, Any], str]:
        if not raw.startswith("---"):
            return {}, raw
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return {}, raw
        fm = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return fm, body


class TenantConfig:
    """Tenant configuration — loads from DB or filesystem fallback."""

    def __init__(
        self,
        tenant_id: str,
        docs: list[KnowledgeDocument] | list[OKFDocument] | None = None,
        prompts: list[TenantPrompt] | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.docs = docs or []
        self.prompts = prompts or []
        self._is_legacy = len(self.docs) > 0 and isinstance(self.docs[0], OKFDocument)

    @classmethod
    def from_filesystem(cls, tenant_id: str) -> TenantConfig:
        """Legacy loader for filesystem-based tenants."""
        path = TENANTS_DIR / tenant_id
        docs_raw: list[OKFDocument] = []
        if path.exists():
            for md_file in path.rglob("*.md"):
                if md_file.name in ("log.md",):
                    continue
                try:
                    docs_raw.append(OKFDocument(md_file))
                except Exception as e:
                    logger.warning(f"Error loading {md_file}: {e}")
        return cls(tenant_id=tenant_id, docs=docs_raw, prompts=[])

    @property
    def index(self) -> str:
        if self._is_legacy:
            doc = self._find_doc_by_path_legacy("index.md")
            return doc.body if doc else ""
        lines = ["# Índice de Documentos\n"]
        for doc in self.docs:
            if doc.doc_type != "negocio":
                lines.append(f"- [{doc.title}]({doc.slug}.md)")
        return "\n".join(lines)

    @property
    def negocio(self) -> dict[str, Any]:
        if self._is_legacy:
            doc = self._find_doc_legacy("Negocio")
            return doc.frontmatter if doc else {}
        for doc in self.docs:
            if doc.doc_type == "negocio":
                return {"title": doc.title, "description": doc.description}
        return {}

    @property
    def prompt(self) -> str:
        return self.get_prompt()

    def get_prompt(self, estilo: str = "chat") -> str:
        parts: list[str] = []

        if self._is_legacy:
            info = self._find_doc_legacy("Negocio")
            promos = self._find_doc_legacy("Promociones")
            if info:
                parts.append(info.body)
            if promos:
                parts.append(promos.body)
            parts.append(f"\nÍNDICE DE DOCUMENTOS DISPONIBLES:\n{self.index}")
            estilo_doc = self._find_estilo_legacy(estilo)
            if estilo_doc:
                parts.append(f"\nESTILO DE COMUNICACIÓN:\n{estilo_doc.body}")
        else:
            negocio_doc = next((d for d in self.docs if d.doc_type == "negocio"), None)
            if negocio_doc:
                content = self.read_doc(negocio_doc.slug)
                if content:
                    parts.append(content)
            promo_doc = next((d for d in self.docs if d.doc_type == "promociones"), None)
            if promo_doc:
                content = self.read_doc(promo_doc.slug)
                if content:
                    parts.append(content)
            parts.append(f"\nÍNDICE DE DOCUMENTOS DISPONIBLES:\n{self.index}")
            prompt = next((p for p in self.prompts if p.estilo == estilo), None)
            if prompt:
                parts.append(f"\nESTILO DE COMUNICACIÓN:\n{prompt.system_prompt}")

        return "\n\n".join(parts)

    def read_doc(self, ruta: str) -> str | None:
        if self._is_legacy:
            doc = self._find_doc_by_path_legacy(ruta)
            return doc.body if doc else None
        slug = ruta.removesuffix(".md")
        for doc in self.docs:
            if doc.slug == slug:
                file_path = Path(doc.file_path)
                if not file_path.exists():
                    logger.error(f"File not found: {file_path}")
                    return None
                return self._read_file_content(file_path, doc.file_format)
        return None

    def _read_file_content(self, path: Path, format: str) -> str:
        if format == "md":
            raw = path.read_text(encoding="utf-8")
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return raw
        if format == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return str(data.get("body", ""))
        if format == "yaml":
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return str(data.get("body", ""))
        return ""

    def get_acciones_config(self) -> list[dict[str, Any]]:
        acciones: list[dict[str, Any]] = []
        if self._is_legacy:
            for doc in self.docs:
                if doc.type != "Acción":
                    continue
                campos_req = self._extract_table_column(doc.body, "Campos requeridos", 0)
                campos_opt = self._extract_table_column(doc.body, "Campos opcionales", 0)
                categoria = self._slug_from_title(doc.title)
                acciones.append(
                    {
                        "categoria": categoria,
                        "nombre": doc.title,
                        "campos_requeridos": campos_req,
                        "campos_opcionales": campos_opt,
                        "confirmacion_requerida": "confirmación" in doc.body.lower(),
                    }
                )
        else:
            for doc in self.docs:
                if doc.doc_type != "accion":
                    continue
                categoria = self._slug_from_title(doc.title)
                acciones.append(
                    {
                        "categoria": categoria,
                        "nombre": doc.title,
                        "campos_requeridos": doc.campos_requeridos,
                        "campos_opcionales": doc.campos_opcionales,
                        "confirmacion_requerida": doc.confirmacion_requerida,
                        "channels": getattr(doc, "channels", ["web", "whatsapp", "call"]),
                        "frontend_action": getattr(doc, "frontend_action", False),
                    }
                )
        return acciones

    def _find_doc_legacy(self, type_: str) -> OKFDocument | None:
        for doc in self.docs:
            if doc.type == type_:
                return doc
        return None

    def _find_doc_by_path_legacy(self, ruta: str) -> OKFDocument | None:
        target = TENANTS_DIR / self.tenant_id / ruta
        for doc in self.docs:
            if doc.path == target:
                return doc
        return None

    def _find_estilo_legacy(self, estilo: str) -> OKFDocument | None:
        for doc in self.docs:
            if doc.type == "Estilo" and estilo in doc.path.stem:
                return doc
        return None

    @staticmethod
    def _extract_table_column(body: str, section: str, col: int) -> list[str]:
        in_section = False
        values: list[str] = []
        for line in body.split("\n"):
            if section.lower() in line.lower() and "#" in line:
                in_section = True
                continue
            if in_section and line.startswith("#"):
                break
            if in_section and "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) > col and not cells[col].startswith("-"):
                    val = cells[col]
                    if val != "Campo":
                        values.append(val)
        return values

    @staticmethod
    def _slug_from_title(title: str) -> str:
        normalized = unicodedata.normalize("NFKD", title)
        ascii_str = normalized.encode("ascii", "ignore").decode()
        return ascii_str.lower().replace(" ", "_")


def load_tenant(tenant_id: str) -> TenantConfig:
    """Sync loader — filesystem only (backward compat)."""
    return TenantConfig.from_filesystem(tenant_id)

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

TENANTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "tenants"


class OKFDocument:
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
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self._path = TENANTS_DIR / tenant_id
        self._docs: list[OKFDocument] = []
        self._load_all_docs()

    def _load_all_docs(self) -> None:
        for md_file in self._path.rglob("*.md"):
            if md_file.name in ("log.md",):
                continue
            self._docs.append(OKFDocument(md_file))

    @property
    def index(self) -> str:
        doc = self._find_doc_by_path("index.md")
        return doc.body if doc else ""

    @property
    def negocio(self) -> dict[str, Any]:
        doc = self._find_doc(type_="Negocio")
        if not doc:
            return {}
        return doc.frontmatter

    def get_prompt(self, estilo: str = "chat") -> str:
        estilo_doc = self._find_estilo(estilo)
        info = self._find_doc(type_="Negocio")
        promos = self._find_doc(type_="Promociones")
        parts: list[str] = []
        if estilo_doc:
            parts.append(estilo_doc.body)
        if info:
            parts.append(info.body)
        if promos:
            parts.append(promos.body)
        parts.append(f"\nÍNDICE DE DOCUMENTOS DISPONIBLES:\n{self.index}")
        return "\n\n".join(parts)

    @property
    def prompt(self) -> str:
        return self.get_prompt()

    def read_doc(self, ruta: str) -> str | None:
        doc = self._find_doc_by_path(ruta)
        return doc.body if doc else None

    def get_acciones_config(self) -> list[dict[str, Any]]:
        acciones: list[dict[str, Any]] = []
        for doc in self._docs:
            if doc.type != "Acción":
                continue
            campos_req = self._extract_table_column(doc.body, "Campos requeridos", 0)
            campos_opt = self._extract_table_column(doc.body, "Campos opcionales", 0)
            categoria = self._slug_from_title(doc.title)
            acciones.append({
                "categoria": categoria,
                "nombre": doc.title,
                "campos_requeridos": campos_req,
                "campos_opcionales": campos_opt,
                "confirmacion_requerida": "confirmación" in doc.body.lower(),
            })
        return acciones

    def _find_doc(self, type_: str) -> OKFDocument | None:
        for doc in self._docs:
            if doc.type == type_:
                return doc
        return None

    def _find_doc_by_path(self, ruta: str) -> OKFDocument | None:
        target = self._path / ruta
        for doc in self._docs:
            if doc.path == target:
                return doc
        return None

    def _find_estilo(self, estilo: str) -> OKFDocument | None:
        for doc in self._docs:
            if doc.type == "Estilo" and estilo in doc.path.stem:
                return doc
        return None

    def _extract_table_column(self, body: str, section: str, col: int) -> list[str]:
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

    def _slug_from_title(self, title: str) -> str:
        return title.lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("ó", "o")


def load_tenant(tenant_id: str) -> TenantConfig:
    return TenantConfig(tenant_id)

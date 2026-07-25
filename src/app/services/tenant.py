from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

TENANTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "tenants"


class TenantConfig:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self._path = TENANTS_DIR / tenant_id
        self.negocio = self._load_yaml("negocio.yaml")
        self.menu = self._load_yaml("menu.yaml")
        self.acciones = self._load_yaml("acciones.yaml")
        self.prompt = self._load_text("prompt.md")

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        filepath = self._path / filename
        if not filepath.exists():
            return {}
        with open(filepath) as f:
            return yaml.safe_load(f) or {}

    def _load_text(self, filename: str) -> str:
        filepath = self._path / filename
        if not filepath.exists():
            return ""
        return filepath.read_text()

    def get_menu_as_text(self) -> str:
        lines: list[str] = []
        for seccion, contenido in self.menu.items():
            lines.append(f"\n## {seccion.upper().replace('_', ' ')}")
            if isinstance(contenido, list):
                for item in contenido:
                    lines.append(self._format_item(item))
            elif isinstance(contenido, dict):
                if "nota" in contenido:
                    lines.append(f"  ({contenido['nota']})")
                if "items" in contenido:
                    for item in contenido["items"]:
                        lines.append(self._format_item(item))
                if "especialidades" in contenido:
                    lines.append("  Especialidades:")
                    for item in contenido["especialidades"]:
                        lines.append(self._format_item(item))
                if "arma_tu_pizza" in contenido:
                    p = contenido["arma_tu_pizza"]
                    lines.append(
                        f"  Arma tu pizza: 14\" ${p['precio_14']} / 8\" ${p['precio_8']}"
                    )
                if "res" in contenido:
                    lines.append("  Res:")
                    for item in contenido["res"]:
                        lines.append(self._format_item(item))
                if "pollo" in contenido:
                    lines.append("  Pollo:")
                    for item in contenido["pollo"]:
                        lines.append(self._format_item(item))
                if "salsas" in contenido:
                    lines.append(f"  Salsas: {', '.join(contenido['salsas'])}")
                if "samplers" in contenido:
                    for item in contenido["samplers"]:
                        lines.append(self._format_item(item))
                if "refrescos" in contenido:
                    r = contenido["refrescos"]
                    lines.append(f"  Refrescos (${r['precio']}): {', '.join(r['opciones'])}")
                if "aguas_frescas" in contenido:
                    for item in contenido["aguas_frescas"]:
                        lines.append(self._format_item(item))
                if "cervezas" in contenido:
                    lines.append("  Cervezas:")
                    for item in contenido["cervezas"]:
                        u = item.get("precio_unidad", "")
                        c = item.get("precio_cubeta", "")
                        lines.append(f"  - {item['nombre']}: ${u} c/u / ${c} cubeta")
                if "cocteles" in contenido:
                    for item in contenido["cocteles"]:
                        lines.append(self._format_item(item))
                if "litros" in contenido:
                    lt = contenido["litros"]
                    lines.append(f"  Litros (${lt['precio']}): {', '.join(lt['opciones'])}")
                if "vinos" in contenido:
                    for item in contenido["vinos"]:
                        lines.append(self._format_item(item))
        return "\n".join(lines)

    def _format_item(self, item: dict[str, Any]) -> str:
        nombre = item.get("nombre", "")
        desc = item.get("descripcion", "")
        precio = item.get("precio", "")
        peso = item.get("peso", "")
        p14 = item.get("precio_14", "")
        p8 = item.get("precio_8", "")
        pp = item.get("precio_pollo", "")
        pc = item.get("precio_camaron", "")

        parts = [f"  - {nombre}"]
        if peso:
            parts[0] += f" ({peso})"
        if precio:
            parts[0] += f" — ${precio}"
        elif p14 and p8:
            parts[0] += f" — 14\":${p14} / 8\":${p8}"
        elif pp and pc:
            parts[0] += f" — Pollo:${pp} / Camarón:${pc}"
        if desc:
            parts.append(f"    {desc}")
        return "\n".join(parts)


def load_tenant(tenant_id: str) -> TenantConfig:
    return TenantConfig(tenant_id)

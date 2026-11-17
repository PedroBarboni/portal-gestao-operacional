"""Helpers para manter slugs e rotas funcionais em um único lugar."""

from __future__ import annotations

import re
import unicodedata


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def sector_route(sector_slug: str) -> str:
    return f"/setores/?setor={sector_slug}"


def module_route(sector_slug: str, module_slug: str) -> str:
    return f"/{sector_slug}/{module_slug}"


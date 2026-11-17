"""Registro das rotas de setor que já possuem funcionalidade implementada em código."""

from __future__ import annotations


# Uma tela cadastrada no banco só se torna navegável após sua rota entrar neste registro.
IMPLEMENTED_MODULE_ROUTES: frozenset[str] = frozenset()


def is_implemented_route(route: str | None) -> bool:
    return bool(route and route in IMPLEMENTED_MODULE_ROUTES)


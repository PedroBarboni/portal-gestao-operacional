"""Registro centralizado de eventos administrativos e de autenticação."""

from server.modules.audit.service import record_event

__all__ = ["record_event"]


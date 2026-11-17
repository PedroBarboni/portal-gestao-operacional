"""Serviço de auditoria independente das interfaces e dos módulos de negócio."""

from __future__ import annotations

from sgo_db import connection, now


def record_event(
    action: str,
    entity_type: str,
    entity_id: int | str | None,
    *,
    actor_user_id: int | None,
    description: str = "",
    ip_address: str | None = None,
) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO audit_events(
                   actor_user_id,action,entity_type,entity_id,description,ip_address,created_at
               ) VALUES(?,?,?,?,?,?,?)""",
            (actor_user_id, action, entity_type, str(entity_id) if entity_id is not None else None, description, ip_address, now()),
        )


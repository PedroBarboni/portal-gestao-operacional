"""Executor mínimo de migrations versionadas para o SQLite de desenvolvimento."""

from __future__ import annotations

from collections.abc import Callable
from sqlite3 import Connection

from server.migrations import m0001_foundation, m0002_action_permissions


Migration = tuple[int, str, Callable[[Connection], None]]
MIGRATIONS: tuple[Migration, ...] = (
    (1, "foundation", m0001_foundation.upgrade),
    (2, "action_permissions", m0002_action_permissions.upgrade),
)


def run_migrations(db: Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    applied = {row[0] for row in db.execute("SELECT version FROM schema_migrations")}
    for version, name, upgrade in MIGRATIONS:
        if version in applied:
            continue
        upgrade(db)
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES(?,?)", (version, name)
        )

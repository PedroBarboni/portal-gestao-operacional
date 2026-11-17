"""Normaliza permissões flexíveis para as ações configuradas em cada tela."""

from __future__ import annotations

import sqlite3


def upgrade(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS user_action_permissions (
               user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
               module_action_id INTEGER NOT NULL REFERENCES module_actions(id) ON DELETE CASCADE,
               allowed INTEGER NOT NULL DEFAULT 0,
               PRIMARY KEY(user_id, module_action_id)
           )"""
    )
    db.execute(
        """INSERT OR IGNORE INTO user_action_permissions(user_id,module_action_id,allowed)
           SELECT p.user_id,ma.id,p.allowed
           FROM permissions p
           JOIN module_actions ma ON ma.module_id=p.module_id AND ma.label=p.action"""
    )

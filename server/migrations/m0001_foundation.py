"""Perfis, sessões, auditoria e metadados de rotas da fundação modular."""

from __future__ import annotations

import re
import sqlite3
import unicodedata


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def upgrade(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          slug TEXT NOT NULL UNIQUE,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS profile_permissions (
          profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
          permission_key TEXT NOT NULL,
          allowed INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(profile_id, permission_key)
        );
        CREATE TABLE IF NOT EXISTS sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token_hash TEXT NOT NULL UNIQUE,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          revoked_at TEXT,
          ip_address TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
        CREATE TABLE IF NOT EXISTS audit_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
          action TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT,
          description TEXT NOT NULL DEFAULT '',
          ip_address TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS module_actions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
          action_key TEXT NOT NULL,
          label TEXT NOT NULL,
          display_order INTEGER NOT NULL DEFAULT 0,
          active INTEGER NOT NULL DEFAULT 1,
          UNIQUE(module_id, action_key)
        );
        """
    )

    if "profile_id" not in _columns(db, "users"):
        db.execute("ALTER TABLE users ADD COLUMN profile_id INTEGER REFERENCES profiles(id)")
    if "slug" not in _columns(db, "sectors"):
        db.execute("ALTER TABLE sectors ADD COLUMN slug TEXT")
    if "display_order" not in _columns(db, "sectors"):
        db.execute("ALTER TABLE sectors ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0")
    module_columns = _columns(db, "modules")
    if "slug" not in module_columns:
        db.execute("ALTER TABLE modules ADD COLUMN slug TEXT")
    if "route" not in module_columns:
        db.execute("ALTER TABLE modules ADD COLUMN route TEXT")
    if "description" not in module_columns:
        db.execute("ALTER TABLE modules ADD COLUMN description TEXT NOT NULL DEFAULT ''")

    profile_names = [row[0] for row in db.execute("SELECT DISTINCT profile FROM users")]
    for name in profile_names:
        db.execute(
            "INSERT OR IGNORE INTO profiles(name,slug) VALUES(?,?)", (name, _slug(name))
        )
    db.execute(
        """UPDATE users SET profile_id=(
               SELECT id FROM profiles WHERE profiles.name=users.profile
           ) WHERE profile_id IS NULL"""
    )
    admin_profile = db.execute(
        "SELECT id FROM profiles WHERE lower(name)=lower('Administrador')"
    ).fetchone()
    if admin_profile:
        db.execute(
            """INSERT INTO profile_permissions(profile_id,permission_key,allowed)
               VALUES(?, 'administration.access', 1)
               ON CONFLICT(profile_id,permission_key) DO UPDATE SET allowed=1""",
            (admin_profile["id"],),
        )

    sectors = db.execute("SELECT id,name,slug,display_order FROM sectors ORDER BY id").fetchall()
    for order, sector in enumerate(sectors, 1):
        db.execute(
            "UPDATE sectors SET slug=?,display_order=? WHERE id=?",
            (sector["slug"] or _slug(sector["name"]), sector["display_order"] or order, sector["id"]),
        )
    modules = db.execute(
        """SELECT m.id,m.name,m.slug,m.route,s.slug sector_slug
           FROM modules m JOIN sectors s ON s.id=m.sector_id"""
    ).fetchall()
    for module in modules:
        slug = module["slug"] or _slug(module["name"])
        db.execute(
            "UPDATE modules SET slug=?,route=? WHERE id=?",
            (slug, module["route"] or f"/{module['sector_slug']}/{slug}", module["id"]),
        )
        default_actions = (
            ("view", "Visualizar"), ("create", "Criar / Incluir"),
            ("edit", "Editar"), ("delete", "Excluir"),
            ("approve", "Aprovar / Finalizar"), ("print", "Imprimir"),
            ("export", "Exportar"), ("attach", "Anexar Arquivos"),
            ("comment", "Comentários"),
        )
        db.executemany(
            """INSERT OR IGNORE INTO module_actions(module_id,action_key,label,display_order)
               VALUES(?,?,?,?)""",
            [(module["id"], key, label, order) for order, (key, label) in enumerate(default_actions, 1)],
        )

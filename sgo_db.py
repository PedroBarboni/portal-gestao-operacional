"""Persistência SQLite local do SGO."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from server.core.config import DATABASE_PATH
from server.core.migrations import run_migrations
from server.core.security import hash_password, verify_password
from server.core.routes import module_route, slugify
from server.modules.sectors import is_implemented_route

SECTORS = [
    ("Compras", "shopping-cart"), ("Fornecedor", "users"),
    ("Conferência", "file-check-2"), ("Almoxarifado", "archive"),
    ("Qualidade", "shield-check"), ("Faturamento/Fiscal", "receipt-text"),
    ("PCP", "chart-no-axes-combined"), ("Produção", "factory"),
    ("Expedição", "truck"), ("Manutenção", "wrench"),
    ("RH", "users-round"), ("Segurança do Trabalho", "hard-hat"),
]

MAINTENANCE_MODULES = [
    ("Dashboard", "chart-no-axes-combined"),
    ("Ordens de Serviço", "clipboard-list"),
    ("Manutenção Preventiva", "route"),
    ("Equipamentos", "wrench"),
    ("Planos de Manutenção", "calendar-cog"),
    ("Indicadores", "chart-column"),
    ("Configurações do Setor", "settings"),
]

class MaintenanceRequiredError(ValueError):
    """Impede alterações enquanto o usuário ainda pode estar conectado."""


MAINTENANCE_REQUIRED_MESSAGE = "Ative a manutenção do usuário antes de realizar alterações."


def connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_database() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      cpf TEXT UNIQUE,
      phone TEXT,
      avatar TEXT,
      profile TEXT NOT NULL,
      sector TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Ativo',
      maintenance INTEGER NOT NULL DEFAULT 0,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_access TEXT
    );
    CREATE TABLE IF NOT EXISTS sectors (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      icon TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Ativo',
      category TEXT NOT NULL DEFAULT 'Operacional',
      responsible TEXT
    );
    CREATE TABLE IF NOT EXISTS modules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sector_id INTEGER NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
      name TEXT NOT NULL,
      icon TEXT NOT NULL,
      category TEXT NOT NULL DEFAULT 'Operacional',
      display_order INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'Ativo',
      permission_enabled INTEGER NOT NULL DEFAULT 1,
      UNIQUE(sector_id, name)
    );
    CREATE TABLE IF NOT EXISTS user_sectors (
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      sector_id INTEGER NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
      PRIMARY KEY(user_id, sector_id)
    );
    CREATE TABLE IF NOT EXISTS user_modules (
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
      PRIMARY KEY(user_id, module_id)
    );
    CREATE TABLE IF NOT EXISTS permissions (
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
      action TEXT NOT NULL,
      allowed INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(user_id, module_id, action)
    );
    CREATE TABLE IF NOT EXISTS access_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      accessed_at TEXT NOT NULL,
      ip_address TEXT NOT NULL,
      success INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      action TEXT NOT NULL,
      actor TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """
    with connection() as db:
        db.executescript(schema)
        user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
        if "maintenance" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN maintenance INTEGER NOT NULL DEFAULT 0")
        if "avatar" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
        sector_columns = {row["name"] for row in db.execute("PRAGMA table_info(sectors)").fetchall()}
        for column, definition in (
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Ativo'"),
            ("category", "TEXT NOT NULL DEFAULT 'Operacional'"),
            ("responsible", "TEXT"),
        ):
            if column not in sector_columns:
                db.execute(f"ALTER TABLE sectors ADD COLUMN {column} {definition}")
        module_columns = {row["name"] for row in db.execute("PRAGMA table_info(modules)").fetchall()}
        for column, definition in (
            ("category", "TEXT NOT NULL DEFAULT 'Operacional'"),
            ("display_order", "INTEGER NOT NULL DEFAULT 0"),
            ("status", "TEXT NOT NULL DEFAULT 'Ativo'"),
            ("permission_enabled", "INTEGER NOT NULL DEFAULT 1"),
        ):
            if column not in module_columns:
                db.execute(f"ALTER TABLE modules ADD COLUMN {column} {definition}")
        # O catálogo oficial do PGO usa PCP; preserva o id e os acessos do protótipo.
        if db.execute("SELECT 1 FROM sectors WHERE name='Vendas'").fetchone() and not db.execute("SELECT 1 FROM sectors WHERE name='PCP'").fetchone():
            db.execute("UPDATE sectors SET name='PCP', icon='chart-no-axes-combined' WHERE name='Vendas'")
        db.executemany("INSERT OR IGNORE INTO sectors(name, icon) VALUES(?, ?)", SECTORS)
        sector_details = {
            "Compras": ("Pedidos, cotações e controle de insumos.", "Administrativo"),
            "Fornecedor": ("Cadastro e avaliação de fornecedores.", "Administrativo"),
            "Conferência": ("Conferência de materiais e documentos.", "Operacional"),
            "Almoxarifado": ("Controle de estoque e movimentações.", "Operacional"),
            "Qualidade": ("Gestão da qualidade e não conformidades.", "Operacional"),
            "Faturamento/Fiscal": ("Emissão de notas e obrigações fiscais.", "Administrativo"),
            "PCP": ("Planejamento e controle da produção.", "Operacional"),
            "Produção": ("Acompanhamento das ordens de produção.", "Operacional"),
            "Expedição": ("Separação, embalagem e envios.", "Operacional"),
            "Manutenção": ("Gestão de ordens de serviço e manutenções.", "Operacional"),
            "RH": ("Gestão de pessoas e processos de RH.", "Administrativo"),
            "Segurança do Trabalho": ("Gestão de acessos e conformidades.", "Operacional"),
        }
        for sector_name, (description, category) in sector_details.items():
            db.execute("UPDATE sectors SET description=CASE WHEN description='' THEN ? ELSE description END, category=? WHERE name=?", (description, category, sector_name))
        maintenance_id = db.execute("SELECT id FROM sectors WHERE name = 'Manutenção'").fetchone()["id"]
        db.executemany(
            "INSERT OR IGNORE INTO modules(sector_id, name, icon) VALUES(?, ?, ?)",
            [(maintenance_id, name, icon) for name, icon in MAINTENANCE_MODULES],
        )
        db.execute("UPDATE modules SET display_order=id WHERE display_order=0")
        user = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not user:
            cursor = db.execute(
                """INSERT INTO users(username,name,email,cpf,phone,profile,sector,status,password_hash,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                ("admin", "Administrador", "admin@empresa.local", None, None, "Administrador", "TI", "Ativo", hash_password("12345"), now()),
            )
            user_id = cursor.lastrowid
            sector_ids = [row["id"] for row in db.execute("SELECT id FROM sectors").fetchall()]
            module_ids = [row["id"] for row in db.execute("SELECT id FROM modules").fetchall()]
            db.executemany("INSERT INTO user_sectors(user_id,sector_id) VALUES(?,?)", [(user_id, item) for item in sector_ids])
            db.executemany("INSERT INTO user_modules(user_id,module_id) VALUES(?,?)", [(user_id, item) for item in module_ids])
            db.execute("INSERT INTO audit_logs(user_id,action,actor,created_at) VALUES(?,?,?,?)", (user_id, "Conta administrativa criada", "Sistema", now()))
        run_migrations(db)


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def public_user(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data.pop("password_hash", None)
    return data


def validate_avatar(value: Any) -> str | None:
    if not value:
        return None
    if not isinstance(value, str) or not value.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
        raise ValueError("A foto de perfil deve ser uma imagem JPG, PNG ou WebP.")
    if len(value) > 2_800_000:
        raise ValueError("A foto de perfil deve ter no máximo 2 MB.")
    return value


def validate_sector_icon(value: Any) -> str:
    icon = str(value or "").strip()
    if not icon:
        raise ValueError("Selecione um ícone SVG ou PNG para o setor.")
    if icon.startswith("data:"):
        if not icon.startswith(("data:image/png;base64,", "data:image/svg+xml;base64,")):
            raise ValueError("O ícone do setor deve ser um arquivo SVG ou PNG.")
        if len(icon) > 1_050_000:
            raise ValueError("O ícone do setor deve ter no máximo 750 KB.")
    return icon


def ensure_profile(db: sqlite3.Connection, profile_name: str) -> int | None:
    """Retorna/cria o perfil mantendo compatibilidade com o campo textual legado."""
    if "profile_id" not in {row["name"] for row in db.execute("PRAGMA table_info(users)")}:
        return None
    row = db.execute("SELECT id FROM profiles WHERE lower(name)=lower(?)", (profile_name,)).fetchone()
    if row:
        return int(row["id"])
    slug = "-".join(profile_name.lower().split())
    cursor = db.execute("INSERT INTO profiles(name,slug) VALUES(?,?)", (profile_name, slug))
    return int(cursor.lastrowid)


def list_users() -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute("SELECT * FROM users ORDER BY name COLLATE NOCASE").fetchall()
    return [public_user(row) for row in rows]


def get_user(user_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        user = public_user(row)
        user["access_logs"] = [dict(item) for item in db.execute("SELECT accessed_at,ip_address,success FROM access_logs WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()]
        user["audit_logs"] = [dict(item) for item in db.execute("SELECT action,actor,created_at FROM audit_logs WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()]
        user["sectors"] = [dict(item) for item in db.execute("SELECT s.id,s.name FROM sectors s JOIN user_sectors us ON us.sector_id=s.id WHERE us.user_id=? ORDER BY s.name", (user_id,)).fetchall()]
    return user


def create_user(data: dict[str, Any]) -> dict[str, Any]:
    required = ["name", "email", "cpf", "profile", "sector", "status", "password"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        raise ValueError(f"Campos obrigatórios: {', '.join(missing)}")
    email = data["email"].strip().lower()
    username = data.get("username") or email.split("@", 1)[0]
    avatar = validate_avatar(data.get("avatar"))
    with connection() as db:
        profile_id = ensure_profile(db, str(data["profile"]).strip())
        cursor = db.execute(
            """INSERT INTO users(username,name,email,cpf,phone,avatar,profile,profile_id,sector,status,password_hash,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (username, data["name"].strip(), email, data["cpf"], data.get("phone"), avatar, data["profile"], profile_id, data["sector"], data["status"], hash_password(data["password"]), now()),
        )
        user_id = cursor.lastrowid
        db.execute("INSERT INTO audit_logs(user_id,action,actor,created_at) VALUES(?,?,?,?)", (user_id, "Usuário cadastrado", "Administrador", now()))
    return get_user(user_id)  # type: ignore[return-value]


def update_user(user_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with connection() as db:
        current = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not current:
            return None
        if not current["maintenance"]:
            raise MaintenanceRequiredError(MAINTENANCE_REQUIRED_MESSAGE)
        values = {key: data.get(key, current[key]) for key in ("name", "email", "cpf", "phone", "profile", "sector", "status")}
        profile_id = ensure_profile(db, str(values["profile"]).strip())
        avatar = validate_avatar(data["avatar"]) if "avatar" in data else current["avatar"]
        db.execute("UPDATE users SET name=?,email=?,cpf=?,phone=?,profile=?,profile_id=?,sector=?,status=?,avatar=? WHERE id=?", (*values.values(), profile_id, avatar, user_id))
        if data.get("password"):
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(data["password"]), user_id))
        db.execute("INSERT INTO audit_logs(user_id,action,actor,created_at) VALUES(?,?,?,?)", (user_id, "Dados do usuário atualizados", "Administrador", now()))
    return get_user(user_id)


def delete_user(user_id: int) -> bool:
    with connection() as db:
        row = db.execute(
            """SELECT u.maintenance,COALESCE(pp.allowed,0) is_admin
               FROM users u
               LEFT JOIN profile_permissions pp ON pp.profile_id=u.profile_id
                    AND pp.permission_key='administration.access'
               WHERE u.id=?""",
            (user_id,),
        ).fetchone()
        if not row:
            return False
        if row["is_admin"]:
            admin_count = db.execute(
                """SELECT COUNT(DISTINCT u.id) total FROM users u
                   JOIN profile_permissions pp ON pp.profile_id=u.profile_id
                   WHERE pp.permission_key='administration.access' AND pp.allowed=1"""
            ).fetchone()["total"]
            if admin_count <= 1:
                return False
        if not row["maintenance"]:
            raise MaintenanceRequiredError(MAINTENANCE_REQUIRED_MESSAGE)
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
    return True


def authenticate(username: str, password: str, ip_address: str) -> dict[str, Any]:
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE lower(username)=lower(?) OR lower(email)=lower(?)", (username, username)).fetchone()
        in_maintenance = bool(row and row["maintenance"])
        success = bool(row and not in_maintenance and row["status"] == "Ativo" and verify_password(password, row["password_hash"]))
        if row:
            db.execute("INSERT INTO access_logs(user_id,accessed_at,ip_address,success) VALUES(?,?,?,?)", (row["id"], now(), ip_address, int(success)))
            if success:
                db.execute("UPDATE users SET last_access=? WHERE id=?", (now(), row["id"]))
        return {"user": public_user(row) if success else None, "maintenance": in_maintenance}


def session_status(user_id: int) -> dict[str, Any]:
    with connection() as db:
        row = db.execute("SELECT id,status,maintenance FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return {"exists": False, "active": False, "maintenance": False}
    return {"exists": True, "active": row["status"] == "Ativo", "maintenance": bool(row["maintenance"])}


def set_user_maintenance(user_id: int, enabled: bool) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return None
        db.execute("UPDATE users SET maintenance=? WHERE id=?", (int(enabled), user_id))
        if enabled:
            db.execute("UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now(), user_id))
        action = "Modo de manutenção ativado" if enabled else "Modo de manutenção desativado"
        db.execute("INSERT INTO audit_logs(user_id,action,actor,created_at) VALUES(?,?,?,?)", (user_id, action, "Administrador", now()))
    return get_user(user_id)


def get_access(user_id: int) -> dict[str, Any]:
    with connection() as db:
        sectors = [dict(row) for row in db.execute(
            """SELECT s.id,s.name,s.slug,s.icon,s.description,s.status,s.display_order,
                      CASE WHEN us.user_id IS NULL THEN 0 ELSE 1 END enabled
               FROM sectors s LEFT JOIN user_sectors us ON us.sector_id=s.id AND us.user_id=?
               ORDER BY s.display_order,s.id""", (user_id,)
        ).fetchall()]
        modules = [dict(row) for row in db.execute(
            """SELECT m.id,m.sector_id,m.name,m.slug,m.route,m.icon,m.description,m.status,
                      m.display_order,m.permission_enabled,
                      CASE WHEN um.user_id IS NULL THEN 0 ELSE 1 END enabled
               FROM modules m LEFT JOIN user_modules um ON um.module_id=m.id AND um.user_id=?
               ORDER BY m.sector_id,m.display_order,m.id""", (user_id,)
        ).fetchall()]
        module_id = next((item["id"] for item in modules if item["name"] == "Ordens de Serviço"), modules[0]["id"] if modules else 0)
        saved = {row["module_action_id"]: bool(row["allowed"]) for row in db.execute(
            """SELECT uap.module_action_id,uap.allowed
               FROM user_action_permissions uap
               JOIN module_actions ma ON ma.id=uap.module_action_id
               WHERE uap.user_id=? AND ma.module_id=?""", (user_id, module_id)
        ).fetchall()}
        configured_actions = [dict(row) for row in db.execute(
            """SELECT id,action_key,label FROM module_actions
               WHERE module_id=? AND active=1 ORDER BY display_order,id""", (module_id,)
        ).fetchall()]
    for module in modules:
        module["implemented"] = is_implemented_route(module.get("route"))
    permissions = [
        {"action": item["label"], "action_key": item["action_key"], "allowed": saved.get(item["id"], item["action_key"] != "delete")}
        for item in configured_actions
    ]
    return {"sectors": sectors, "modules": modules, "module_id": module_id, "permissions": permissions}


def save_access(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    sector_ids = [int(value) for value in data.get("sector_ids", [])]
    module_ids = [int(value) for value in data.get("module_ids", [])]
    module_id = int(data.get("module_id") or 0)
    permissions = data.get("permissions", {})
    with connection() as db:
        user = db.execute("SELECT maintenance FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise ValueError("Usuário não encontrado.")
        if not user["maintenance"]:
            raise MaintenanceRequiredError(MAINTENANCE_REQUIRED_MESSAGE)
        if "sector_ids" in data:
            db.execute("DELETE FROM user_sectors WHERE user_id=?", (user_id,))
            db.executemany("INSERT INTO user_sectors(user_id,sector_id) VALUES(?,?)", [(user_id, item) for item in sector_ids])
        if "module_ids" in data:
            db.execute("DELETE FROM user_modules WHERE user_id=?", (user_id,))
            db.executemany("INSERT INTO user_modules(user_id,module_id) VALUES(?,?)", [(user_id, item) for item in module_ids])
        if module_id and permissions:
            valid_actions = {row["label"]: row["id"] for row in db.execute("SELECT id,label FROM module_actions WHERE module_id=? AND active=1", (module_id,)).fetchall()}
            for action, allowed in permissions.items():
                if action not in valid_actions:
                    raise ValueError(f"Ação de permissão inválida: {action}")
                db.execute(
                    """INSERT INTO user_action_permissions(user_id,module_action_id,allowed)
                       VALUES(?,?,?)
                       ON CONFLICT(user_id,module_action_id) DO UPDATE SET allowed=excluded.allowed""",
                    (user_id, valid_actions[action], int(bool(allowed))),
                )
        db.execute("INSERT INTO audit_logs(user_id,action,actor,created_at) VALUES(?,?,?,?)", (user_id, "Permissões de acesso atualizadas", "Administrador", now()))
    return get_access(user_id)


def list_sectors() -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute(
            """SELECT s.*,COUNT(m.id) module_count
               FROM sectors s LEFT JOIN modules m ON m.sector_id=s.id
               GROUP BY s.id ORDER BY s.display_order,s.name COLLATE NOCASE"""
        ).fetchall()
    return [dict(row) for row in rows]


def get_sector(sector_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute("SELECT * FROM sectors WHERE id=?", (sector_id,)).fetchone()
        if not row:
            return None
        sector = dict(row)
        sector["modules"] = [dict(item) for item in db.execute(
            """SELECT * FROM modules WHERE sector_id=?
               ORDER BY display_order,id""", (sector_id,)
        ).fetchall()]
    return sector


def create_sector(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    icon = validate_sector_icon(data.get("icon"))
    if not name or not description:
        raise ValueError("Nome, descrição e ícone são obrigatórios.")
    with connection() as db:
        sector_slug = slugify(name)
        cursor = db.execute(
            "INSERT INTO sectors(name,slug,icon,description,status,category,responsible,display_order) VALUES(?,?,?,?,?,?,?,(SELECT COALESCE(MAX(display_order),0)+1 FROM sectors))",
            (name, sector_slug, icon, description, data.get("status", "Ativo"), data.get("category", "Operacional"), data.get("responsible") or None),
        )
        sector_id = cursor.lastrowid
        for order, module in enumerate(data.get("modules", []), 1):
            module_name = str(module.get("name") if isinstance(module, dict) else module).strip()
            if module_name:
                db.execute(
                    "INSERT INTO modules(sector_id,name,slug,route,icon,category,display_order) VALUES(?,?,?,?,?,?,?)",
                    (sector_id, module_name, slugify(module_name), module_route(sector_slug, slugify(module_name)), "panel-top", "Operacional", order),
                )
    return get_sector(sector_id)  # type: ignore[return-value]


def update_sector(sector_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with connection() as db:
        current = db.execute("SELECT * FROM sectors WHERE id=?", (sector_id,)).fetchone()
        if not current:
            return None
        values = {key: data.get(key, current[key]) for key in ("name", "icon", "description", "status", "category", "responsible")}
        values["icon"] = validate_sector_icon(values["icon"])
        if not str(values["name"]).strip() or not str(values["description"]).strip():
            raise ValueError("Nome, descrição e ícone são obrigatórios.")
        old_slug = current["slug"] or slugify(current["name"])
        new_slug = slugify(str(values["name"]))
        db.execute(
            "UPDATE sectors SET name=?,slug=?,icon=?,description=?,status=?,category=?,responsible=? WHERE id=?",
            (values["name"], new_slug, values["icon"], values["description"], values["status"], values["category"], values["responsible"], sector_id),
        )
        if old_slug != new_slug:
            modules = db.execute("SELECT id,slug,route FROM modules WHERE sector_id=?", (sector_id,)).fetchall()
            for module in modules:
                if not module["route"] or module["route"].startswith(f"/{old_slug}/"):
                    db.execute("UPDATE modules SET route=? WHERE id=?", (module_route(new_slug, module["slug"]), module["id"]))
    return get_sector(sector_id)


def delete_sector(sector_id: int) -> bool:
    with connection() as db:
        row = db.execute("SELECT id FROM sectors WHERE id=?", (sector_id,)).fetchone()
        if not row:
            return False
        db.execute("DELETE FROM sectors WHERE id=?", (sector_id,))
    return True


def create_module(sector_id: int, data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Informe o nome da tela.")
    with connection() as db:
        sector = db.execute("SELECT slug FROM sectors WHERE id=?", (sector_id,)).fetchone()
        if not sector:
            raise ValueError("Setor não encontrado.")
        module_slug = slugify(name)
        next_order = db.execute("SELECT COALESCE(MAX(display_order),0)+1 value FROM modules WHERE sector_id=?", (sector_id,)).fetchone()["value"]
        cursor = db.execute(
            """INSERT INTO modules(sector_id,name,slug,route,icon,category,display_order,status,permission_enabled,description)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (sector_id, name, module_slug, data.get("route") or module_route(sector["slug"], module_slug), data.get("icon", "panel-top"), data.get("category", "Operacional"), next_order, data.get("status", "Ativo"), int(bool(data.get("permission_enabled", True))), str(data.get("description", "")).strip()),
        )
        default_actions = (("view", "Visualizar"), ("create", "Criar / Incluir"), ("edit", "Editar"), ("delete", "Excluir"))
        db.executemany(
            "INSERT INTO module_actions(module_id,action_key,label,display_order) VALUES(?,?,?,?)",
            [(cursor.lastrowid, key, label, order) for order, (key, label) in enumerate(default_actions, 1)],
        )
        row = db.execute("SELECT * FROM modules WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def update_module(module_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with connection() as db:
        current = db.execute("SELECT * FROM modules WHERE id=?", (module_id,)).fetchone()
        if not current:
            return None
        values = {key: data.get(key, current[key]) for key in ("name", "icon", "category", "display_order", "status", "permission_enabled", "description", "route")}
        old_slug = current["slug"] or slugify(current["name"])
        new_slug = slugify(str(values["name"]))
        sector_slug = db.execute("SELECT slug FROM sectors WHERE id=?", (current["sector_id"],)).fetchone()["slug"]
        if not values["route"] or values["route"] == module_route(sector_slug, old_slug):
            values["route"] = module_route(sector_slug, new_slug)
        db.execute(
            "UPDATE modules SET name=?,slug=?,icon=?,category=?,display_order=?,status=?,permission_enabled=?,description=?,route=? WHERE id=?",
            (values["name"], new_slug, values["icon"], values["category"], int(values["display_order"]), values["status"], int(bool(values["permission_enabled"])), values["description"], values["route"], module_id),
        )
        row = db.execute("SELECT * FROM modules WHERE id=?", (module_id,)).fetchone()
    return dict(row)


def delete_module(module_id: int) -> bool:
    with connection() as db:
        cursor = db.execute("DELETE FROM modules WHERE id=?", (module_id,))
    return cursor.rowcount > 0


def overview() -> dict[str, Any]:
    with connection() as db:
        users = db.execute("SELECT COUNT(*) total FROM users").fetchone()["total"]
        profiles = db.execute("SELECT COUNT(DISTINCT profile) total FROM users").fetchone()["total"]
        sectors = db.execute("SELECT COUNT(*) total FROM sectors").fetchone()["total"]
        modules = db.execute("SELECT COUNT(*) total FROM modules").fetchone()["total"]
        rows = db.execute("SELECT profile,COUNT(*) users FROM users GROUP BY profile ORDER BY profile").fetchall()
    return {"users": users, "profiles": profiles, "sectors": sectors, "modules": modules, "profile_summary": [dict(row) for row in rows]}

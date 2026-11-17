"""Serviço de autenticação e autorização baseado em sessões opacas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from server.core.config import SESSION_TTL_HOURS
from server.core.security import generate_session_token, hash_session_token, verify_password
from sgo_db import connection, public_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Principal:
    user: dict[str, Any]
    permissions: frozenset[str]

    @property
    def id(self) -> int:
        return int(self.user["id"])


def authenticate_user(username: str, password: str, ip_address: str) -> dict[str, Any]:
    with connection() as db:
        row = db.execute(
            """SELECT u.* FROM users u
               WHERE lower(u.username)=lower(?) OR lower(u.email)=lower(?)""",
            (username, username),
        ).fetchone()
        maintenance = bool(row and row["maintenance"])
        success = bool(
            row
            and not maintenance
            and row["status"] == "Ativo"
            and verify_password(password, row["password_hash"])
        )
        if row:
            db.execute(
                "INSERT INTO access_logs(user_id,accessed_at,ip_address,success) VALUES(?,?,?,?)",
                (row["id"], _timestamp(), ip_address, int(success)),
            )
            if success:
                db.execute("UPDATE users SET last_access=? WHERE id=?", (_timestamp(), row["id"]))
        return {"user": public_user(row) if success else None, "maintenance": maintenance}


def create_session(user_id: int, ip_address: str) -> str:
    token = generate_session_token()
    created_at = _utc_now()
    expires_at = created_at + timedelta(hours=SESSION_TTL_HOURS)
    with connection() as db:
        db.execute(
            """INSERT INTO sessions(token_hash,user_id,created_at,expires_at,ip_address)
               VALUES(?,?,?,?,?)""",
            (hash_session_token(token), user_id, _timestamp(created_at), _timestamp(expires_at), ip_address),
        )
    return token


def resolve_session(token: str | None) -> Principal | None:
    if not token:
        return None
    with connection() as db:
        row = db.execute(
            """SELECT u.*,s.expires_at,s.revoked_at
               FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=?""",
            (hash_session_token(token),),
        ).fetchone()
        if not row or row["revoked_at"] or row["expires_at"] <= _timestamp():
            return None
        if row["status"] != "Ativo" or row["maintenance"]:
            db.execute(
                "UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (_timestamp(), hash_session_token(token)),
            )
            return None
        permissions = frozenset(
            item["permission_key"]
            for item in db.execute(
                """SELECT pp.permission_key FROM profile_permissions pp
                   WHERE pp.profile_id=? AND pp.allowed=1""",
                (row["profile_id"],),
            ).fetchall()
        )
    user = public_user(row)
    user.pop("expires_at", None)
    user.pop("revoked_at", None)
    return Principal(user, permissions)


def session_state(token: str | None) -> dict[str, bool]:
    if not token:
        return {"exists": False, "active": False, "maintenance": False}
    with connection() as db:
        row = db.execute(
            """SELECT u.status,u.maintenance,s.expires_at,s.revoked_at
               FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=?""",
            (hash_session_token(token),),
        ).fetchone()
    if not row:
        return {"exists": False, "active": False, "maintenance": False}
    maintenance = bool(row["maintenance"])
    active = bool(not row["revoked_at"] and row["expires_at"] > _timestamp() and row["status"] == "Ativo" and not maintenance)
    return {"exists": True, "active": active, "maintenance": maintenance}


def has_permission(principal: Principal, permission_key: str) -> bool:
    return permission_key in principal.permissions


def logout(token: str | None) -> None:
    if not token:
        return
    with connection() as db:
        db.execute(
            "UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
            (_timestamp(), hash_session_token(token)),
        )

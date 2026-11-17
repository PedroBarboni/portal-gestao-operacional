"""Testes da fundação modular, autenticação e migrations do PGO."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FoundationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data_directory = PROJECT_ROOT / "data"
        data_directory.mkdir(exist_ok=True)
        cls.temp_directory = tempfile.TemporaryDirectory(dir=data_directory)
        os.environ["PGO_DATABASE_PATH"] = str(Path(cls.temp_directory.name) / "pgo-test.db")

        import sgo_db
        from server.modules.auth import authenticate_user, create_session, resolve_session, session_state

        cls.db = sgo_db
        cls.authenticate_user = staticmethod(authenticate_user)
        cls.create_session = staticmethod(create_session)
        cls.resolve_session = staticmethod(resolve_session)
        cls.session_state = staticmethod(session_state)
        sgo_db.init_database()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_directory.cleanup()

    def test_versioned_schema_is_valid(self) -> None:
        with self.db.connection() as database:
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(database.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                database.execute("SELECT name FROM schema_migrations WHERE version=1").fetchone()[0],
                "foundation",
            )
            self.assertEqual(
                database.execute("SELECT name FROM schema_migrations WHERE version=2").fetchone()[0],
                "action_permissions",
            )
            tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"profiles", "profile_permissions", "sessions", "module_actions", "user_action_permissions", "audit_events"} <= tables)

    def test_administrator_permission_comes_from_profile(self) -> None:
        authentication = self.authenticate_user("admin", "12345", "127.0.0.1")
        token = self.create_session(authentication["user"]["id"], "127.0.0.1")
        principal = self.resolve_session(token)
        self.assertIsNotNone(principal)
        self.assertIn("administration.access", principal.permissions)

    def test_maintenance_revokes_active_sessions(self) -> None:
        user = self.db.create_user({
            "name": "Usuário de Teste",
            "email": "usuario.teste@empresa.local",
            "cpf": "123.456.789-00",
            "phone": "(11) 99999-9999",
            "profile": "Usuário",
            "sector": "PCP",
            "status": "Ativo",
            "password": "teste-seguro",
        })
        token = self.create_session(user["id"], "127.0.0.1")
        self.assertIsNotNone(self.resolve_session(token))
        self.db.set_user_maintenance(user["id"], True)
        self.assertIsNone(self.resolve_session(token))
        self.assertEqual(self.session_state(token), {"exists": True, "active": False, "maintenance": True})

    def test_sector_catalog_and_permissions_come_from_database(self) -> None:
        admin = self.db.list_users()[0]
        access = self.db.get_access(admin["id"])
        self.assertIn("PCP", {sector["name"] for sector in access["sectors"]})
        self.assertTrue(all(sector["slug"] for sector in access["sectors"]))
        self.assertTrue(all("implemented" in module for module in access["modules"]))
        self.assertTrue(all(permission["action_key"] for permission in access["permissions"]))


if __name__ == "__main__":
    unittest.main()

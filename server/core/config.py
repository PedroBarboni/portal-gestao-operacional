"""Configurações do servidor carregadas exclusivamente do ambiente."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.environ.get("PGO_DATABASE_PATH", PROJECT_ROOT / "data" / "sgo.db"))
SESSION_COOKIE_NAME = "pgo_session"
SESSION_TTL_HOURS = int(os.environ.get("PGO_SESSION_TTL_HOURS", "12"))


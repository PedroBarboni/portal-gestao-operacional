"""Servidor local do SGO acessível por outros dispositivos da rede."""

from __future__ import annotations

import os
import json
import socket
import sqlite3
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from sgo_db import (
    MaintenanceRequiredError,
    create_module,
    create_sector,
    create_user,
    delete_module,
    delete_sector,
    delete_user,
    get_access,
    get_sector,
    get_user,
    init_database,
    list_users,
    list_sectors,
    overview,
    save_access,
    set_user_maintenance,
    update_user,
    update_module,
    update_sector,
)
from server.core.config import SESSION_COOKIE_NAME, SESSION_TTL_HOURS
from server.modules.auth import (
    Principal,
    authenticate_user,
    create_session,
    has_permission,
    logout,
    resolve_session,
    session_state,
)
from server.modules.audit import record_event


PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_HOST = os.environ.get("SGO_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SGO_PORT", "5026"))


def get_local_ip() -> str:
    """Retorna um endereço IPv4 não local para exibição no terminal."""
    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        for address in addresses:
            ip_address = address[4][0]
            if not ip_address.startswith("127.") and not ip_address.startswith("169.254."):
                return ip_address
    except socket.gaierror:
        pass

    return "IP-DA-MAQUINA"


class SGORequestHandler(SimpleHTTPRequestHandler):
    """Entrega os arquivos do projeto e normaliza as rotas principais."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - assinatura definida pela biblioteca
        route = urlsplit(self.path).path

        if route.startswith("/api/"):
            self.handle_api_get(route)
            return

        if route == "/home":
            self.send_response(301)
            self.send_header("Location", "/home/")
            self.end_headers()
            return

        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        route = urlsplit(self.path).path
        if route == "/api/auth/login":
            data = self.read_json()
            auth = authenticate_user(str(data.get("username", "")).strip(), str(data.get("password", "")), self.client_address[0])
            if auth["maintenance"]:
                self.send_json({"error": "Seu usuário está em manutenção. Entre em contato com o suporte ou aguarde a conclusão da manutenção."}, 423)
                return
            if not auth["user"]:
                self.send_json({"error": "Usuário ou senha incorretos."}, 401)
                return
            token = create_session(int(auth["user"]["id"]), self.client_address[0])
            record_event("auth.login", "session", None, actor_user_id=int(auth["user"]["id"]), ip_address=self.client_address[0])
            self.send_json(
                {"user": auth["user"]},
                headers={"Set-Cookie": self.session_cookie(token)},
            )
            return
        if route == "/api/auth/logout":
            principal = resolve_session(self.session_token())
            logout(self.session_token())
            if principal:
                record_event("auth.logout", "session", None, actor_user_id=principal.id, ip_address=self.client_address[0])
            self.send_json(
                {"logged_out": True},
                headers={"Set-Cookie": self.session_cookie("", max_age=0)},
            )
            return
        if route == "/api/users":
            if not self.require_principal(admin=True):
                return
            try:
                self.send_json({"user": create_user(self.read_json())}, 201)
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            except sqlite3.IntegrityError:
                self.send_json({"error": "E-mail, usuário ou CPF já cadastrado."}, 409)
            return
        if route == "/api/sectors":
            if not self.require_principal(admin=True):
                return
            try:
                self.send_json({"sector": create_sector(self.read_json())}, 201)
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            except sqlite3.IntegrityError:
                self.send_json({"error": "Já existe um setor com esse nome."}, 409)
            return
        parts = route.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "sectors"] and parts[3] == "modules":
            if not self.require_principal(admin=True):
                return
            try:
                self.send_json({"module": create_module(int(parts[2]), self.read_json())}, 201)
            except (ValueError, sqlite3.IntegrityError) as error:
                self.send_json({"error": str(error) or "Não foi possível criar a tela."}, 400)
            return
        self.send_json({"error": "Rota não encontrada."}, 404)

    def do_PUT(self) -> None:  # noqa: N802
        route = urlsplit(self.path).path
        parts = route.strip("/").split("/")
        if not self.require_principal(admin=True):
            return
        try:
            if len(parts) == 3 and parts[:2] == ["api", "users"]:
                user = update_user(int(parts[2]), self.read_json())
                self.send_json({"user": user}, 200 if user else 404)
                return
            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "access":
                self.send_json({"access": save_access(int(parts[2]), self.read_json())})
                return
            if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "maintenance":
                user = set_user_maintenance(int(parts[2]), bool(self.read_json().get("enabled")))
                self.send_json({"user": user}, 200 if user else 404)
                return
            if len(parts) == 3 and parts[:2] == ["api", "sectors"]:
                sector = update_sector(int(parts[2]), self.read_json())
                self.send_json({"sector": sector}, 200 if sector else 404)
                return
            if len(parts) == 3 and parts[:2] == ["api", "modules"]:
                module = update_module(int(parts[2]), self.read_json())
                self.send_json({"module": module}, 200 if module else 404)
                return
        except MaintenanceRequiredError as error:
            self.send_json({"error": str(error)}, 423)
            return
        except (ValueError, sqlite3.IntegrityError) as error:
            self.send_json({"error": str(error) or "Dados inválidos."}, 400)
            return
        self.send_json({"error": "Rota não encontrada."}, 404)

    def do_DELETE(self) -> None:  # noqa: N802
        parts = urlsplit(self.path).path.strip("/").split("/")
        if not self.require_principal(admin=True):
            return
        if len(parts) == 3 and parts[:2] == ["api", "users"]:
            try:
                deleted = delete_user(int(parts[2]))
            except MaintenanceRequiredError as error:
                self.send_json({"error": str(error)}, 423)
                return
            self.send_json({"deleted": True} if deleted else {"error": "A conta administrativa inicial não pode ser excluída."}, 200 if deleted else 400)
            return
        if len(parts) == 3 and parts[:2] == ["api", "sectors"]:
            deleted = delete_sector(int(parts[2]))
            self.send_json({"deleted": deleted}, 200 if deleted else 404)
            return
        if len(parts) == 3 and parts[:2] == ["api", "modules"]:
            deleted = delete_module(int(parts[2]))
            self.send_json({"deleted": deleted}, 200 if deleted else 404)
            return
        self.send_json({"error": "Rota não encontrada."}, 404)

    def handle_api_get(self, route: str) -> None:
        parts = route.strip("/").split("/")
        if route == "/api/auth/me":
            principal = self.require_principal()
            if principal:
                self.send_json({"user": principal.user, "permissions": sorted(principal.permissions)})
            return
        if route == "/api/users":
            if not self.require_principal(admin=True):
                return
            self.send_json({"users": list_users()})
            return
        if route == "/api/access/overview":
            if not self.require_principal(admin=True):
                return
            self.send_json({"overview": overview()})
            return
        if route == "/api/sectors":
            if not self.require_principal():
                return
            self.send_json({"sectors": list_sectors()})
            return
        if route == "/api/session/status":
            self.send_json({"session": session_state(self.session_token())})
            return
        if len(parts) == 3 and parts[:2] == ["api", "users"]:
            principal = self.require_principal()
            if not principal:
                return
            requested_user_id = int(parts[2])
            if requested_user_id != principal.id and not has_permission(principal, "administration.access"):
                self.send_json({"error": "Acesso negado."}, 403)
                return
            user = get_user(requested_user_id)
            self.send_json({"user": user}, 200 if user else 404)
            return
        if len(parts) == 4 and parts[:2] == ["api", "users"] and parts[3] == "access":
            principal = self.require_principal()
            if not principal:
                return
            requested_user_id = int(parts[2])
            if requested_user_id != principal.id and not has_permission(principal, "administration.access"):
                self.send_json({"error": "Acesso negado."}, 403)
                return
            self.send_json({"access": get_access(requested_user_id)})
            return
        if len(parts) == 3 and parts[:2] == ["api", "sectors"]:
            if not self.require_principal():
                return
            sector = get_sector(int(parts[2]))
            self.send_json({"sector": sector}, 200 if sector else 404)
            return
        self.send_json({"error": "Rota não encontrada."}, 404)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    def session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except ValueError:
            return None
        morsel = cookie.get(SESSION_COOKIE_NAME)
        return morsel.value if morsel else None

    def session_cookie(self, token: str, max_age: int | None = None) -> str:
        age = SESSION_TTL_HOURS * 60 * 60 if max_age is None else max_age
        return (
            f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; "
            f"Max-Age={age}"
        )

    def require_principal(self, admin: bool = False) -> Principal | None:
        principal = resolve_session(self.session_token())
        if not principal:
            self.send_json({"error": "Sessão expirada ou inválida."}, 401)
            return None
        if admin and not has_permission(principal, "administration.access"):
            self.send_json({"error": "Acesso administrativo não autorizado."}, 403)
            return None
        return principal

    def record_admin_event(self, action: str, entity_type: str, entity_id: int | str | None, description: str = "") -> None:
        principal = resolve_session(self.session_token())
        if principal:
            record_event(
                action,
                entity_type,
                entity_id,
                actor_user_id=principal.id,
                description=description,
                ip_address=self.client_address[0],
            )

    def send_json(self, payload: dict, status: int = 200, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, message_format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {message_format % args}")


def main() -> None:
    init_database()
    local_ip = get_local_ip()

    try:
        with ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), SGORequestHandler) as server:
            print("SGO disponível na rede local:")
            print(f"  Login: http://{local_ip}:{SERVER_PORT}/")
            print(f"  Setores: http://{local_ip}:{SERVER_PORT}/home/")
            print(f"  Administração: http://{local_ip}:{SERVER_PORT}/administradores/")
            print("Pressione Ctrl+C para encerrar.")
            server.serve_forever()
    except PermissionError:
        raise SystemExit(
            f"Sem permissão para utilizar a porta {SERVER_PORT}. "
            "Execute o terminal com as permissões necessárias."
        )
    except OSError as error:
        if getattr(error, "winerror", None) == 10048 or error.errno == 98:
            raise SystemExit(f"A porta {SERVER_PORT} já está sendo utilizada.")
        raise
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()

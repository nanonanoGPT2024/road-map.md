#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Ruby Lanjutan & Anatomi Rails Engine
Simulasi Arsitektur Internal Ruby on Rails:
- ActiveSupport Concern & Callback Chain Execution (before_action/around_action)
- Rack Middleware Stack (Onion Architecture)
- Isolated Rails Engine (Sub-aplikasi modular dengan isolated namespace & routing)
- Dynamic Route Dispatcher & Parameter Extraction (:id, constraints)
"""

import sys
import time
import re
from typing import Callable, Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field


# ============================================================================
# ANSI Color Palette & Formatters
# ============================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    @staticmethod
    def header(title: str) -> None:
        print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}{'=' * 75}{ANSI.RESET}")
        print(f"{ANSI.BOLD}{ANSI.MAGENTA}>>> {title.upper()} <<<{ANSI.RESET}")
        print(f"{ANSI.BOLD}{ANSI.MAGENTA}{'=' * 75}{ANSI.RESET}")

    @staticmethod
    def log(step: str, detail: str, level: str = "INFO") -> None:
        color = ANSI.CYAN if level == "INFO" else ANSI.GREEN if level == "SUCCESS" else ANSI.YELLOW
        print(f"[{color}{level:7s}{ANSI.RESET}] {ANSI.BOLD}{step:<24}{ANSI.RESET} : {detail}")


# ============================================================================
# 1. RACK SPECIFICATION LAYER (Abstraksi Antarmuka Web Rack)
# ============================================================================
@dataclass
class RackResponse:
    status: int
    headers: Dict[str, str]
    body: List[str]

    def render(self) -> str:
        return "".join(self.body)


class RackMiddleware:
    """
    Simulasi Rack Middleware standard: setiap middleware membungkus downstream app
    mengikuti pola Russian Doll / Onion Architecture.
    """
    def __init__(self, app: Callable[[Dict[str, Any]], RackResponse]):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        raise NotImplementedError


class ExecutionTimerMiddleware(RackMiddleware):
    """Mengukur wall-time komputasi dari inner stack."""
    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        start_time = time.perf_counter()
        response = self.app(env)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Runtime"] = f"{elapsed_ms:.3f}ms"
        ANSI.log("Rack:TimerMiddleware", f"Request diproses dalam {elapsed_ms:.3f} ms")
        return response


class ContentLengthMiddleware(RackMiddleware):
    """Menghitung byte payload dan menginjeksi header HTTP Content-Length."""
    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        response = self.app(env)
        length = sum(len(chunk.encode("utf-8")) for chunk in response.body)
        response.headers["Content-Length"] = str(length)
        return response


# ============================================================================
# 2. ACTIONSUPPORT CONCERN & CALLBACK LIFECYCLE (ActiveSupport::Callbacks)
# ============================================================================
class ActionControllerHalt(Exception):
    """Eksepsi penanda pemutusan callback chain (throw :abort)."""
    def __init__(self, response: RackResponse):
        self.response = response


class ActionControllerBase:
    """
    Simulasi ActionController::Base dengan dukungan lifecycle filters:
    before_action, after_action, dan around_action.
    """
    def __init__(self):
        self.before_actions: List[Tuple[str, Optional[List[str]]]] = []
        self.after_actions: List[Tuple[str, Optional[List[str]]]] = []
        self.params: Dict[str, Any] = {}
        self.env: Dict[str, Any] = {}

    def add_before_action(self, method_name: str, only: Optional[List[str]] = None) -> None:
        self.before_actions.append((method_name, only))

    def add_after_action(self, method_name: str, only: Optional[List[str]] = None) -> None:
        self.after_actions.append((method_name, only))

    def render(self, body_text: str, status: int = 200, content_type: str = "application/json") -> RackResponse:
        return RackResponse(
            status=status,
            headers={"Content-Type": content_type},
            body=[body_text]
        )

    def process_action(self, action_name: str, env: Dict[str, Any], params: Dict[str, Any]) -> RackResponse:
        self.env = env
        self.params = params

        try:
            # 1. Jalankan before_action callbacks
            for callback_name, only_actions in self.before_actions:
                if only_actions is None or action_name in only_actions:
                    callback_fn = getattr(self, callback_name, None)
                    if callable(callback_fn):
                        ANSI.log("Controller:Callback", f"Menjalankan before_action: '{callback_name}'")
                        callback_fn()

            # 2. Eksekusi Action Controller Inti
            action_fn = getattr(self, action_name, None)
            if not callable(action_fn):
                return self.render(f'{{"error": "Action {action_name} tidak ditemukan"}}', 404)

            ANSI.log("Controller:Action", f"Menjalankan action '{self.__class__.__name__}#{action_name}'")
            response = action_fn()

            # 3. Jalankan after_action callbacks
            for callback_name, only_actions in self.after_actions:
                if only_actions is None or action_name in only_actions:
                    callback_fn = getattr(self, callback_name, None)
                    if callable(callback_fn):
                        ANSI.log("Controller:Callback", f"Menjalankan after_action: '{callback_name}'")
                        callback_fn()

            return response

        except ActionControllerHalt as halt:
            ANSI.log("Controller:Halt", f"Callback chain dihentikan secara prematur (halt)", "WARN")
            return halt.response


# ============================================================================
# 3. RAILS ROUTER & ROUTE COMPILER (ActionDispatch::Journey Sim)
# ============================================================================
@dataclass
class Route:
    method: str
    path_pattern: str
    regex: re.Pattern
    param_names: List[str]
    controller_cls: type
    action_name: str


class ActionDispatchRouter:
    """Mesin routing Rails yang mengompilasi path parametrik menjadi Regex."""
    def __init__(self):
        self.routes: List[Route] = []

    def draw(self, method: str, path: str, controller_cls: type, action_name: str) -> None:
        param_names = re.findall(r":([a-zA-Z_][a-zA-Z0-9_]*)", path)
        regex_path = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", r"(?P<\1>[^/]+)", path)
        compiled_regex = re.compile(f"^{regex_path}$")

        self.routes.append(Route(
            method=method.upper(),
            path_pattern=path,
            regex=compiled_regex,
            param_names=param_names,
            controller_cls=controller_cls,
            action_name=action_name
        ))

    def recognize_route(self, method: str, path: str) -> Optional[Tuple[Route, Dict[str, Any]]]:
        for route in self.routes:
            if route.method == method.upper():
                match = route.regex.match(path)
                if match:
                    return route, match.groupdict()
        return None


# ============================================================================
# 4. RAILS ENGINE ARCHITECTURE (Modular Sub-Applications)
# ============================================================================
class RailsEngine:
    """
    Abstraksi Rails Engine: Unit independen dengan router, controller,
    dan middleware sendiri yang dapat dimuat ke Root Application.
    """
    def __init__(self, engine_name: str, isolated: bool = True):
        self.engine_name = engine_name
        self.isolated = isolated
        self.router = ActionDispatchRouter()
        self.setup_routes()

    def setup_routes(self) -> None:
        """Override untuk mendefinisikan rute internal Engine."""
        pass

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        path_info = env.get("PATH_INFO", "/")
        method = env.get("REQUEST_METHOD", "GET")

        match_result = self.router.recognize_route(method, path_info)
        if not match_result:
            return RackResponse(404, {"Content-Type": "application/json"}, [f'{{"error": "Rute Engine {self.engine_name} 404"}}'])

        route, params = match_result
        controller_instance = route.controller_cls()
        return controller_instance.process_action(route.action_name, env, params)


# ============================================================================
# 5. DOMAIN IMPLEMENTATION: CONTROLLERS & ENGINE MODULES
# ============================================================================
class UsersController(ActionControllerBase):
    """Root Application Controller."""
    def __init__(self):
        super().__init__()
        self.add_before_action("authenticate_token", only=["create", "destroy"])
        self.add_before_action("set_user", only=["show"])
        self.add_after_action("audit_log", only=["show", "create"])
        self.current_user: Optional[str] = None

    def authenticate_token(self) -> None:
        auth_header = self.env.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer SECRET_KEY"):
            raise ActionControllerHalt(self.render('{"error": "401 Unauthorized"}', 401))

    def set_user(self) -> None:
        user_id = self.params.get("id")
        ANSI.log("UsersController", f"Memuat rekaman database untuk User ID={user_id}")
        self.current_user = f"UserRecord_#{user_id}"

    def audit_log(self) -> None:
        ANSI.log("UsersController", "Menulis jejak log audit keamanan ke sinkronisasi stream")

    def index(self) -> RackResponse:
        return self.render('{"data": [{"id": 1, "name": "Budi"}, {"id": 2, "name": "Siti"}]}')

    def show(self) -> RackResponse:
        return self.render(f'{{"id": {self.params.get("id")}, "entity": "{self.current_user}"}}')

    def create(self) -> RackResponse:
        return self.render('{"message": "User berhasil dibuat"}', 201)


class AdminMetricsController(ActionControllerBase):
    """Engine Controller (Terisolasi di dalam Engine Admin)."""
    def __init__(self):
        super().__init__()
        self.add_before_action("verify_admin_role")

    def verify_admin_role(self) -> None:
        role = self.env.get("HTTP_X_USER_ROLE", "guest")
        if role != "admin":
            raise ActionControllerHalt(self.render('{"error": "403 Forbidden: Hanya Admin"}', 403))

    def stats(self) -> RackResponse:
        return self.render('{"engine": "AdminEngine", "cpu_usage": "12%", "active_nodes": 4}')


class AdminEngine(RailsEngine):
    """Engine terisolasi yang menangani analitik administratif."""
    def setup_routes(self) -> None:
        self.router.draw("GET", "/stats", AdminMetricsController, "stats")


# ============================================================================
# 6. ROOT APPLICATION (MAIN DISPATCHER DENGAN MOUNTED ENGINES)
# ============================================================================
class RailsApplication:
    def __init__(self):
        self.router = ActionDispatchRouter()
        self.mounted_engines: Dict[str, RailsEngine] = {}
        self.middleware_stack: List[type] = [ContentLengthMiddleware, ExecutionTimerMiddleware]

    def mount(self, engine: RailsEngine, at_prefix: str) -> None:
        prefix = at_prefix.rstrip("/")
        self.mounted_engines[prefix] = engine
        ANSI.log("Application:Mount", f"Engine [{engine.engine_name}] dimuat pada namespace: '{prefix}'")

    def build_rack_app(self) -> Callable[[Dict[str, Any]], RackResponse]:
        """Menyusun seluruh pipeline middleware dan routing menjadi callable tunggal."""
        def root_dispatcher(env: Dict[str, Any]) -> RackResponse:
            path = env.get("PATH_INFO", "/")

            # A. Verifikasi apakah rute menuju Mounted Rails Engine
            for prefix, engine in self.mounted_engines.items():
                if path.startswith(prefix):
                    engine_path = path[len(prefix):] or "/"
                    child_env = env.copy()
                    child_env["PATH_INFO"] = engine_path
                    ANSI.log("Router:Dispatch", f"Mendelegasikan rute '{path}' -> Engine '{engine.engine_name}' ({engine_path})")
                    return engine(child_env)

            # B. Dispatching Aplikasi Induk (Root App)
            method = env.get("REQUEST_METHOD", "GET")
            route_match = self.router.recognize_route(method, path)

            if route_match:
                route, params = route_match
                ANSI.log("Router:Dispatch", f"Rute cocok: {route.method} {route.path_pattern}")
                controller = route.controller_cls()
                return controller.process_action(route.action_name, env, params)

            return RackResponse(404, {"Content-Type": "application/json"}, ['{"error": "404 Route Not Found"}'])

        # Susun middleware (Inversi susunan agar dieksekusi dari terluar ke terdalam)
        app: Callable[[Dict[str, Any]], RackResponse] = root_dispatcher
        for middleware_cls in reversed(self.middleware_stack):
            app = middleware_cls(app)
        return app


# ============================================================================
# RUNTIME LAB VERIFICATION & SUITE TEST
# ============================================================================
def execute_test_request(app_entrypoint: Callable[[Dict[str, Any]], RackResponse],
                         title: str,
                         method: str,
                         path: str,
                         headers: Optional[Dict[str, str]] = None) -> None:
    ANSI.header(title)
    env: Dict[str, Any] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
    }
    if headers:
        for k, v in headers.items():
            rack_key = f"HTTP_{k.upper().replace('-', '_')}"
            env[rack_key] = v

    print(f"{ANSI.BOLD}REQUEST -> {method} {path}{ANSI.RESET}")
    response = app_entrypoint(env)

    status_color = ANSI.GREEN if response.status < 400 else ANSI.RED
    print(f"\n{ANSI.BOLD}RESPONSE HEADERS:{ANSI.RESET}")
    for hk, hv in response.headers.items():
        print(f"  {hk}: {hv}")

    print(f"\n{ANSI.BOLD}STATUS CODE : {status_color}{response.status}{ANSI.RESET}")
    print(f"{ANSI.BOLD}PAYLOAD     : {ANSI.YELLOW}{response.render()}{ANSI.RESET}")


def main() -> None:
    print(f"{ANSI.BOLD}{ANSI.CYAN}MEMULAI INISIALISASI ARSITEKTUR ENGINE & LIFECYCLE CONTROLLER{ANSI.RESET}")

    # 1. Bootstrapping Root Application
    rails_app = RailsApplication()

    # 2. Definisikan Route Root
    rails_app.router.draw("GET", "/users", UsersController, "index")
    rails_app.router.draw("GET", "/users/:id", UsersController, "show")
    rails_app.router.draw("POST", "/users", UsersController, "create")

    # 3. Mount Isolated Engine
    admin_engine = AdminEngine("AdminEngine", isolated=True)
    rails_app.mount(admin_engine, at_prefix="/admin")

    # 4. Bangun Middleware Stack
    rack_pipeline = rails_app.build_rack_app()

    # Skenario 1: Eksekusi Route Normal dengan Callback Parameters
    execute_test_request(
        rack_pipeline,
        title="Skenario 1: Query Record Berparameter & Lifecycle Callback Chain",
        method="GET",
        path="/users/42"
    )

    # Skenario 2: Eksekusi Terputus (Halt) Akibat Guard Clause Before Action
    execute_test_request(
        rack_pipeline,
        title="Skenario 2: Penolakan Before-Action (401 Unauthorized Halt)",
        method="POST",
        path="/users"
    )

    # Skenario 3: Eksekusi Lolos Autentikasi Menggunakan Token Header
    execute_test_request(
        rack_pipeline,
        title="Skenario 3: Autentikasi Berhasil dengan Bearer Token",
        method="POST",
        path="/users",
        headers={"Authorization": "Bearer SECRET_KEY"}
    )

    # Skenario 4: Akses Mounted Rails Engine (Akses Ditolak - Non-Admin)
    execute_test_request(
        rack_pipeline,
        title="Skenario 4: Engine Dispatching Terisolasi - Validasi Role Gagal",
        method="GET",
        path="/admin/stats",
        headers={"X-User-Role": "guest"}
    )

    # Skenario 5: Akses Mounted Rails Engine (Akses Diterima - Admin)
    execute_test_request(
        rack_pipeline,
        title="Skenario 5: Engine Dispatching Terisolasi - Validasi Role Berhasil",
        method="GET",
        path="/admin/stats",
        headers={"X-User-Role": "admin"}
    )

    # Skenario 6: Rute Tidak Ditemukan (404 Fallback)
    execute_test_request(
        rack_pipeline,
        title="Skenario 6: Penanganan 404 Route Not Found",
        method="GET",
        path="/api/v1/unknown"
    )

    print(f"\n{ANSI.BOLD}{ANSI.GREEN}Seluruh demonstrasi simulasi arsitektur Rails selesai dieksekusi.{ANSI.RESET}\n")


if __name__ == "__main__":
    main()
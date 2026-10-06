#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Rack & Pemrograman Jaringan Ruby
BAB-08: Network Programming & Rack Architecture

Skrip mandiri ini mengimplementasikan replika prinsip Rack Ruby:
1. Raw HTTP Request Parsing ke Rack Environment Hash (env).
2. Konvensi Rack Callable: app.call(env) -> [status, headers, body].
3. Pola Middleware Berlapis (Onion Architecture / Pipeline Pattern).
4. Error Handling & Request Logging Middleware.
"""

import sys
import time
from typing import Callable, Dict, List, Tuple, Any

# ==============================================================================
# Terminal ANSI Color Formatting
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"


def print_banner():
    print(f"{Color.CYAN}{Color.BOLD}" + "=" * 70 + f"{Color.RESET}")
    print(f"{Color.YELLOW}{Color.BOLD}   LAB RUBY RACK ARCHITECTURE & NETWORK SIMULATOR (PYTHON 3){Color.RESET}")
    print(f"{Color.CYAN}" + "=" * 70 + f"{Color.RESET}")
    print(f"{Color.WHITE}Simulasi standar protokol Rack: [status, headers, body]{Color.RESET}\n")


# ==============================================================================
# Type Definitions
# ==============================================================================
# Sesuai spesifikasi Rack Ruby:
# env: Hash/Dict
# return: [status_code (int), headers (dict), body (iterable/list)]
RackResponse = Tuple[int, Dict[str, str], List[str]]
RackApp = Callable[[Dict[str, Any]], RackResponse]


# ==============================================================================
# 1. HTTP Request Parser (Simulasi Socket TCP Layer)
# ==============================================================================
def parse_raw_http_to_rack_env(raw_http: str) -> Dict[str, Any]:
    """
    Mengubah raw socket payload HTTP/1.1 menjadi Rack environment dictionary.
    """
    lines = raw_http.strip().split("\r\n")
    if not lines or not lines[0]:
        raise ValueError("Invalid HTTP Request: Empty payload")

    # Request Line: METHOD PATH PROTOCOL
    request_line = lines[0].split()
    if len(request_line) < 3:
        raise ValueError(f"Malformed Request-Line: {lines[0]}")

    method, path, protocol = request_line[0], request_line[1], request_line[2]

    # Parsing Query String jika ada
    query_string = ""
    path_info = path
    if "?" in path:
        path_info, query_string = path.split("?", 1)

    rack_env: Dict[str, Any] = {
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": "",
        "PATH_INFO": path_info,
        "QUERY_STRING": query_string,
        "SERVER_PROTOCOL": protocol,
        "rack.version": [1, 3],
        "rack.url_scheme": "http",
        "rack.errors": sys.stderr,
        "rack.multithread": True,
        "rack.multiprocess": False,
        "rack.run_once": False,
    }

    # Headers parsing
    i = 1
    while i < len(lines) and lines[i]:
        header_line = lines[i]
        if ":" in header_line:
            key, val = header_line.split(":", 1)
            norm_key = "HTTP_" + key.strip().upper().replace("-", "_")
            rack_env[norm_key] = val.strip()
        i += 1

    # Body payload
    body_payload = "\r\n".join(lines[i + 1:]) if i + 1 < len(lines) else ""
    rack_env["rack.input"] = body_payload

    return rack_env


# ==============================================================================
# 2. Inti Aplikasi Rack (Endpoint Ruby App)
# ==============================================================================
class CoreRubyApp:
    """Aplikasi web Rack murni: Callable yang menerima env dan mereturn tuple."""

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        path = env.get("PATH_INFO", "/")
        method = env.get("REQUEST_METHOD", "GET")

        if path == "/" and method == "GET":
            status = 200
            headers = {"Content-Type": "text/html; charset=utf-8"}
            body = ["<h1>Selamat Datang di Rack Core Application</h1>\n"]
            return status, headers, body

        elif path == "/api/status" and method == "GET":
            status = 200
            headers = {"Content-Type": "application/json"}
            body = ['{"service": "ruby-rack-core", "status": "operational", "latency_ms": 1.2}\n']
            return status, headers, body

        elif path == "/crash":
            # Simulasi unhandled exception di controller
            raise RuntimeError("DatabaseConnectionLost: Simulasi kegagalan internal server.")

        else:
            status = 404
            headers = {"Content-Type": "text/plain"}
            body = [f"404 Not Found: Rute '{path}' tidak dikenali.\n"]
            return status, headers, body


# ==============================================================================
# 3. Rack Middleware (Pola Lapisan Bawang / Pipeline)
# ==============================================================================
class RequestLoggerMiddleware:
    """Middleware 1: Mencatat durasi pemrosesan dan status output (mirip Rack::Logger)."""

    def __init__(self, app: RackApp):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        start_time = time.perf_counter()
        method = env.get("REQUEST_METHOD")
        path = env.get("PATH_INFO")

        print(f"  {Color.BLUE}--> [Logger IN]{Color.RESET} {method} {path}")
        
        status, headers, body = self.app(env)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        status_color = Color.GREEN if status < 400 else Color.RED
        print(f"  {Color.BLUE}<-- [Logger OUT]{Color.RESET} Status: {status_color}{status}{Color.RESET} ({elapsed_ms:.3f} ms)")
        
        headers["X-Runtime"] = f"{elapsed_ms:.4f}ms"
        return status, headers, body


class AuthenticationMiddleware:
    """Middleware 2: Memverifikasi Bearer Token untuk rute /api/*."""

    def __init__(self, app: RackApp):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        path = env.get("PATH_INFO", "")
        if path.startswith("/api"):
            auth_header = env.get("HTTP_AUTHORIZATION", "")
            if auth_header != "Bearer ruby-secret-token":
                print(f"  {Color.YELLOW}[Auth]{Color.RESET} Unauthorized access attempt ke {path}")
                return 401, {"Content-Type": "application/json"}, ['{"error": "Unauthorized: Token tidak valid"}\n']
        
        return self.app(env)


class ExceptionHandlerMiddleware:
    """Middleware 3: Menangkap unhandled exception (mirip Rack::ShowExceptions)."""

    def __init__(self, app: RackApp):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        try:
            return self.app(env)
        except Exception as exc:
            print(f"  {Color.RED}{Color.BOLD}[Rescue Caught]{Color.RESET} {str(exc)}")
            status = 500
            headers = {"Content-Type": "application/json", "X-Handled-By": "RackExceptionHandler"}
            body = [f'{{"error": "InternalServerError", "message": "{str(exc)}"}}\n']
            return status, headers, body


# ==============================================================================
# 4. Rack Builder (Perakit Stack)
# ==============================================================================
class RackBuilder:
    """Simulasi DSL Rack::Builder (seperti isi config.ru)."""

    def __init__(self):
        self.middlewares: List[Callable[[RackApp], RackApp]] = []
        self.app: RackApp = None

    def use(self, middleware_cls, *args, **kwargs):
        self.middlewares.append(lambda app: middleware_cls(app, *args, **kwargs))
        return self

    def run(self, app: RackApp):
        self.app = app

    def to_app(self) -> RackApp:
        if not self.app:
            raise ValueError("Tidak ada aplikasi target yang didefinisikan dengan run()")
        
        composed = self.app
        for middleware in reversed(self.middlewares):
            composed = middleware(composed)
        return composed


# ==============================================================================
# 5. Interface Interaktif CLI Lab
# ==============================================================================
def execute_request_cycle(pipeline: RackApp, raw_request: str, desc: str):
    print(f"\n{Color.CYAN}{Color.BOLD}>>> Simulasi Kasus: {desc}{Color.RESET}")
    print(f"{Color.WHITE}Raw Request Payload:\n" + "-" * 30)
    for line in raw_request.strip().split("\r\n"):
        print(f"  {line}")
    print("-" * 30 + f"{Color.RESET}")

    env = parse_raw_http_to_rack_env(raw_request)
    print(f"{Color.MAGENTA}[Pipeline Execution Start]{Color.RESET}")
    status, headers, body = pipeline(env)
    print(f"{Color.MAGENTA}[Pipeline Execution End]{Color.RESET}")

    print(f"\n{Color.GREEN}{Color.BOLD}Rack Triple Result:{Color.RESET}")
    print(f"  HTTP Status Code : {Color.BOLD}{status}{Color.RESET}")
    print("  Response Headers :")
    for k, v in headers.items():
        print(f"    - {k}: {v}")
    print(f"  Response Body    : {''.join(body).strip()}\n")


def run_interactive_lab():
    # Bangun Pipeline Rack sesuai konfigurasi config.ru
    builder = RackBuilder()
    builder.use(ExceptionHandlerMiddleware)
    builder.use(RequestLoggerMiddleware)
    builder.use(AuthenticationMiddleware)
    builder.run(CoreRubyApp())

    rack_pipeline = builder.to_app()
    print_banner()

    menu = (
        f"{Color.BOLD}PILIH SKENARIO SIMULASI RACK:{Color.RESET}\n"
        "1. GET / (Rute Dasar HTML Berhasil - 200 OK)\n"
        "2. GET /api/status Tanpa Auth (Ditolak Middleware Auth - 401 Unauthorized)\n"
        "3. GET /api/status Dengan Token Benar (Lolos Middleware - 200 OK)\n"
        "4. GET /crash (Simulasi Exception Ditangani Middleware Rescue - 500)\n"
        "5. GET /unknown (Rute Tidak Ditemukan - 404 Not Found)\n"
        "6. Inspeksi Struktur Dictionary Rack 'env'\n"
        "7. Keluar\n"
    )

    requests_map = {
        "1": (
            "GET / HTTP/1.1\r\nHost: localhost:9292\r\nUser-Agent: curl/7.88.1\r\nAccept: */*\r\n\r\n",
            "Permintaan dasar ke root URL",
        ),
        "2": (
            "GET /api/status HTTP/1.1\r\nHost: localhost:9292\r\nUser-Agent: browser/1.0\r\n\r\n",
            "Akses API privat tanpa Header Authorization",
        ),
        "3": (
            "GET /api/status HTTP/1.1\r\nHost: localhost:9292\r\nAuthorization: Bearer ruby-secret-token\r\n\r\n",
            "Akses API privat dengan Bearer Token valid",
        ),
        "4": (
            "GET /crash HTTP/1.1\r\nHost: localhost:9292\r\n\r\n",
            "Akses rute berbahaya yang memicu unhandled RuntimeError",
        ),
        "5": (
            "GET /missing-path HTTP/1.1\r\nHost: localhost:9292\r\n\r\n",
            "Akses rute non-existent",
        ),
    }

    while True:
        print(menu)
        try:
            pilihan = input(f"{Color.YELLOW}Masukkan pilihan (1-7): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if pilihan in requests_map:
            raw_req, desc = requests_map[pilihan]
            execute_request_cycle(rack_pipeline, raw_req, desc)
        elif pilihan == "6":
            raw_sample = "GET /api/test?debug=true HTTP/1.1\r\nHost: localhost:9292\r\nCustom-Header: DemoVal\r\n\r\n"
            sample_env = parse_raw_http_to_rack_env(raw_sample)
            print(f"\n{Color.CYAN}--- Struktur Rack Env (CGI-derived hash) ---{Color.RESET}")
            for k, v in sample_env.items():
                print(f"  {Color.BOLD}{k:<20}{Color.RESET}: {v}")
            print()
        elif pilihan == "7":
            print(f"{Color.GREEN}Terima kasih telah menjalankan lab arsitektur Rack Ruby!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()

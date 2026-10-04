#!/usr/bin/env python3
"""
Lab Exercise: Fondasi Inti Arsitektur Backend
Modul: BAB-02 Materi Lanjutan - Backend Beginner

Skrip ini mensimulasikan alur kerja inti server backend modern:
1. HTTP Request/Response Model (Status Codes, Headers, Body)
2. Middleware Chain (Logging, Authentication, Rate Limiting)
3. Routing & Handler Dispatching
4. In-Memory Data Store (CRUD)
5. Structured Error Handling & Response Serialization
"""

import json
import time
import uuid
from typing import Callable, Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palette untuk Visualisasi Terminal
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def banner(text: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{text.center(65)}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}\n")


def log_event(stage: str, message: str, color: str = Color.WHITE) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} {Color.BOLD}[{stage}]{Color.RESET} {color}{message}{Color.RESET}")


# ==============================================================================
# Model HTTP Mini: Request & Response
# ==============================================================================
class Request:
    def __init__(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict] = None,
    ):
        self.method = method.upper()
        self.path = path
        self.headers = headers or {}
        self.body = body or {}
        self.context: Dict = {}  # Metadata yang diteruskan antar-middleware


class Response:
    def __init__(
        self,
        status_code: int = 200,
        body: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.body = body or {}
        self.headers = headers or {"Content-Type": "application/json"}

    def to_terminal_view(self) -> str:
        color = Color.GREEN if self.status_code < 400 else Color.RED
        status_text = {
            200: "200 OK",
            201: "201 Created",
            400: "400 Bad Request",
            401: "401 Unauthorized",
            404: "404 Not Found",
            429: "429 Too Many Requests",
            500: "500 Internal Server Error",
        }.get(self.status_code, f"{self.status_code} Unknown")

        out = [
            f"{Color.BOLD}HTTP Status:{Color.RESET} {color}{status_text}{Color.RESET}",
            f"{Color.BOLD}Response Headers:{Color.RESET} {Color.DIM}{json.dumps(self.headers)}{Color.RESET}",
            f"{Color.BOLD}Response Payload:{Color.RESET}",
            f"{Color.CYAN}{json.dumps(self.body, indent=2)}{Color.RESET}"
        ]
        return "\n".join(out)


# ==============================================================================
# Database In-Memory & State
# ==============================================================================
class Database:
    def __init__(self):
        self.users: Dict[str, Dict] = {
            "usr_admin": {"id": "usr_admin", "name": "System Administrator", "role": "admin"},
            "usr_learner": {"id": "usr_learner", "name": "Budi Santoso", "role": "student"},
        }
        self.posts: Dict[str, Dict] = {
            "post_1": {
                "id": "post_1",
                "title": "Pengantar Backend Engineering",
                "author": "usr_admin",
                "views": 42
            }
        }

    def reset(self):
        self.__init__()


# ==============================================================================
# Middleware Layer
# ==============================================================================
MiddlewareHandler = Callable[[Request, Callable[[], Response]], Response]

class Pipeline:
    def __init__(self):
        self.middlewares: List[MiddlewareHandler] = []
        self.request_counters: Dict[str, List[float]] = {}

    def use(self, mw: MiddlewareHandler):
        self.middlewares.append(mw)

    def execute(self, req: Request, target_handler: Callable[[Request], Response]) -> Response:
        idx = 0

        def next_fn() -> Response:
            nonlocal idx
            if idx < len(self.middlewares):
                current_mw = self.middlewares[idx]
                idx += 1
                return current_mw(req, next_fn)
            return target_handler(req)

        return next_fn()


# ==============================================================================
# Implementasi Middleware Nyata
# ==============================================================================
def logger_middleware(req: Request, next_fn: Callable[[], Response]) -> Response:
    start_t = time.perf_counter()
    log_event("MIDDLEWARE:LOG", f">> Masuk: {req.method} {req.path}", Color.MAGENTA)
    
    res = next_fn()
    
    elapsed_ms = (time.perf_counter() - start_t) * 1000
    color = Color.GREEN if res.status_code < 400 else Color.RED
    log_event("MIDDLEWARE:LOG", f"<< Selesai: Status={res.status_code} dalam {elapsed_ms:.2f}ms", color)
    return res


def auth_middleware(req: Request, next_fn: Callable[[], Response]) -> Response:
    # Mengamankan endpoint yang berawalan /api/protected
    if req.path.startswith("/api/protected"):
        auth_header = req.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            log_event("MIDDLEWARE:AUTH", "Penolakan akses: Token tidak valid atau tidak disertakan!", Color.RED)
            return Response(401, {"error": "Unauthorized", "detail": "Missing or invalid Bearer token"})

        token = auth_header.split(" ", 1)[1]
        if token != "secret-token-123":
            log_event("MIDDLEWARE:AUTH", f"Token ditolak: '{token}' tidak sah", Color.RED)
            return Response(401, {"error": "Unauthorized", "detail": "Invalid token credential"})

        req.context["user_id"] = "usr_admin"
        req.context["authenticated"] = True
        log_event("MIDDLEWARE:AUTH", "Autentikasi berhasil untuk user: usr_admin", Color.GREEN)

    return next_fn()


class RateLimiterMiddleware:
    def __init__(self, max_requests: int = 3, window_seconds: float = 5.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []

    def __call__(self, req: Request, next_fn: Callable[[], Response]) -> Response:
        now = time.time()
        # Buang request lama di luar window
        self.requests = [t for t in self.requests if now - t < self.window_seconds]
        
        if len(self.requests) >= self.max_requests:
            log_event("MIDDLEWARE:RATE_LIMIT", f"Rate limit terlampaui ({len(self.requests)}/{self.max_requests})!", Color.YELLOW)
            return Response(429, {
                "error": "Too Many Requests",
                "message": f"Maksimal {self.max_requests} request per {self.window_seconds} detik"
            })

        self.requests.append(now)
        log_event("MIDDLEWARE:RATE_LIMIT", f"Quota aman ({len(self.requests)}/{self.max_requests})", Color.DIM)
        return next_fn()


# ==============================================================================
# Router & Controllers
# ==============================================================================
class Router:
    def __init__(self, db: Database):
        self.db = db
        self.routes: Dict[Tuple[str, str], Callable[[Request], Response]] = {}
        self._register_routes()

    def _register_routes(self):
        self.routes[("GET", "/health")] = self.handle_health
        self.routes[("GET", "/api/posts")] = self.handle_get_posts
        self.routes[("POST", "/api/posts")] = self.handle_create_post
        self.routes[("GET", "/api/protected/profile")] = self.handle_get_profile

    def handle_health(self, req: Request) -> Response:
        return Response(200, {"status": "UP", "timestamp": time.time(), "engine": "Python-Backend-Core"})

    def handle_get_posts(self, req: Request) -> Response:
        posts_list = list(self.db.posts.values())
        return Response(200, {"count": len(posts_list), "data": posts_list})

    def handle_create_post(self, req: Request) -> Response:
        title = req.body.get("title")
        author = req.body.get("author", "usr_learner")
        
        if not title:
            return Response(400, {"error": "Validation Error", "field": "title", "message": "Judul wajib diisi"})

        post_id = f"post_{uuid.uuid4().hex[:6]}"
        new_post = {"id": post_id, "title": title, "author": author, "views": 0}
        self.db.posts[post_id] = new_post

        return Response(201, {"message": "Postingan berhasil dibuat", "item": new_post})

    def handle_get_profile(self, req: Request) -> Response:
        user_id = req.context.get("user_id")
        user = self.db.users.get(user_id)
        if not user:
            return Response(404, {"error": "User tidak ditemukan"})
        return Response(200, {"user": user, "message": "Area terlindungi berhasil diakses"})

    def dispatch(self, req: Request) -> Response:
        key = (req.method, req.path)
        handler = self.routes.get(key)
        if not handler:
            return Response(404, {"error": "Route Not Found", "method": req.method, "path": req.path})
        return handler(req)


# ==============================================================================
# Server Simulator App
# ==============================================================================
class BackendApplication:
    def __init__(self):
        self.db = Database()
        self.pipeline = Pipeline()
        self.router = Router(self.db)
        self.rate_limiter = RateLimiterMiddleware(max_requests=3, window_seconds=4.0)

        # Susun pipeline middleware
        self.pipeline.use(logger_middleware)
        self.pipeline.use(self.rate_limiter)
        self.pipeline.use(auth_middleware)

    def handle_http_request(self, req: Request) -> Response:
        return self.pipeline.execute(req, self.router.dispatch)


# ==============================================================================
# CLI Interactive Loop & Test Scenarios
# ==============================================================================
def run_scenario(app: BackendApplication, title: str, req: Request) -> None:
    print(f"\n{Color.BOLD}{Color.YELLOW}>>> SCENARIO: {title}{Color.RESET}")
    print(f"{Color.DIM}Request: {req.method} {req.path} | Headers: {req.headers} | Body: {req.body}{Color.RESET}")
    time.sleep(0.3)
    
    response = app.handle_http_request(req)
    
    print("\n--- Output Response HTTP ---")
    print(response.to_terminal_view())
    print("-" * 40)


def automated_lab_tour(app: BackendApplication):
    banner("LAB SIMULATOR: 5 TAHAPAN SIKLUS HIDUP BACKEND")

    # 1. Healthcheck (GET 200)
    app.rate_limiter.requests.clear()
    run_scenario(
        app,
        "1. Basic GET Endpoint (Healthcheck)",
        Request("GET", "/health")
    )

    # 2. In-Memory CRUD (POST 201)
    app.rate_limiter.requests.clear()
    run_scenario(
        app,
        "2. Validasi & Create Data (POST 201)",
        Request("POST", "/api/posts", body={"title": "Mastering Async I/O & Architecture"})
    )

    # 3. Validasi Error (POST 400)
    app.rate_limiter.requests.clear()
    run_scenario(
        app,
        "3. Validasi Gagal (Bad Request 400)",
        Request("POST", "/api/posts", body={})
    )

    # 4. Auth Middleware Failure (GET 401)
    app.rate_limiter.requests.clear()
    run_scenario(
        app,
        "4. Akses Protected Route Tanpa Token (Unauthorized 401)",
        Request("GET", "/api/protected/profile")
    )

    # 5. Auth Middleware Success (GET 200)
    app.rate_limiter.requests.clear()
    run_scenario(
        app,
        "5. Akses Protected Route Dengan Bearer Token Valid",
        Request("GET", "/api/protected/profile", headers={"Authorization": "Bearer secret-token-123"})
    )

    # 6. Rate Limiter Trigger (429)
    app.rate_limiter.requests.clear()
    print(f"\n{Color.BOLD}{Color.YELLOW}>>> 6. Rate Limiting Stress Test (Batas: 3 req / 4 detik){Color.RESET}")
    for i in range(1, 5):
        log_event("STRESS_TEST", f"Mengirim request #{i}...", Color.CYAN)
        res = app.handle_http_request(Request("GET", "/health"))
        if res.status_code == 429:
            log_event("STRESS_TEST", f"Request #{i} terblokir dengan HTTP 429!", Color.RED)
            print(res.to_terminal_view())
            break
        time.sleep(0.1)


def interactive_menu(app: BackendApplication):
    while True:
        banner("INTERACTIVE BACKEND LAB EXPLORER")
        print(f"[{Color.GREEN}1{Color.RESET}] Jalankan Full Automated Tour (5 Skenario Arsitektur)")
        print(f"[{Color.GREEN}2{Color.RESET}] GET /health (Health Check)")
        print(f"[{Color.GREEN}3{Color.RESET}] GET /api/posts (Lihat Database Postingan)")
        print(f"[{Color.GREEN}4{Color.RESET}] POST /api/posts (Input Data Baru)")
        print(f"[{Color.GREEN}5{Color.RESET}] GET /api/protected/profile (Uji Autentikasi)")
        print(f"[{Color.GREEN}6{Color.RESET}] Reset Database & Quota")
        print(f"[{Color.RED}0{Color.RESET}] Keluar dari Lab")
        
        choice = input(f"\n{Color.BOLD}Pilih opsi [0-6]: {Color.RESET}").strip()

        if choice == "1":
            automated_lab_tour(app)
        elif choice == "2":
            run_scenario(app, "Cek Kesehatan Layanan", Request("GET", "/health"))
        elif choice == "3":
            run_scenario(app, "Fetch Daftar Postingan", Request("GET", "/api/posts"))
        elif choice == "4":
            title = input("Masukkan judul postingan: ").strip()
            run_scenario(app, "Simpan Post Baru", Request("POST", "/api/posts", body={"title": title}))
        elif choice == "5":
            token_input = input("Masukkan Token (tekan Enter jika ingin uji coba tanpa token): ").strip()
            headers = {}
            if token_input:
                headers["Authorization"] = f"Bearer {token_input}"
            run_scenario(app, "Uji Akses Protected Area", Request("GET", "/api/protected/profile", headers=headers))
        elif choice == "6":
            app.db.reset()
            app.rate_limiter.requests.clear()
            print(f"\n{Color.GREEN}[V] Database dan quota rate-limit berhasil direset ke kondisi awal.{Color.RESET}")
        elif choice == "0":
            print(f"\n{Color.CYAN}Terima kasih telah belajar fondasi backend. Sesi selesai!{Color.RESET}\n")
            break
        else:
            print(f"\n{Color.RED}[!] Pilihan tidak valid.{Color.RESET}")

        input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")


if __name__ == "__main__":
    app_instance = BackendApplication()
    # Jika dijalankan secara non-interaktif/scripted, tampilkan automated tour
    import sys
    if not sys.stdin.isatty():
        automated_lab_tour(app_instance)
    else:
        interactive_menu(app_instance)

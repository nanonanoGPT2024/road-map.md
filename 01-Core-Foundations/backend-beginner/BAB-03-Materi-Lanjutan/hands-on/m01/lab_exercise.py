#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Backend Core Foundations - Advanced Concepts (BAB-03)
Topik: Middleware Pipeline, Authentication (Token-based), Request Validation,
       Error Handling Global, dan RESTful Resource Lifecycle Simulation.
"""

import sys
import time
import json
import uuid
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field

# --- ANSI Color Palette ---
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"
COLOR_BLUE = "\033[34m"
COLOR_MAGENTA = "\033[35m"

def c_print(color: str, text: str):
    print(f"{color}{text}{COLOR_RESET}")

def header(text: str):
    print(f"\n{COLOR_BOLD}{COLOR_BLUE}{'=' * 65}{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}  {text}{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_BLUE}{'=' * 65}{COLOR_RESET}")

# --- Data Structures & Context ---

@dataclass
class HttpRequest:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HttpResponse:
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)

class HttpError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

# --- Middleware Implementations ---

HandlerType = Callable[[HttpRequest], HttpResponse]
MiddlewareType = Callable[[HttpRequest, HandlerType], HttpResponse]

def logging_middleware(req: HttpRequest, next_handler: HandlerType) -> HttpResponse:
    start_time = time.time()
    c_print(COLOR_MAGENTA, f"[LOG] Incoming Request -> {req.method} {req.path}")
    res = next_handler(req)
    duration_ms = (time.time() - start_time) * 1000
    color = COLOR_GREEN if res.status_code < 400 else COLOR_RED
    c_print(COLOR_MAGENTA, f"[LOG] Response Dispatched <- {color}{res.status_code}{COLOR_MAGENTA} ({duration_ms:.2f}ms)")
    return res

def auth_middleware(req: HttpRequest, next_handler: HandlerType) -> HttpResponse:
    # Protected paths: /api/v1/protected/*
    if req.path.startswith("/api/v1/protected"):
        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HttpError(401, "UNAUTHORIZED", "Missing or malformed Authorization header. Expected 'Bearer <token>'.")
        
        token = auth_header.replace("Bearer ", "").strip()
        # Mock token validation
        valid_tokens = {
            "token-admin-123": {"sub": "usr-admin", "role": "admin", "name": "Budi Hartono"},
            "token-user-456": {"sub": "usr-regular", "role": "member", "name": "Siti Rahma"}
        }
        
        if token not in valid_tokens:
            raise HttpError(403, "FORBIDDEN", "Token signature expired or invalid identity signature.")
        
        req.context["auth_user"] = valid_tokens[token]
        c_print(COLOR_CYAN, f"[AUTH] Verified: {req.context['auth_user']['name']} ({req.context['auth_user']['role']})")
    
    return next_handler(req)

def validation_middleware(req: HttpRequest, next_handler: HandlerType) -> HttpResponse:
    if req.method in ("POST", "PUT") and req.path == "/api/v1/protected/items":
        required_fields = ["name", "price", "sku"]
        missing = [f for f in required_fields if f not in req.body]
        if missing:
            raise HttpError(422, "VALIDATION_ERROR", f"Payload validation failed. Missing required fields: {missing}")
        if not isinstance(req.body["price"], (int, float)) or req.body["price"] <= 0:
            raise HttpError(422, "VALIDATION_ERROR", "Field 'price' must be a numeric value greater than zero.")
    return next_handler(req)

# --- In-Memory Repository & Controllers ---

DB_ITEMS: Dict[str, Dict[str, Any]] = {
    "item-001": {"id": "item-001", "name": "Mechanical Keyboard Pro", "price": 850000, "sku": "KB-MEC-01", "created_by": "usr-admin"},
    "item-002": {"id": "item-002", "name": "Ergonomic Mesh Chair", "price": 1450000, "sku": "CHR-ERG-02", "created_by": "usr-admin"}
}

def router_dispatch(req: HttpRequest) -> HttpResponse:
    if req.path == "/api/v1/health":
        return HttpResponse(200, body={"status": "UP", "timestamp": int(time.time()), "service": "Core-Backend-Simulator"})
    
    elif req.path == "/api/v1/protected/items":
        if req.method == "GET":
            return HttpResponse(200, body={"data": list(DB_ITEMS.values()), "count": len(DB_ITEMS)})
        elif req.method == "POST":
            item_id = f"item-{str(uuid.uuid4())[:8]}"
            new_item = {
                "id": item_id,
                "name": req.body["name"],
                "price": req.body["price"],
                "sku": req.body["sku"],
                "created_by": req.context["auth_user"]["sub"]
            }
            DB_ITEMS[item_id] = new_item
            return HttpResponse(201, body={"message": "Item created successfully", "item": new_item})
    
    raise HttpError(404, "NOT_FOUND", f"Route endpoint '{req.method} {req.path}' is not registered.")

# --- Application Kernel ---

class MiniBackendKernel:
    def __init__(self):
        self.middlewares: List[MiddlewareType] = []

    def use(self, mw: MiddlewareType):
        self.middlewares.append(mw)

    def handle(self, req: HttpRequest) -> HttpResponse:
        def build_chain(index: int) -> HandlerType:
            if index < len(self.middlewares):
                current_mw = self.middlewares[index]
                return lambda r: current_mw(r, build_chain(index + 1))
            return router_dispatch

        try:
            pipeline = build_chain(0)
            return pipeline(req)
        except HttpError as err:
            return HttpResponse(
                status_code=err.status_code,
                body={"error": {"code": err.error_code, "message": err.message, "status": err.status_code}}
            )
        except Exception as ex:
            return HttpResponse(
                status_code=500,
                body={"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(ex), "status": 500}}
            )

# --- Interactive Terminal CLI ---

def run_interactive_lab():
    app = MiniBackendKernel()
    app.use(logging_middleware)
    app.use(auth_middleware)
    app.use(validation_middleware)

    header("SIMULASI FONDASI BACKEND: MIDDLEWARE, AUTH & ERROR PIPELINE")
    c_print(COLOR_YELLOW, "Skenario Eksplorasi:")
    print(" 1. GET /api/v1/health (Publik, tanpa auth)")
    print(" 2. GET /api/v1/protected/items [Tanpa Token] (Uji 401 Unauthorized)")
    print(" 3. GET /api/v1/protected/items [Token Invalid] (Uji 403 Forbidden)")
    print(" 4. GET /api/v1/protected/items [Token Valid] (Uji 200 OK & Middleware Pipeline)")
    print(" 5. POST /api/v1/protected/items [Payload Invalid] (Uji 422 Unprocessable Entity)")
    print(" 6. POST /api/v1/protected/items [Payload Valid] (Uji 201 Created & State Mutation)")
    print(" 7. GET /api/v1/unknown (Uji 404 Not Found Handling)")
    print(" 0. Jalankan Seluruh Skenario Otomatis (Demo Lengkap) & Keluar")

    def execute_and_inspect(label: str, req: HttpRequest):
        print(f"\n{COLOR_BOLD}{COLOR_CYAN}--- Menjalankan: {label} ---{COLOR_RESET}")
        res = app.handle(req)
        color = COLOR_GREEN if res.status_code < 400 else COLOR_RED
        print(f"{COLOR_BOLD}Hasil Response [HTTP {color}{res.status_code}{COLOR_RESET}{COLOR_BOLD}]:{COLOR_RESET}")
        print(json.dumps(res.body, indent=2, ensure_ascii=False))

    scenarios = {
        "1": ("Health Check Publik", HttpRequest("GET", "/api/v1/health")),
        "2": ("Get Items Protected - No Auth Header", HttpRequest("GET", "/api/v1/protected/items")),
        "3": ("Get Items Protected - Token Palsu", HttpRequest("GET", "/api/v1/protected/items", headers={"Authorization": "Bearer bad-token-999"})),
        "4": ("Get Items Protected - Token Admin Valid", HttpRequest("GET", "/api/v1/protected/items", headers={"Authorization": "Bearer token-admin-123"})),
        "5": ("Create Item - Payload Hilang 'sku' & 'price' Negatif", HttpRequest(
            "POST",
            "/api/v1/protected/items",
            headers={"Authorization": "Bearer token-admin-123"},
            body={"name": "Gaming Mouse", "price": -50000}
        )),
        "6": ("Create Item - Payload Valid", HttpRequest(
            "POST",
            "/api/v1/protected/items",
            headers={"Authorization": "Bearer token-admin-123"},
            body={"name": "Wireless Ultra Mouse", "price": 450000, "sku": "MOU-WL-03"}
        )),
        "7": ("Akses Endpoint Antah Berantah", HttpRequest("GET", "/api/v1/unknown"))
    }

    if not sys.stdin.isatty():
        # Automated non-interactive run
        c_print(COLOR_GREEN, "\n[Mode Non-Interactive Terdeteksi: Menjalankan Seluruh Siklus Tes]")
        for key in sorted(scenarios.keys()):
            lbl, req = scenarios[key]
            execute_and_inspect(lbl, req)
        header("LAB EXERCISE COMPLETED: ALL PATTERNS VERIFIED")
        return

    while True:
        try:
            choice = input(f"\n{COLOR_BOLD}Pilih nomor skenario (0-7, atau 'q' untuk keluar): {COLOR_RESET}").strip()
            if choice in ("q", "exit", "quit"):
                c_print(COLOR_YELLOW, "Selesai. Selamat belajar arsitektur backend!")
                break
            elif choice == "0":
                for key in sorted(scenarios.keys()):
                    lbl, req = scenarios[key]
                    execute_and_inspect(lbl, req)
                header("LAB EXERCISE COMPLETED: ALL PATTERNS VERIFIED")
                break
            elif choice in scenarios:
                lbl, req = scenarios[choice]
                execute_and_inspect(lbl, req)
            else:
                c_print(COLOR_RED, "Pilihan tidak valid, silakan ketik nomor 0 hingga 7.")
        except (KeyboardInterrupt, EOFError):
            print("\nSesi dihentikan.")
            break

if __name__ == "__main__":
    run_interactive_lab()

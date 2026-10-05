#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi Django (BAB-01 Fondasi & Arsitektur)
Eksekusi mandiri (Python 3 standard library) dengan simulasi alur request-response:
WSGI/ASGI Worker -> Middleware Onion -> URL Dispatcher -> View -> ORM/Cache -> Response.
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional

# ANSI Color Codes untuk visualisasi terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"

@dataclass
class HttpRequest:
    path: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    user: Optional[str] = None
    session_id: Optional[str] = None
    is_secure: bool = True
    start_time: float = field(default_factory=time.time)

@dataclass
class HttpResponse:
    status_code: int
    content: str
    headers: Dict[str, str] = field(default_factory=dict)

# --- LAYER 1: CACHE & DATABASE SIMULATION ---

class MockRedisCache:
    def __init__(self):
        self.store: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str, ttl: int = 60):
        self.store[key] = value

class MockDatabaseRouter:
    """Simulasi Multi-DB Router Django (Read Replica vs Primary Write)"""
    def __init__(self):
        self.primary_pool = ["db-primary.prod.internal:5432"]
        self.replica_pool = [
            "db-replica-01.prod.internal:5432",
            "db-replica-02.prod.internal:5432"
        ]

    def db_for_read(self) -> str:
        return random.choice(self.replica_pool)

    def db_for_write(self) -> str:
        return self.primary_pool[0]

# --- LAYER 2: MIDDLEWARE ONION PIPELINE ---

class Middleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        raise NotImplementedError

class SecurityMiddleware(Middleware):
    def __call__(self, request: HttpRequest) -> HttpResponse:
        print(f"  {Colors.CYAN}[Middleware:Security]{Colors.RESET} Checking HTTPS & HSTS headers...")
        if not request.is_secure:
            return HttpResponse(301, "Redirecting to HTTPS", {"Location": f"https://prod{request.path}"})
        response = self.get_response(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

class AuthenticationMiddleware(Middleware):
    def __call__(self, request: HttpRequest) -> HttpResponse:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer valid-token"):
            request.user = "arch-engineer"
            print(f"  {Colors.GREEN}[Middleware:Auth]{Colors.RESET} Authenticated user: {Colors.BOLD}{request.user}{Colors.RESET}")
        else:
            request.user = "AnonymousUser"
            print(f"  {Colors.YELLOW}[Middleware:Auth]{Colors.RESET} User unauthenticated: AnonymousUser")
        return self.get_response(request)

class PerformanceMetricsMiddleware(Middleware):
    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Runtime-Latency"] = f"{elapsed_ms:.2f}ms"
        print(f"  {Colors.MAGENTA}[Middleware:Metrics]{Colors.RESET} Latency Pipeline: {elapsed_ms:.2f} ms")
        return response

# --- LAYER 3: CONTROLLERS & SERVICES ---

cache_instance = MockRedisCache()
db_router = MockDatabaseRouter()

def dashboard_view(request: HttpRequest) -> HttpResponse:
    cache_key = f"view_cache:{request.path}"
    cached = cache_instance.get(cache_key)
    
    if cached:
        print(f"    {Colors.BG_GREEN}{Colors.WHITE} CACHE HIT {Colors.RESET} Mengambil payload dari Redis cluster...")
        return HttpResponse(200, json.dumps({"source": "redis_cache", "data": cached}))

    print(f"    {Colors.BG_BLUE}{Colors.WHITE} CACHE MISS {Colors.RESET} Routing query ke Database...")
    db_node = db_router.db_for_read()
    print(f"    {Colors.DIM}-> Routing Django ORM SELECT query ke {Colors.BOLD}{db_node}{Colors.RESET}")
    time.sleep(0.05)  # Simulasi latency I/O database
    
    payload = {"status": "ok", "system_health": "99.98%", "active_workers": 8}
    cache_instance.set(cache_key, payload)
    return HttpResponse(200, json.dumps({"source": "postgresql_replica", "data": payload}))

def mutate_setting_view(request: HttpRequest) -> HttpResponse:
    if request.user == "AnonymousUser":
        return HttpResponse(403, json.dumps({"error": "Forbidden - Authentication Required"}))
    
    db_node = db_router.db_for_write()
    print(f"    {Colors.RED}-> Routing Django ORM WRITE transaction ke {Colors.BOLD}{db_node}{Colors.RESET}")
    time.sleep(0.08)  # Simulasi sync commit Primary
    return HttpResponse(200, json.dumps({"status": "updated", "cluster_mode": "strict-acid"}))

# --- LAYER 4: URL ROUTER ---

ROUTES = {
    "/api/v1/system/dashboard/": dashboard_view,
    "/api/v1/system/settings/": mutate_setting_view,
}

def resolve_and_dispatch(request: HttpRequest) -> HttpResponse:
    print(f"  {Colors.BLUE}[URL Resolver]{Colors.RESET} Mencocokkan regex path: {request.path}")
    view_func = ROUTES.get(request.path)
    if not view_func:
        return HttpResponse(404, json.dumps({"error": "Not Found", "path": request.path}))
    return view_func(request)

# --- LAYER 5: PIPELINE FACTORY ---

def build_production_pipeline() -> Callable[[HttpRequest], HttpResponse]:
    """Membangun rantai Middleware Onion Django"""
    handler = resolve_and_dispatch
    handler = PerformanceMetricsMiddleware(handler)
    handler = AuthenticationMiddleware(handler)
    handler = SecurityMiddleware(handler)
    return handler

# --- INTERACTIVE SIMULATION RUNNER ---

def run_simulation(path: str, method: str, auth_token: Optional[str] = None):
    pipeline = build_production_pipeline()
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req = HttpRequest(path=path, method=method, headers=headers)
    print(f"\n{Colors.BOLD}{Colors.WHITE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BG_MAGENTA}{Colors.WHITE} [WSGI/ASGI Worker: Gunicorn/Uvicorn] Incoming Request {Colors.RESET}")
    print(f"Method: {Colors.CYAN}{req.method}{Colors.RESET} | URI: {Colors.YELLOW}{req.path}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.WHITE}{'-'*70}{Colors.RESET}")
    
    resp = pipeline(req)
    
    print(f"{Colors.BOLD}{Colors.WHITE}{'-'*70}{Colors.RESET}")
    color_status = Colors.GREEN if resp.status_code == 200 else Colors.RED
    print(f"{Colors.BOLD}Response Status:{Colors.RESET} {color_status}{resp.status_code}{Colors.RESET}")
    print(f"{Colors.BOLD}Response Headers:{Colors.RESET} {json.dumps(resp.headers, indent=2)}")
    print(f"{Colors.BOLD}Response Body:{Colors.RESET} {resp.content}")
    print(f"{Colors.BOLD}{Colors.WHITE}{'='*70}{Colors.RESET}\n")

def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}======================================================================
  DJANGO ARCHITECTURE & PRODUCTION PIPELINE SIMULATOR (BAB-01)
  Interaktif: WSGI/ASGI -> Middleware Onion -> Routing -> ORM & Cache
======================================================================{Colors.RESET}
"""
    print(banner)

def main():
    print_banner()
    
    # Skenario 1: Cache Miss & Read Replica
    print(f"{Colors.YELLOW}[Skenario 1]{Colors.RESET} Request Dashboard (Awal / Cold Cache)")
    run_simulation("/api/v1/system/dashboard/", "GET")

    # Skenario 2: Cache Hit
    print(f"{Colors.YELLOW}[Skenario 2]{Colors.RESET} Request Dashboard Ulang (Warm Cache / Redis Hit)")
    run_simulation("/api/v1/system/dashboard/", "GET")

    # Skenario 3: Mutasi Data Tanpa Autentikasi (Ditolak)
    print(f"{Colors.YELLOW}[Skenario 3]{Colors.RESET} POST Mutasi Pengaturan tanpa Token")
    run_simulation("/api/v1/system/settings/", "POST")

    # Skenario 4: Mutasi Data dengan Autentikasi (Primary DB Write)
    print(f"{Colors.YELLOW}[Skenario 4]{Colors.RESET} POST Mutasi Pengaturan dengan Bearer Token")
    run_simulation("/api/v1/system/settings/", "POST", auth_token="valid-token")

    # Skenario 5: 404 Route Not Found
    print(f"{Colors.YELLOW}[Skenario 5]{Colors.RESET} Request Endpoint Tidak Ditemukan")
    run_simulation("/api/v1/unknown-service/", "GET")

    print(f"{Colors.GREEN}{Colors.BOLD}[SIMULASI SELESAI]{Colors.RESET} Arsitektur Django berhasil diverifikasi secara mandiri.\n")

if __name__ == "__main__":
    main()

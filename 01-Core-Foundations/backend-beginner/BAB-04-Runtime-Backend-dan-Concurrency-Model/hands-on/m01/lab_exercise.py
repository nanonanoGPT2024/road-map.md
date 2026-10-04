#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Backend Beginner - Materi Lanjutan (BAB-04)
Topik: Arsitektur Backend, Pipeline Middleware, Routing, dan Request-Response Lifecycle
Deskripsi: Simulasi engine backend mandiri dengan dukungan middleware pipeline,
           routing RESTful, validasi payload, in-memory repository, serta visualisasi
           ANSI color terminal.
"""

import json
import time
from typing import Callable, Dict, List, Optional, Tuple

# ==============================================================================
# 1. Terminal Styling & ANSI Colors
# ==============================================================================
class Colors:
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
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def print_header(title: str):
    print(f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} === {title.upper()} === {Colors.RESET}")

def print_info(label: str, message: str):
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {Colors.BOLD}{label}:{Colors.RESET} {message}")

def print_success(message: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {message}")

def print_warn(message: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {message}")

def print_error(message: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}")


# ==============================================================================
# 2. HTTP Primitives (Request, Response, Status Codes)
# ==============================================================================
class HttpRequest:
    def __init__(self, method: str, path: str, headers: Optional[Dict[str, str]] = None, body: Optional[dict] = None):
        self.method = method.upper()
        self.path = path
        self.headers = headers or {}
        self.body = body or {}
        self.context: Dict[str, any] = {}

class HttpResponse:
    STATUS_TEXTS = {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        429: "Too Many Requests",
        500: "Internal Server Error",
    }

    def __init__(self, status_code: int = 200, body: Optional[dict] = None, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self.body = body or {}
        self.headers = headers or {"Content-Type": "application/json"}

    @property
    def status_text(self) -> str:
        return self.STATUS_TEXTS.get(self.status_code, "Unknown")

    def render(self):
        color = Colors.GREEN if self.status_code < 400 else Colors.RED
        print(f"{color}{Colors.BOLD}HTTP/1.1 {self.status_code} {self.status_text}{Colors.RESET}")
        for k, v in self.headers.items():
            print(f"{Colors.DIM}{k}: {v}{Colors.RESET}")
        print(f"\n{Colors.WHITE}{json.dumps(self.body, indent=2)}{Colors.RESET}")


# ==============================================================================
# 3. Middleware Pipeline
# ==============================================================================
HandlerFunc = Callable[[HttpRequest], HttpResponse]
MiddlewareFunc = Callable[[HttpRequest, HandlerFunc], HttpResponse]

class LoggingMiddleware:
    def __call__(self, req: HttpRequest, next_handler: HandlerFunc) -> HttpResponse:
        start_time = time.time()
        print(f"  {Colors.MAGENTA}↳ [Middleware: Logger]{Colors.RESET} Incoming {req.method} {req.path}")
        response = next_handler(req)
        latency_ms = (time.time() - start_time) * 1000
        print(f"  {Colors.MAGENTA}↳ [Middleware: Logger]{Colors.RESET} Outgoing {response.status_code} ({latency_ms:.2f}ms)")
        return response

class AuthMiddleware:
    def __call__(self, req: HttpRequest, next_handler: HandlerFunc) -> HttpResponse:
        protected_routes = ["/api/v1/orders", "/api/v1/admin"]
        if any(req.path.startswith(route) for route in protected_routes):
            print(f"  {Colors.BLUE}↳ [Middleware: Auth]{Colors.RESET} Memeriksa token otorisasi...")
            auth_token = req.headers.get("Authorization")
            if not auth_token or not auth_token.startswith("Bearer valid-token"):
                print(f"  {Colors.RED}↳ [Middleware: Auth] Autentikasi ditolak: Token tidak valid!{Colors.RESET}")
                return HttpResponse(401, {"error": "Unauthorized", "detail": "Valid Bearer token is required."})
            req.context["user"] = {"id": "usr_99", "role": "developer"}
            print(f"  {Colors.GREEN}↳ [Middleware: Auth] Terverifikasi sebagai user: usr_99{Colors.RESET}")
        return next_handler(req)

class RateLimitMiddleware:
    def __init__(self, limit: int = 5):
        self.limit = limit
        self.counter: Dict[str, int] = {}

    def __call__(self, req: HttpRequest, next_handler: HandlerFunc) -> HttpResponse:
        client_ip = req.headers.get("X-Forwarded-For", "127.0.0.1")
        self.counter[client_ip] = self.counter.get(client_ip, 0) + 1
        current_hits = self.counter[client_ip]

        print(f"  {Colors.YELLOW}↳ [Middleware: RateLimit]{Colors.RESET} IP: {client_ip} (Hits: {current_hits}/{self.limit})")
        if current_hits > self.limit:
            return HttpResponse(429, {"error": "Too Many Requests", "detail": "Rate limit exceeded. Try again later."})
        return next_handler(req)


# ==============================================================================
# 4. In-Memory Data Store & Controller Logic
# ==============================================================================
class Database:
    def __init__(self):
        self.products = [
            {"id": 1, "name": "Laptop ThinkPad", "category": "electronics", "price": 14500000},
            {"id": 2, "name": "Mechanical Keyboard", "category": "accessories", "price": 1250000},
            {"id": 3, "name": "Wireless Mouse", "category": "accessories", "price": 450000},
        ]
        self.orders = []

db = Database()

def get_products(req: HttpRequest) -> HttpResponse:
    return HttpResponse(200, {"data": db.products, "total": len(db.products)})

def create_product(req: HttpRequest) -> HttpResponse:
    data = req.body
    if not data.get("name") or not data.get("price"):
        return HttpResponse(400, {"error": "Validation Error", "fields": ["name", "price wajib diisi"]})
    
    new_product = {
        "id": len(db.products) + 1,
        "name": data["name"],
        "category": data.get("category", "general"),
        "price": data["price"]
    }
    db.products.append(new_product)
    return HttpResponse(201, {"message": "Produk berhasil ditambahkan", "product": new_product})

def create_order(req: HttpRequest) -> HttpResponse:
    user = req.context.get("user")
    item_id = req.body.get("product_id")
    qty = req.body.get("qty", 1)

    product = next((p for p in db.products if p["id"] == item_id), None)
    if not product:
        return HttpResponse(404, {"error": "Not Found", "detail": f"Product ID {item_id} tidak ditemukan"})

    order = {
        "order_id": f"ORD-{len(db.orders) + 1001}",
        "user_id": user["id"],
        "product": product["name"],
        "qty": qty,
        "total_price": product["price"] * qty,
        "status": "PAID"
    }
    db.orders.append(order)
    return HttpResponse(201, {"message": "Order berhasil dibuat", "order": order})


# ==============================================================================
# 5. Core Engine: Router & Application Dispatcher
# ==============================================================================
class ApplicationEngine:
    def __init__(self):
        self.routes: Dict[Tuple[str, str], HandlerFunc] = {}
        self.middlewares: List[MiddlewareFunc] = []

    def use(self, middleware: MiddlewareFunc):
        self.middlewares.append(middleware)

    def route(self, method: str, path: str, handler: HandlerFunc):
        self.routes[(method.upper(), path)] = handler

    def dispatch(self, req: HttpRequest) -> HttpResponse:
        def core_handler(r: HttpRequest) -> HttpResponse:
            key = (r.method, r.path)
            if key in self.routes:
                return self.routes[key](r)
            return HttpResponse(404, {"error": "Not Found", "detail": f"Route {r.method} {r.path} tidak terdaftar"})

        # Membangun rantai eksekusi middleware (Onion architecture)
        chain = core_handler
        for mw in reversed(self.middlewares):
            def make_layer(m=mw, nxt=chain):
                return lambda r: m(r, nxt)
            chain = make_layer()

        return chain(req)


# ==============================================================================
# 6. Setup & Interactive CLI Simulator
# ==============================================================================
def create_app() -> ApplicationEngine:
    app = ApplicationEngine()
    app.use(LoggingMiddleware())
    app.use(RateLimitMiddleware(limit=6))
    app.use(AuthMiddleware())

    app.route("GET", "/api/v1/products", get_products)
    app.route("POST", "/api/v1/products", create_product)
    app.route("POST", "/api/v1/orders", create_order)
    return app

def run_automated_demo(app: ApplicationEngine):
    print_header("Simulasi Lifecycle Request Otomatis")

    test_scenarios = [
        ("1. GET Publik /api/v1/products", HttpRequest("GET", "/api/v1/products")),
        ("2. POST Tambah Produk Baru", HttpRequest("POST", "/api/v1/products", body={"name": "Ultrawide Monitor", "price": 4200000, "category": "electronics"})),
        ("3. POST Order Tanpa Token (Harus Gagal 401)", HttpRequest("POST", "/api/v1/orders", body={"product_id": 1, "qty": 2})),
        ("4. POST Order Dengan Token Bearer (Harus Berhasil 201)", HttpRequest("POST", "/api/v1/orders", headers={"Authorization": "Bearer valid-token-xyz"}, body={"product_id": 1, "qty": 1})),
        ("5. GET Endpoint Tidak Ada (Harus 404)", HttpRequest("GET", "/api/v1/unknown-endpoint")),
    ]

    for title, req in test_scenarios:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}▶ Skenario: {title}{Colors.RESET}")
        print(f"{Colors.DIM}Client Sending: {req.method} {req.path}{Colors.RESET}")
        res = app.dispatch(req)
        res.render()
        time.sleep(0.3)

def interactive_menu(app: ApplicationEngine):
    while True:
        print_header("Backend Engine Playground (BAB-04)")
        print(f"{Colors.BOLD}1.{Colors.RESET} Jalankan Automated Test Scenarios")
        print(f"{Colors.BOLD}2.{Colors.RESET} Kirim Request Kustom Manual")
        print(f"{Colors.BOLD}3.{Colors.RESET} Tampilkan Isi Database In-Memory")
        print(f"{Colors.BOLD}4.{Colors.RESET} Simulasi Rate Limiting Trigger")
        print(f"{Colors.BOLD}5.{Colors.RESET} Keluar")
        
        try:
            choice = input(f"\n{Colors.GREEN}Pilih opsi [1-5]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            run_automated_demo(app)
        elif choice == "2":
            method = input("Method (GET/POST): ").strip().upper() or "GET"
            path = input("Path (misal /api/v1/products): ").strip() or "/api/v1/products"
            token = input("Authorization Bearer (kosongkan jika tanpa token): ").strip()
            
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            body = None
            if method == "POST":
                raw_json = input("JSON Body (e.g. {\"name\": \"Gadget\", \"price\": 1000}): ").strip()
                if raw_json:
                    try:
                        body = json.loads(raw_json)
                    except json.JSONDecodeError:
                        print_error("Format JSON tidak valid!")
                        continue
            
            req = HttpRequest(method=method, path=path, headers=headers, body=body)
            print(f"\n{Colors.CYAN}Mengirim Request...{Colors.RESET}")
            res = app.dispatch(req)
            res.render()

        elif choice == "3":
            print_info("Daftar Produk", json.dumps(db.products, indent=2))
            print_info("Daftar Order", json.dumps(db.orders, indent=2))
        elif choice == "4":
            print_warn("Memicu 7 request berturut-turut untuk menguji Rate Limit (Max 6)...")
            for i in range(1, 8):
                print(f"\n{Colors.BOLD}Hit ke-{i}:{Colors.RESET}")
                res = app.dispatch(HttpRequest("GET", "/api/v1/products"))
                if res.status_code == 429:
                    print_error(f"Rate limit terpicu pada hit ke-{i}!")
                else:
                    print_success(f"Status: {res.status_code}")
        elif choice == "5":
            print(f"{Colors.CYAN}Terima kasih telah mempelajari fondasi backend BAB-04!{Colors.RESET}")
            break
        else:
            print_warn("Opsi tidak valid, silakan coba lagi.")


if __name__ == "__main__":
    application = create_app()
    print_success("Backend Engine berhasil diinisialisasi.")
    # Jika dijalankan interaktif, tampilkan menu
    import sys
    if "--demo" in sys.argv or not sys.stdin.isatty():
        run_automated_demo(application)
    else:
        interactive_menu(application)

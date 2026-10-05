#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Fondasi dan Arsitektur Django
Simulasi Teknis Mandiri Konsep Inti Django:
1. Request-Response Lifecycle & Onion Middleware Architecture
2. URL Dispatcher (Regex/Path Resolver & Kwargs Extraction)
3. MTV (Model - Template - View) Design Pattern
4. Django App Registry & Settings Bootstrapping

Dapat dijalankan secara interaktif (CLI menu) maupun otomatis (batch mode).
"""

from __future__ import annotations
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any

# ==============================================================================
# ANSI Color Formatting & Terminal Helpers
# ==============================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def print_header(title: str):
    width = 72
    print(f"\n{ANSI.CYAN}{'=' * width}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.WHITE} {title.center(width - 2)} {ANSI.RESET}")
    print(f"{ANSI.CYAN}{'=' * width}{ANSI.RESET}")

def print_step(step_num: int, label: str, detail: str = ""):
    print(f"  {ANSI.YELLOW}[Step {step_num:02d}]{ANSI.RESET} {ANSI.BOLD}{label:<28}{ANSI.RESET} {ANSI.DIM}{detail}{ANSI.RESET}")

def print_success(msg: str):
    print(f"  {ANSI.GREEN}✓ {msg}{ANSI.RESET}")

def print_info(label: str, value: str):
    print(f"    {ANSI.BLUE}▸ {label:<16}:{ANSI.RESET} {value}")

def print_box(content: str, color: str = ANSI.MAGENTA):
    lines = content.strip().split("\n")
    max_len = max(len(re.sub(r'\x1b\[[0-9;]*m', '', line)) for line in lines)
    border = "+" + "-" * (max_len + 2) + "+"
    print(f"{color}{border}{ANSI.RESET}")
    for line in lines:
        raw_len = len(re.sub(r'\x1b\[[0-9;]*m', '', line))
        padding = " " * (max_len - raw_len)
        print(f"{color}|{ANSI.RESET} {line}{padding} {color}|{ANSI.RESET}")
    print(f"{color}{border}{ANSI.RESET}")


# ==============================================================================
# 1. HTTP Core Abstraction: HttpRequest & HttpResponse
# ==============================================================================
@dataclass
class HttpRequest:
    path: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    GET: Dict[str, str] = field(default_factory=dict)
    POST: Dict[str, str] = field(default_factory=dict)
    resolver_match: Optional[Dict[str, Any]] = None
    user: Optional[str] = None
    META: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HttpResponse:
    content: str
    status_code: int = 200
    content_type: str = "text/html; charset=utf-8"
    headers: Dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        return (
            f"HTTP/1.1 {self.status_code}\n"
            f"Content-Type: {self.content_type}\n"
            f"Content-Length: {len(self.content.encode('utf-8'))}\n\n"
            f"{self.content}"
        )


# ==============================================================================
# 2. MTV Components: Model, Template, View
# ==============================================================================
class Model:
    """Simulasi Mock Django ORM Model"""
    _storage: Dict[int, Dict[str, Any]] = {}
    _next_id: int = 1

    def __init__(self, **kwargs):
        self.fields = kwargs
        self.id = kwargs.get("id")

    @classmethod
    def create(cls, **kwargs) -> Model:
        record_id = cls._next_id
        cls._next_id += 1
        data = {"id": record_id, **kwargs}
        cls._storage[record_id] = data
        return cls(**data)

    @classmethod
    def get(cls, pk: int) -> Optional[Model]:
        data = cls._storage.get(pk)
        return cls(**data) if data else None

    @classmethod
    def all(cls) -> List[Model]:
        return [cls(**data) for data in cls._storage.values()]

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id} fields={self.fields}>"


class Article(Model):
    pass


class TemplateEngine:
    """Simulasi Template Engine Django (Variable Interpolation & Filter sederhana)"""
    @staticmethod
    def render(template_str: str, context: Dict[str, Any]) -> str:
        output = template_str
        # Replace {{ variable }}
        for key, val in context.items():
            pattern = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")
            output = pattern.sub(str(val), output)
        
        # Simple loop simulation: {% for item in items %} ... {% endfor %}
        loop_pattern = re.compile(r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}", re.DOTALL)
        while True:
            match = loop_pattern.search(output)
            if not match:
                break
            var_name, list_name, inner_tpl = match.groups()
            collection = context.get(list_name, [])
            rendered_loop = ""
            for item in collection:
                item_rendered = inner_tpl
                if isinstance(item, dict):
                    for ik, iv in item.items():
                        item_rendered = re.sub(r"\{\{\s*" + re.escape(var_name) + r"\." + re.escape(ik) + r"\s*\}\}", str(iv), item_rendered)
                elif hasattr(item, "fields"):
                    for ik, iv in item.fields.items():
                        item_rendered = re.sub(r"\{\{\s*" + re.escape(var_name) + r"\." + re.escape(ik) + r"\s*\}\}", str(iv), item_rendered)
                rendered_loop += item_rendered
            output = output[:match.start()] + rendered_loop + output[match.end():]

        return output.strip()


# Views
def article_list_view(request: HttpRequest) -> HttpResponse:
    articles = Article.all()
    template = """
<div class="articles-container">
  <h1>Daftar Artikel (MTV: View -> Model -> Template)</h1>
  <p>User Aktif: {{ user }}</p>
  <ul>
    {% for art in articles %}
    <li><strong>ID {{ art.id }}:</strong> {{ art.title }} (Penulis: {{ art.author }})</li>
    {% endfor %}
  </ul>
</div>
"""
    rendered = TemplateEngine.render(template, {
        "user": request.user or "AnonymousUser",
        "articles": articles
    })
    return HttpResponse(rendered, status_code=200)


def article_detail_view(request: HttpRequest, article_id: int) -> HttpResponse:
    article = Article.get(int(article_id))
    if not article:
        return HttpResponse("<h1>404 Not Found</h1><p>Artikel tidak ditemukan.</p>", status_code=404)
    
    template = """
<article>
  <h1>{{ title }}</h1>
  <p class="meta">Ditulis oleh: {{ author }} | ID: {{ id }}</p>
  <div class="content">{{ content }}</div>
</article>
"""
    rendered = TemplateEngine.render(template, {
        "title": article.fields.get("title", ""),
        "author": article.fields.get("author", ""),
        "id": article.id,
        "content": article.fields.get("content", "")
    })
    return HttpResponse(rendered, status_code=200)


# ==============================================================================
# 3. URL Dispatcher (URLconf & Resolver)
# ==============================================================================
@dataclass
class URLPattern:
    pattern: str
    view_func: Callable
    name: str

class URLResolver:
    def __init__(self, urlpatterns: List[URLPattern]):
        self.urlpatterns = urlpatterns

    def resolve(self, path: str) -> Optional[Tuple[Callable, Dict[str, Any], str]]:
        for entry in self.urlpatterns:
            # Mengubah django path param syntax seperti <int:article_id> menjadi regex
            regex = entry.pattern
            regex = re.sub(r"<int:(\w+)>", r"(?P<\1>\\d+)", regex)
            regex = re.sub(r"<str:(\w+)>", r"(?P<\1>[^/]+)", regex)
            regex = f"^{regex}$"

            match = re.match(regex, path)
            if match:
                kwargs = match.groupdict()
                # Typecast ints
                for k, v in kwargs.items():
                    if v.isdigit():
                        kwargs[k] = int(v)
                return entry.view_func, kwargs, entry.name
        return None


# ==============================================================================
# 4. Middleware Pipeline (Onion Architecture)
# ==============================================================================
class BaseMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        raise NotImplementedError


class SecurityMiddleware(BaseMiddleware):
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Pre-processing (Inward)
        print_step(1, "SecurityMiddleware (IN)", "Memeriksa headers keamanan & host")
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Post-processing (Outward)
        duration = (time.time() - start_time) * 1000
        print_step(6, "SecurityMiddleware (OUT)", f"Injeksi header X-Content-Type-Options (+{duration:.2f}ms)")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


class AuthenticationMiddleware(BaseMiddleware):
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Pre-processing (Inward)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            request.user = f"StaffUser_{token[:5]}"
        else:
            request.user = "AnonymousUser"
        print_step(2, "AuthenticationMiddleware (IN)", f"Resolving user: {ANSI.BOLD}{request.user}{ANSI.RESET}")

        response = self.get_response(request)

        # Post-processing (Outward)
        print_step(5, "AuthenticationMiddleware (OUT)", "Menyelesaikan context session user")
        return response


class CommonMiddleware(BaseMiddleware):
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Pre-processing (Inward)
        print_step(3, "CommonMiddleware (IN)", f"Normalisasi URI & trailing slash [{request.path}]")
        
        response = self.get_response(request)

        # Post-processing (Outward)
        print_step(4, "CommonMiddleware (OUT)", "Mengatur Content-Length dan caching headers")
        return response


# ==============================================================================
# 5. Core Handler: WSGIHandler / Server Engine
# ==============================================================================
class WSGIHandlerSimulation:
    def __init__(self, resolver: URLResolver, middleware_classes: List[type]):
        self.resolver = resolver
        self.middleware_classes = middleware_classes
        self._handler = self._build_middleware_stack()

    def _build_middleware_stack(self) -> Callable[[HttpRequest], HttpResponse]:
        handler = self._get_response_view_executor
        # Menyusun onion stack dari dalam ke luar (reverse)
        for middleware_cls in reversed(self.middleware_classes):
            handler = middleware_cls(handler)
        return handler

    def _get_response_view_executor(self, request: HttpRequest) -> HttpResponse:
        print_step(3, "URL Dispatcher", f"Resolving URL '{request.path}'")
        resolved = self.resolver.resolve(request.path)
        if not resolved:
            return HttpResponse("<h1>404 Page Not Found</h1>", status_code=404)
        
        view_func, kwargs, route_name = resolved
        request.resolver_match = {"name": route_name, "kwargs": kwargs}
        print_info("Match Found", f"Route='{route_name}', View='{view_func.__name__}', Kwargs={kwargs}")
        
        print_step(4, "View Execution", f"Memanggil {view_func.__name__}() [Pola MTV View]")
        return view_func(request, **kwargs)

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        return self._handler(request)


# ==============================================================================
# 6. Django App Registry & Settings Simulation
# ==============================================================================
class AppConfig:
    def __init__(self, name: str, label: str):
        self.name = name
        self.label = label
        self.models: List[str] = []

    def ready(self):
        pass


class CoreAppConfig(AppConfig):
    def ready(self):
        self.models = ["Article", "Author", "Comment"]


class AppRegistry:
    def __init__(self):
        self.apps: Dict[str, AppConfig] = {}
        self.ready = False

    def populate(self, installed_apps: List[str]):
        print_header("DJANGO APP REGISTRY BOOTSTRAPPING (apps.populate())")
        print(f"  {ANSI.DIM}Mensimulasikan fase django.setup() saat server booting:{ANSI.RESET}")
        for app_path in installed_apps:
            label = app_path.split(".")[-1]
            config = CoreAppConfig(name=app_path, label=label)
            config.ready()
            self.apps[label] = config
            print(f"  {ANSI.GREEN}✔ App Loaded:{ANSI.RESET} {ANSI.BOLD}{app_path:<25}{ANSI.RESET} [Models: {', '.join(config.models)}]")
        self.ready = True
        print_success(f"AppRegistry siap dengan {len(self.apps)} installed applications.\n")


# ==============================================================================
# Interactive CLI & Verification Runner
# ==============================================================================
def seed_database():
    Article._storage.clear()
    Article._next_id = 1
    Article.create(
        title="Pengenalan Filosofi Django: Batteries-Included",
        author="Guido & Adrian",
        content="Django dirancang untuk kecepatan pengembangan dengan arsitektur yang modular, aman, dan kohesif."
    )
    Article.create(
        title="Mendalami Arsitektur MTV vs MVC",
        author="Django Core Team",
        content="Dalam Django, Model adalah data layer, Template adalah presentation layer, dan View bertindak sebagai controller bisnis."
    )
    Article.create(
        title="Memahami Siklus Onion Middleware di WSGI/ASGI",
        author="Web Architect",
        content="Middleware memproses request masuk secara serial, lalu memproses response keluar secara terbalik (LIFO)."
    )

def setup_simulation() -> Tuple[WSGIHandlerSimulation, AppRegistry]:
    seed_database()
    
    # URL Patterns
    urlpatterns = [
        URLPattern(r"/articles/", article_list_view, "article_list"),
        URLPattern(r"/articles/<int:article_id>/", article_detail_view, "article_detail"),
    ]
    resolver = URLResolver(urlpatterns)

    # Middleware Chain
    middlewares = [
        SecurityMiddleware,
        AuthenticationMiddleware,
        CommonMiddleware,
    ]
    handler = WSGIHandlerSimulation(resolver, middlewares)

    registry = AppRegistry()
    registry.populate([
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "myproject.blog"
    ])
    return handler, registry


def demo_request_cycle(handler: WSGIHandlerSimulation):
    print_header("SIMULASI 1: FULL REQUEST-RESPONSE LIFECYCLE (ONION PIPELINE)")
    
    req = HttpRequest(
        path="/articles/1/",
        method="GET",
        headers={"Authorization": "Bearer tok_demo_987654"}
    )
    
    print(f"{ANSI.YELLOW}Request Datang:{ANSI.RESET} GET {req.path} | Auth: {req.headers.get('Authorization')}\n")
    print(f"{ANSI.BOLD}Alur Eksekusi (Onion Middleware & View Pipeline):{ANSI.RESET}")
    
    response = handler.handle_request(req)
    
    print("\n" + f"{ANSI.GREEN}Hasil HttpResponse Diterima:{ANSI.RESET}")
    print_info("Status Code", f"{response.status_code} OK")
    print_info("Content-Type", response.content_type)
    print_info("Injected Headers", str(response.headers))
    
    print("\n" + f"{ANSI.CYAN}Output HTML Ter-render (Template Engine):{ANSI.RESET}")
    print_box(response.content, ANSI.GREEN)


def demo_mtv_architecture(handler: WSGIHandlerSimulation):
    print_header("SIMULASI 2: PENJELASAN PRAKTEK MTV (MODEL-TEMPLATE-VIEW)")
    
    diagram = """
+-----------------------------------------------------------------+
|                       DJANGO MTV PATTERN                        |
+-----------------------------------------------------------------+
| [Request] ---> [URLConf] ---> [VIEW (Logika Bisnis)]            |
|                                     |        ^                  |
|                                     v        |                  |
|                        [MODEL (ORM / Data)]  |                  |
|                                     |        |                  |
|                                     +--------+                  |
|                                     |                           |
|                                     v                           |
|                           [TEMPLATE (HTML Engine)]              |
|                                     |                           |
|                                     v                           |
| [Response (HTML / JSON)] <----------+                           |
+-----------------------------------------------------------------+
"""
    print(f"{ANSI.MAGENTA}{diagram}{ANSI.RESET}")
    
    print(f"{ANSI.BOLD}Simulasi: Mengakses Daftar Seluruh Artikel (/articles/){ANSI.RESET}\n")
    req = HttpRequest(path="/articles/", method="GET")
    resp = handler.handle_request(req)
    
    print(f"\n{ANSI.GREEN}Hasil Render Halaman List Artikel:{ANSI.RESET}")
    print_box(resp.content, ANSI.CYAN)


def demo_404_flow(handler: WSGIHandlerSimulation):
    print_header("SIMULASI 3: PENANGANAN ROUTE 404 & RECORD TIDAK DITEMUKAN")
    
    print(f"{ANSI.YELLOW}Kasus A: URL Tidak Ada dalam URLConf (/products/xyz/){ANSI.RESET}")
    req_not_found = HttpRequest(path="/products/xyz/", method="GET")
    resp_404 = handler.handle_request(req_not_found)
    print_info("Status Code", str(resp_404.status_code))
    print_info("Response Body", resp_404.content)
    
    print(f"\n{ANSI.YELLOW}Kasus B: URL Valid Namun Record Tidak Ada (/articles/999/){ANSI.RESET}")
    req_item_404 = HttpRequest(path="/articles/999/", method="GET")
    resp_item_404 = handler.handle_request(req_item_404)
    print_info("Status Code", str(resp_item_404.status_code))
    print_info("Response Body", resp_item_404.content)


def run_all_simulations():
    handler, registry = setup_simulation()
    demo_request_cycle(handler)
    demo_mtv_architecture(handler)
    demo_404_flow(handler)
    print_header("SEMUA SIMULASI SELESAI DENGAN SUKSES")
    print_success("Konsep fondasi Django (Arsitektur WSGI, Onion Middleware, URLconf, MTV, AppRegistry) tervalidasi.\n")


def interactive_menu():
    handler, registry = setup_simulation()
    
    while True:
        print_header("HANDS-ON LAB: FONDASI & ARSITEKTUR DJANGO (CLI INTERAKTIF)")
        print("  1. Jalankan Siklus Penuh Request-Response & Onion Middleware (GET /articles/1/)")
        print("  2. Eksplorasi Arsitektur MTV (Model-Template-View) (GET /articles/)")
        print("  3. Simulasi Kasus Error (Route 404 & Object Not Found)")
        print("  4. Tampilkan Status App Registry & Models yang Terdaftar")
        print("  5. Jalankan Seluruh Demonstrasi (Batch Mode)")
        print("  0. Keluar")
        print("-" * 72)
        
        try:
            choice = input(f"{ANSI.BOLD}Pilih menu [0-5]: {ANSI.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            demo_request_cycle(handler)
        elif choice == "2":
            demo_mtv_architecture(handler)
        elif choice == "3":
            demo_404_flow(handler)
        elif choice == "4":
            print_header("STATUS DJANGO APP REGISTRY")
            for label, app in registry.apps.items():
                print(f"  • {ANSI.BOLD}{label:<15}{ANSI.RESET} : {app.name} (Models: {app.models})")
            print()
        elif choice == "5":
            demo_request_cycle(handler)
            demo_mtv_architecture(handler)
            demo_404_flow(handler)
        elif choice == "0":
            print("\nTerima kasih telah menjelajahi fondasi Django.")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid! Masukkan angka 0-5.{ANSI.RESET}")

        if sys.stdin.isatty():
            try:
                input(f"\n{ANSI.DIM}Tekan [Enter] untuk kembali ke menu utama...{ANSI.RESET}")
            except (EOFError, KeyboardInterrupt):
                break


if __name__ == "__main__":
    # Jika dijalankan dengan argument --all atau non-TTY (misal piped), jalankan batch mode
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_all_simulations()
    elif not sys.stdin.isatty():
        run_all_simulations()
    else:
        interactive_menu()

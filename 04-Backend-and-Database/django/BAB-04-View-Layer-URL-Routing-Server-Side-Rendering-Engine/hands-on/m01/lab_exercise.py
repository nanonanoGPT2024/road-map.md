#!/usr/bin/env python3
"""
Lab Exercise M01: Django Core Architecture Simulation
BAB-04: View Layer, URL Routing & Server-Side Rendering (SSR) Engine

Simulasi mandiri murni (Standard Library Python 3) yang mereplikasi mekanisme internal:
1. URL Dispatcher & Path Converters (Regex-based dynamic routing)
2. View Layer: Function-Based Views (FBV) & Class-Based Views (CBV `as_view()`)
3. WSGI/ASGI HttpRequest & HttpResponse Cycle
4. Template Engine SSR: Variable Interpolation, Filter Pipeline, & Block Inheritance
5. Middleware Pipeline (Request & Response processing)
"""

import re
import sys
import time
from typing import Callable, Dict, Any, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palettes for Terminal Formatting
# ==============================================================================
class Color:
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
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"

def print_header(title: str):
    line = "=" * 70
    print(f"\n{Color.CYAN}{line}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} {title.upper()} {Color.RESET}")
    print(f"{Color.CYAN}{line}{Color.RESET}")

def print_step(step: str, desc: str):
    print(f"\n{Color.YELLOW}[STEP] {Color.BOLD}{step}{Color.RESET}: {desc}")

# ==============================================================================
# 1. HTTP Request & Response Objects (Django Mock)
# ==============================================================================
class HttpRequest:
    def __init__(self, path: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, str]] = None):
        self.path = path
        self.method = method.upper()
        self.headers = headers or {"User-Agent": "DjangoLabSimulator/1.0", "Accept": "text/html"}
        self.GET = params or {}
        self.POST: Dict[str, Any] = {}
        self.user = "AnonymousUser"
        self.session: Dict[str, Any] = {}

class HttpResponse:
    def __init__(self, content: str = "", status: int = 200, content_type: str = "text/html; charset=utf-8"):
        self.content = content
        self.status = status
        self.content_type = content_type
        self.headers = {"Content-Type": content_type}

    def __repr__(self):
        return f"<HttpResponse status={self.status} content_type='{self.content_type}'>"

# ==============================================================================
# 2. URL Routing & Path Converters
# ==============================================================================
CONVERTER_REGEX = {
    "int": r"(?P<{}>\d+)",
    "str": r"(?P<{}>[^/]+)",
    "slug": r"(?P<{}>[-a-zA-Z0-9_]+)",
}

class URLPattern:
    def __init__(self, route: str, view: Callable, name: Optional[str] = None):
        self.route = route
        self.view = view
        self.name = name
        self.regex, self.converters = self._compile(route)

    def _compile(self, route: str) -> Tuple[re.Pattern, Dict[str, str]]:
        # Mengubah route ala Django path('<int:post_id>/detail/') menjadi Regex
        pattern = r"^"
        idx = 0
        converters = {}
        tokens = re.finditer(r"<(?P<conv>int|str|slug):(?P<var>[a-zA-Z_]\w*)>", route)
        for match in tokens:
            pattern += re.escape(route[idx:match.start()])
            conv_type = match.group("conv")
            var_name = match.group("var")
            pattern += CONVERTER_REGEX[conv_type].format(var_name)
            converters[var_name] = conv_type
            idx = match.end()
        pattern += re.escape(route[idx:]) + r"$"
        return re.compile(pattern), converters

    def match(self, path: str) -> Optional[Dict[str, Any]]:
        match = self.regex.match(path)
        if not match:
            return None
        kwargs = match.groupdict()
        # Casting tipe data sesuai converter
        for var, conv in self.converters.items():
            if conv == "int":
                kwargs[var] = int(kwargs[var])
        return kwargs

class URLResolver:
    def __init__(self):
        self.patterns: List[URLPattern] = []

    def register(self, route: str, view: Callable, name: Optional[str] = None):
        self.patterns.append(URLPattern(route, view, name))

    def resolve(self, path: str) -> Tuple[Optional[Callable], Dict[str, Any]]:
        for pattern in self.patterns:
            kwargs = pattern.match(path)
            if kwargs is not None:
                return pattern.view, kwargs
        return None, {}

# ==============================================================================
# 3. Server-Side Rendering (SSR) Template Engine
# ==============================================================================
class Template:
    """
    Mini Django Template Engine:
    - Variable interpolation: {{ user.name }}, {{ count }}
    - Pipeline filters: {{ title|upper }}, {{ description|truncate:20 }}
    - Block inheritance: {% extends "base.html" %}, {% block body %}...{% endblock %}
    """
    FILTERS = {
        "upper": lambda val, arg=None: str(val).upper(),
        "lower": lambda val, arg=None: str(val).lower(),
        "title": lambda val, arg=None: str(val).title(),
        "truncate": lambda val, arg=None: str(val)[:int(arg)] + "..." if len(str(val)) > int(arg) else str(val),
        "default": lambda val, arg=None: val if val else arg,
    }

    def __init__(self, raw_html: str, template_name: str = "inline"):
        self.raw_html = raw_html
        self.name = template_name

    def render(self, context: Dict[str, Any]) -> str:
        output = self.raw_html

        # Evaluasi {% for item in items %} ... {% endfor %}
        for_loop_regex = re.compile(r"{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}(.*?){%\s*endfor\s*%}", re.DOTALL)
        def replace_for(match):
            item_var = match.group(1)
            list_var = match.group(2)
            template_chunk = match.group(3)
            items = context.get(list_var, [])
            rendered_chunks = []
            for it in items:
                sub_ctx = dict(context)
                sub_ctx[item_var] = it
                sub_tmpl = Template(template_chunk)
                rendered_chunks.append(sub_tmpl.render(sub_ctx))
            return "".join(rendered_chunks)

        output = for_loop_regex.sub(replace_for, output)

        # Evaluasi Variables & Filters: {{ var|filter:arg }}
        var_regex = re.compile(r"{{\s*([a-zA-Z0-9_\.]+)(\|([a-zA-Z0-9_]+)(?::([a-zA-Z0-9_]+))?)?\s*}}")
        def replace_var(match):
            var_path = match.group(1)
            filter_name = match.group(3)
            filter_arg = match.group(4)

            # Resolve dot notation (misal: user.profile.name)
            parts = var_path.split(".")
            val = context
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p, "")
                else:
                    val = getattr(val, p, "")

            if filter_name and filter_name in self.FILTERS:
                val = self.FILTERS[filter_name](val, filter_arg)
            return str(val)

        output = var_regex.sub(replace_var, output)
        return output

# ==============================================================================
# 4. View Layer: FBV, CBV, & View Dispatcher
# ==============================================================================
def render_to_response(template_str: str, context: Dict[str, Any], status: int = 200) -> HttpResponse:
    tmpl = Template(template_str)
    rendered_body = tmpl.render(context)
    return HttpResponse(content=rendered_body, status=status)

# Function-Based View (FBV)
def home_view(request: HttpRequest) -> HttpResponse:
    template = """
<!DOCTYPE html>
<html>
<head><title>{{ site_name|title }}</title></head>
<body>
    <h1>Selamat datang di {{ site_name|upper }}!</h1>
    <p>Pengguna: <strong>{{ user.username }}</strong> (Status: {{ user.status|default:Guest }})</p>
    <h3>Daftar Materi Pembelajaran:</h3>
    <ul>
        {% for course in courses %}
        <li><strong>{{ course.code }}</strong>: {{ course.title|title }} ({{ course.lecturer }})</li>
        {% endfor %}
    </ul>
</body>
</html>
    """
    context = {
        "site_name": "django architecture lab",
        "user": {"username": "hermes_developer", "status": "Active Senior Engineer"},
        "courses": [
            {"code": "CS-401", "title": "deep dive url dispatcher", "lecturer": "Guido van Rossum"},
            {"code": "CS-402", "title": "class based generic views", "lecturer": "Adrian Holovaty"},
            {"code": "CS-403", "title": "template inheritance and dtl", "lecturer": "Simon Willison"},
        ]
    }
    return render_to_response(template, context)

def post_detail_view(request: HttpRequest, post_id: int, slug: str) -> HttpResponse:
    template = """
<article>
    <h2>Post #{{ post.id }}: {{ post.title|upper }}</h2>
    <div class="meta">Slug: /posts/{{ post.slug }}/ | Dilihat: {{ post.views }} kali</div>
    <hr/>
    <p>{{ post.content|truncate:50 }}</p>
</article>
    """
    context = {
        "post": {
            "id": post_id,
            "title": f"Misteri Routing Django di {slug}",
            "slug": slug,
            "views": 4120,
            "content": "Pada modul ini kita mengupas tuntas bagaimana URLconf memetakan pola regex path converter ke fungsi view target secara efisien."
        }
    }
    return render_to_response(template, context)

# Class-Based View (CBV) Simulation
class View:
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']

    @classmethod
    def as_view(cls, **initkwargs):
        def view(request: HttpRequest, *args, **kwargs):
            self = cls(**initkwargs)
            return self.dispatch(request, *args, **kwargs)
        return view

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        handler_name = request.method.lower()
        if handler_name in self.http_method_names and hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            return handler(request, *args, **kwargs)
        return HttpResponse(f"Method {request.method} Not Allowed", status=405)

class CourseCatalogCBV(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        catalog_template = """
<section class="cbv-catalog">
    <h2>CBV Course Catalog - Dispatcher Class Based</h2>
    <p>Rendered via: <code>CourseCatalogCBV.as_view()</code></p>
    <ul>
        {% for item in items %}
        <li>{{ item.name|upper }} - Level: {{ item.level }}</li>
        {% endfor %}
    </ul>
</section>
        """
        ctx = {
            "items": [
                {"name": "fullstack python web", "level": "Advanced"},
                {"name": "distributed caching with redis", "level": "Expert"},
            ]
        }
        return render_to_response(catalog_template, ctx)

    def post(self, request: HttpRequest) -> HttpResponse:
        return HttpResponse("JSON: {'status': 'created', 'msg': 'Course added via POST CBV'}", status=201, content_type="application/json")

# ==============================================================================
# 5. Middleware Pipeline
# ==============================================================================
class SecurityHeaderMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Pre-processing Request
        request.headers["X-Django-Security"] = "Passed-v4.2"
        response = self.get_response(request)
        # Post-processing Response
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

class TimingMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Runtime-Latency"] = f"{duration_ms:.2f}ms"
        return response

# ==============================================================================
# 6. Django Application Engine (WSGI Pipeline Handler)
# ==============================================================================
class DjangoAppSimulator:
    def __init__(self):
        self.resolver = URLResolver()
        self.middlewares: List[Callable] = []
        self._setup_routes()

    def _setup_routes(self):
        self.resolver.register("/", home_view, name="home")
        self.resolver.register("/posts/<int:post_id>/<slug:slug>/", post_detail_view, name="post-detail")
        self.resolver.register("/catalog/", CourseCatalogCBV.as_view(), name="course-catalog")

    def get_handler(self) -> Callable:
        # Base Handler
        def core_handler(req: HttpRequest) -> HttpResponse:
            view_func, kwargs = self.resolver.resolve(req.path)
            if not view_func:
                return HttpResponse("<h1>404 Not Found</h1><p>Pola URL tidak cocok dengan URLconf manapun.</p>", status=404)
            return view_func(req, **kwargs)

        # Build Middleware Onion
        handler = core_handler
        for mw in reversed(self.middlewares):
            handler = mw(handler)
        return handler

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        handler = self.get_handler()
        return handler(request)

# ==============================================================================
# 7. Interactive Terminal Runner
# ==============================================================================
def simulate_traffic():
    print_header("Simulasi Siklus Permintaan Django (Request-Response Cycle)")
    app = DjangoAppSimulator()
    app.middlewares.append(SecurityHeaderMiddleware)
    app.middlewares.append(TimingMiddleware)

    test_cases = [
        ("GET", "/", "Halaman Utama (FBV + SSR Engine List & Filter)"),
        ("GET", "/posts/42/arsitektur-django-modern/", "Detail Post (Path Converter int & slug)"),
        ("GET", "/catalog/", "CBV Catalog (Class-Based View GET)"),
        ("POST", "/catalog/", "CBV Catalog (Class-Based View POST Dispatch)"),
        ("GET", "/unknown/route/testing/", "Route Tidak Terdaftar (404 Handler)"),
    ]

    for method, path, label in test_cases:
        print_step(f"{method} {path}", label)
        req = HttpRequest(path=path, method=method)
        res = app.handle_request(req)

        # Output Status
        status_color = Color.GREEN if res.status in (200, 201) else Color.RED
        print(f" {Color.BOLD}Status Code:{Color.RESET} {status_color}{res.status}{Color.RESET}")
        print(f" {Color.BOLD}Headers Disuntikkan Middleware:{Color.RESET}")
        for hk, hv in res.headers.items():
            print(f"   {Color.MAGENTA}{hk}{Color.RESET}: {Color.WHITE}{hv}{Color.RESET}")

        print(f" {Color.BOLD}Body Preview:{Color.RESET}")
        preview = res.content.strip().split("\n")
        max_lines = 8
        for l in preview[:max_lines]:
            print(f"   {Color.DIM}|{Color.RESET} {l}")
        if len(preview) > max_lines:
            print(f"   {Color.DIM}| ... ({len(preview) - max_lines} baris lainnya disembunyikan){Color.RESET}")
        print("-" * 50)

def main():
    print(f"{Color.BOLD}{Color.BG_BLUE} DJANGO CORE LAB 01: VIEW LAYER & SSR ENGINE SIMULATOR {Color.RESET}")
    print(f"{Color.CYAN}Modul Interaktif Praktik Tanpa Dependensi Pihak Ketiga{Color.RESET}\n")

    simulate_traffic()

    print_header("Eksplorasi Interaktif Mandiri")
    print("Masukkan path yang ingin Anda uji terhadap URLconf simulator.")
    print("Contoh yang valid:")
    print("  - /")
    print("  - /posts/101/pembahasan-dtl/")
    print("  - /catalog/")
    print("  - (atau ketik 'exit' untuk mengakhiri)\n")

    app = DjangoAppSimulator()
    app.middlewares.append(SecurityHeaderMiddleware)
    app.middlewares.append(TimingMiddleware)

    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}[INFO] Non-interactive environment detected. Skipping input loop.{Color.RESET}")
        print(f"{Color.GREEN}✓ Lab simulasi selesai dieksekusi dengan sukses.{Color.RESET}")
        return

    while True:
        try:
            user_input = input(f"{Color.BOLD}{Color.GREEN}django-sim > {Color.RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print(f"{Color.CYAN}Menutup simulasi lab. Sampai jumpa!{Color.RESET}")
                break

            req = HttpRequest(path=user_input, method="GET")
            resp = app.handle_request(req)

            status_col = Color.GREEN if resp.status == 200 else Color.RED
            print(f"Status: {status_col}{resp.status}{Color.RESET} | Content-Type: {resp.content_type}")
            print(f"Response:\n{resp.content.strip()}\n")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Color.CYAN}Selesai.{Color.RESET}")
            break

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Django Production Architecture Simulation: View Layer, URL Routing & SSR Engine
BAB-04: View Layer, URL Routing, dan Server-Side Rendering (SSR) Engine

Simulasi mandiri (zero external dependencies) arsitektur produksi Django:
1. URL Dispatcher & Path Converters (Regex-based resolver, reverse lookup)
2. Class-Based Views (CBV) Hierarchy: View, TemplateView, ListView, DetailView
3. View Decorators & Middleware Pipeline (CSRF, Request Timing, Auth Guard)
4. SSR Template Engine (Context Processors, Variable Resolution, Safe Filter, Loops)
5. Interactive CLI Runner dengan ANSI terminal styling
"""

import sys
import re
import time
import html
from typing import Callable, Dict, Any, List, Optional, Tuple


# ==============================================================================
# ANSI Color Palette for Rich Terminal UI
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

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
    BG_DARK = "\033[100m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === [ {title} ] === {Color.RESET}")


def info(msg: str) -> None:
    print(f"{Color.CYAN}[INFO]{Color.RESET} {msg}")


def success(msg: str) -> None:
    print(f"{Color.GREEN}[SUCCESS]{Color.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")


def error(msg: str) -> None:
    print(f"{Color.RED}[ERROR]{Color.RESET} {msg}")


# ==============================================================================
# 1. HTTP Request & Response Primitives
# ==============================================================================
class HttpRequest:
    def __init__(
        self,
        path: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        user: Optional[Dict[str, Any]] = None,
    ):
        self.path = path
        self.method = method.upper()
        self.headers = headers or {}
        self.GET = params or {}
        self.user = user or {"is_authenticated": False, "username": "AnonymousUser"}
        self.meta: Dict[str, Any] = {"START_TIME": time.time()}


class HttpResponse:
    def __init__(self, content: str = "", status_code: int = 200, content_type: str = "text/html"):
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def render(self) -> str:
        status_color = Color.GREEN if self.status_code == 200 else (Color.YELLOW if self.status_code < 500 else Color.RED)
        lines = [
            f"{Color.BOLD}HTTP/1.1 {status_color}{self.status_code}{Color.RESET}",
            f"{Color.DIM}Content-Type: {self.headers.get('Content-Type')}{Color.RESET}",
            f"{Color.DIM}Content-Length: {len(self.content)} bytes{Color.RESET}",
            "-" * 60,
            self.content,
            "-" * 60,
        ]
        return "\n".join(lines)


# ==============================================================================
# 2. Server-Side Rendering (SSR) Template Engine
# ==============================================================================
class TemplateContext(dict):
    """Context object with support for context processors."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def auth_context_processor(request: HttpRequest) -> Dict[str, Any]:
    return {"user": request.user}


def site_context_processor(request: HttpRequest) -> Dict[str, Any]:
    return {"site_name": "Production Django Enterprise SSR", "current_year": 2026}


class SimpleDTLEngine:
    """Simulates Django Template Language (DTL) parser and renderer."""
    CONTEXT_PROCESSORS = [auth_context_processor, site_context_processor]

    @classmethod
    def render_to_string(cls, template_src: str, context: Dict[str, Any], request: HttpRequest) -> str:
        merged_context = {}
        for cp in cls.CONTEXT_PROCESSORS:
            merged_context.update(cp(request))
        merged_context.update(context)

        output = template_src

        # 1. Parse For Loops: {% for item in items %} ... {% endfor %}
        loop_pattern = re.compile(r"{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}(.*?){%\s*endfor\s*%}", re.DOTALL)

        def replace_loop(match):
            item_var = match.group(1)
            list_var = match.group(2)
            body = match.group(3)

            items = merged_context.get(list_var, [])
            rendered_chunks = []
            for itm in items:
                chunk = body
                if isinstance(itm, dict):
                    for k, v in itm.items():
                        chunk = chunk.replace(f"{{{{ {item_var}.{k} }}}}", html.escape(str(v)))
                else:
                    chunk = chunk.replace(f"{{{{ {item_var} }}}}", html.escape(str(itm)))
                rendered_chunks.append(chunk)
            return "".join(rendered_chunks)

        output = loop_pattern.sub(replace_loop, output)

        # 2. Parse Variable Interpolation & Filters: {{ var }} or {{ var|filter }}
        var_pattern = re.compile(r"{{\s*([\w.]+)(?:\|(\w+))?\s*}}")

        def replace_var(match):
            var_path = match.group(1)
            filt = match.group(2)

            parts = var_path.split(".")
            val = merged_context
            for p in parts:
                if isinstance(val, dict) and p in val:
                    val = val[p]
                elif hasattr(val, p):
                    val = getattr(val, p)
                else:
                    val = ""
                    break

            val_str = str(val) if val is not None else ""
            if filt == "upper":
                val_str = val_str.upper()
            elif filt == "lower":
                val_str = val_str.lower()
            elif filt == "safe":
                return val_str

            return html.escape(val_str)

        output = var_pattern.sub(replace_var, output)
        return output.strip()


# ==============================================================================
# 3. URL Dispatcher & Path Resolvers
# ==============================================================================
class URLPattern:
    CONVERTERS = {
        "int": r"(?P<{}>\d+)",
        "slug": r"(?P<{}>[-a-zA-Z0-9_]+)",
        "str": r"(?P<{}>[^/]+)",
    }

    def __init__(self, route: str, view: Callable, name: str):
        self.route = route
        self.view = view
        self.name = name
        self.regex = self._compile_route(route)

    def _compile_route(self, route: str) -> re.Pattern:
        regex_pattern = "^"
        segments = route.split("/")
        parsed_segments = []
        for seg in segments:
            if not seg:
                continue
            if seg.startswith("<") and seg.endswith(">"):
                inner = seg[1:-1]
                if ":" in inner:
                    conv, param = inner.split(":", 1)
                else:
                    conv, param = "str", inner
                conv_regex = self.CONVERTERS.get(conv, r"(?P<{}>[^/]+)").format(param)
                parsed_segments.append(conv_regex)
            else:
                parsed_segments.append(re.escape(seg))

        if route.startswith("/"):
            regex_pattern += "/"
        regex_pattern += "/".join(parsed_segments)
        if route.endswith("/") and len(route) > 1:
            regex_pattern += "/"
        regex_pattern += "$"
        return re.compile(regex_pattern)

    def match(self, path: str) -> Optional[Dict[str, Any]]:
        m = self.regex.match(path)
        if not m:
            return None
        kwargs = m.groupdict()
        # Convert types
        for k, v in kwargs.items():
            if v.isdigit():
                kwargs[k] = int(v)
        return kwargs


class URLResolver:
    def __init__(self, patterns: List[URLPattern]):
        self.patterns = patterns

    def resolve(self, path: str) -> Tuple[Callable, Dict[str, Any]]:
        for pattern in self.patterns:
            kwargs = pattern.match(path)
            if kwargs is not None:
                return pattern.view, kwargs
        raise LookupError(f"Page not found (404): No URL matches '{path}'")

    def reverse(self, name: str, **kwargs) -> str:
        for p in self.patterns:
            if p.name == name:
                res = p.route
                for k, v in kwargs.items():
                    res = re.sub(rf"<(\w+:)?{k}>", str(v), res)
                return res
        raise ValueError(f"Reverse for '{name}' with args {kwargs} not found.")


# ==============================================================================
# 4. Middleware & Decorators Pipeline
# ==============================================================================
def require_http_methods(allowed: List[str]):
    def decorator(view_func: Callable):
        def wrapper(request: HttpRequest, *args, **kwargs):
            if request.method not in allowed:
                return HttpResponse(
                    f"405 Method Not Allowed: Method {request.method} is not permitted for this resource.",
                    status_code=405
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def login_required(view_func: Callable):
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.get("is_authenticated", False):
            return HttpResponse(
                "<h3>403 Forbidden: Anda harus login untuk mengakses sumber daya ini.</h3>",
                status_code=403
            )
        return view_func(request, *args, **kwargs)
    return wrapper


class ExecutionTimeMiddleware:
    @staticmethod
    def process_request(request: HttpRequest) -> None:
        request.meta["START_TIME"] = time.time()

    @staticmethod
    def process_response(request: HttpRequest, response: HttpResponse) -> HttpResponse:
        duration_ms = (time.time() - request.meta.get("START_TIME", time.time())) * 1000
        response.headers["X-Runtime-Ms"] = f"{duration_ms:.2f}ms"
        return response


# ==============================================================================
# 5. Class-Based Views (CBV) Framework
# ==============================================================================
class View:
    http_method_names = ["get", "post", "put", "delete", "head", "options"]

    @classmethod
    def as_view(cls, **initkwargs):
        def view(request: HttpRequest, *args, **kwargs):
            self = cls(**initkwargs)
            return self.dispatch(request, *args, **kwargs)
        return view

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        method = request.method.lower()
        if method in self.http_method_names:
            handler = getattr(self, method, self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed
        return handler(request, *args, **kwargs)

    def http_method_not_allowed(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return HttpResponse(f"Method Not Allowed ({request.method})", status_code=405)


class TemplateView(View):
    template_name: str = ""

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        return kwargs

    def render_to_response(self, context: Dict[str, Any], request: HttpRequest) -> HttpResponse:
        body = SimpleDTLEngine.render_to_string(self.template_name, context, request)
        return HttpResponse(body, status_code=200)

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context, request)


class ListView(TemplateView):
    model_data: List[Dict[str, Any]] = []
    context_object_name: str = "object_list"

    def get_queryset(self) -> List[Dict[str, Any]]:
        return self.model_data

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context[self.context_object_name] = self.get_queryset()
        return context


class DetailView(TemplateView):
    model_data: List[Dict[str, Any]] = []
    context_object_name: str = "object"
    pk_url_kwarg: str = "pk"

    def get_object(self, pk: int) -> Optional[Dict[str, Any]]:
        for item in self.model_data:
            if item.get("id") == pk:
                return item
        return None

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        pk = kwargs.get(self.pk_url_kwarg)
        obj = self.get_object(pk)
        if not obj:
            return HttpResponse(f"404 Not Found: Item dengan id={pk} tidak ditemukan.", status_code=404)
        context = self.get_context_data(**kwargs)
        context[self.context_object_name] = obj
        return self.render_to_response(context, request)


# ==============================================================================
# 6. Concrete Application Views & Templates
# ==============================================================================
SAMPLE_COURSES = [
    {"id": 101, "title": "Advanced Django View Architecture", "category": "Backend", "level": "Expert"},
    {"id": 102, "title": "Mastering Class-Based Views (CBV)", "category": "Architecture", "level": "Advanced"},
    {"id": 103, "title": "High-Performance SSR & DTL Caching", "category": "Performance", "level": "Intermediate"},
]

HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>{{ site_name }}</title></head>
<body>
  <h1>Selamat Datang di {{ site_name }}</h1>
  <p>User Aktif: <strong>{{ user.username }}</strong></p>
  <p>Tahun Operasional: {{ current_year }}</p>
  <hr/>
  <h3>Navigasi Modul:</h3>
  <ul>
    <li><a href="/courses/">Katalog Kelas (ListView)</a></li>
    <li><a href="/dashboard/">Admin Dashboard (Protected CBV)</a></li>
  </ul>
</body>
</html>
"""

COURSE_LIST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Daftar Kursus - {{ site_name }}</title></head>
<body>
  <h2>Daftar Kursus Terakreditasi</h2>
  <ul>
  {% for course in courses %}
    <li>[{{ course.category }}] {{ course.title }} (Level: {{ course.level }}) - ID: {{ course.id }}</li>
  {% endfor %}
  </ul>
</body>
</html>
"""

COURSE_DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>{{ course.title }} - Detail</title></head>
<body>
  <h1>Modul: {{ course.title }}</h1>
  <p>Kategori: {{ course.category }}</p>
  <p>Tingkat Kesulitan: {{ course.level }}</p>
  <p>ID Rekaman: {{ course.id }}</p>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Admin Command Center</title></head>
<body>
  <h1>Panel Kontrol Produksi</h1>
  <p>Selamat datang, Administrator <strong>{{ user.username|upper }}</strong>!</p>
  <p>Status Server: Online (Production High-Availability Cluster)</p>
</body>
</html>
"""


class HomeView(TemplateView):
    template_name = HOME_TEMPLATE


class CourseListView(ListView):
    template_name = COURSE_LIST_TEMPLATE
    model_data = SAMPLE_COURSES
    context_object_name = "courses"


class CourseDetailView(DetailView):
    template_name = COURSE_DETAIL_TEMPLATE
    model_data = SAMPLE_COURSES
    context_object_name = "course"


class DashboardView(TemplateView):
    template_name = DASHBOARD_TEMPLATE

    @classmethod
    def as_view(cls, **initkwargs):
        # Penerapan decorator login_required pada dispatch
        raw_view = super().as_view(**initkwargs)
        return login_required(raw_view)


# FBV Contoh
@require_http_methods(["GET", "POST"])
def health_check_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse('{"status": "healthy", "service": "django-ssr-worker"}', content_type="application/json")


# ==============================================================================
# 7. URL Configuration (urls.py)
# ==============================================================================
urlpatterns = [
    URLPattern(r"/", HomeView.as_view(), name="home"),
    URLPattern(r"/courses/", CourseListView.as_view(), name="course_list"),
    URLPattern(r"/courses/<int:pk>/", CourseDetailView.as_view(), name="course_detail"),
    URLPattern(r"/dashboard/", DashboardView.as_view(), name="admin_dashboard"),
    URLPattern(r"/api/health/", health_check_view, name="health_check"),
]

url_resolver = URLResolver(urlpatterns)


# ==============================================================================
# 8. Dispatcher Execution Pipeline
# ==============================================================================
def process_http_request(request: HttpRequest) -> HttpResponse:
    ExecutionTimeMiddleware.process_request(request)
    try:
        view_func, kwargs = url_resolver.resolve(request.path)
        response = view_func(request, **kwargs)
    except LookupError as le:
        response = HttpResponse(f"<h1>404 Not Found</h1><p>{str(le)}</p>", status_code=404)
    except Exception as e:
        response = HttpResponse(f"<h1>500 Internal Server Error</h1><p>{str(e)}</p>", status_code=500)

    response = ExecutionTimeMiddleware.process_response(request, response)
    return response


# ==============================================================================
# 9. Interactive Simulation Shell & Automated Benchmark
# ==============================================================================
def run_automated_suite():
    header("MENJALANKAN SUITE VERIFIKASI ARSITEKTUR DJANGO SSR")

    test_scenarios = [
        ("GET Home View (TemplateView & Context Processors)", HttpRequest("/")),
        ("GET Course List (ListView & DTL Loop Tag)", HttpRequest("/courses/")),
        ("GET Course Detail (DetailView Converter <int:pk> = 102)", HttpRequest("/courses/102/")),
        ("GET DetailView Invalid PK (404 Object Not Found)", HttpRequest("/courses/999/")),
        ("GET Protected Dashboard sbg Anonymous (Guard: 403 Forbidden)", HttpRequest("/dashboard/")),
        (
            "GET Protected Dashboard sbg Admin (Auth Passed)",
            HttpRequest("/dashboard/", user={"is_authenticated": True, "username": "chief_architect"}),
        ),
        ("POST Method to Health Check (FBV Method Check)", HttpRequest("/api/health/", method="POST")),
        ("DELETE Method to Health Check (405 Method Not Allowed)", HttpRequest("/api/health/", method="DELETE")),
        ("GET Non-existent URL (404 Resolver Miss)", HttpRequest("/random/not/found/")),
    ]

    for title, req in test_scenarios:
        print(f"\n{Color.BOLD}{Color.MAGENTA}>> Skenario:{Color.RESET} {Color.WHITE}{title}{Color.RESET}")
        info(f"Dispatching HTTP {req.method} -> {req.path}")
        resp = process_http_request(req)
        print(resp.render())
        print(f"{Color.CYAN}Runtime Header:{Color.RESET} {resp.headers.get('X-Runtime-Ms', 'N/A')}")
        time.sleep(0.05)

    header("URL REVERSE RESOLUTION TEST")
    rev_home = url_resolver.reverse("home")
    rev_detail = url_resolver.reverse("course_detail", pk=101)
    success(f"Reverse 'home' => {rev_home}")
    success(f"Reverse 'course_detail' (pk=101) => {rev_detail}")


def interactive_cli():
    print(f"\n{Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} SIMULATOR INTERAKTIF DJANGO VIEW LAYER & SSR {Color.RESET}")
    print(f"{Color.DIM}Ketik path URL yang ingin diuji, atau ketik 'exit' untuk keluar.{Color.RESET}")
    print(f"{Color.YELLOW}Pilihan path contoh:{Color.RESET}")
    print("  1. /")
    print("  2. /courses/")
    print("  3. /courses/101/")
    print("  4. /courses/102/")
    print("  5. /dashboard/")
    print("  6. /api/health/")

    is_admin = False

    while True:
        try:
            status_auth = f"{Color.GREEN}Authenticated (admin){Color.RESET}" if is_admin else f"{Color.YELLOW}Anonymous{Color.RESET}"
            prompt = f"\n[{status_auth}] Masukkan URL path: "
            user_input = input(prompt).strip()

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print(f"{Color.CYAN}Menutup simulator Django. Selesai.{Color.RESET}")
                break
            if user_input.lower() == "toggle-auth":
                is_admin = not is_admin
                info(f"Status autentikasi diubah menjadi: {'Admin' if is_admin else 'Anonymous'}")
                continue

            user_obj = {"is_authenticated": True, "username": "lead_engineer"} if is_admin else {"is_authenticated": False, "username": "AnonymousUser"}
            req = HttpRequest(path=user_input, method="GET", user=user_obj)
            res = process_http_request(req)
            print(res.render())
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari mode interaktif.")
            break


def main():
    print(f"{Color.BOLD}{Color.BLUE}Memulai Lab Exercise: Django View Layer & SSR Engine (BAB-04){Color.RESET}")
    run_automated_suite()

    if sys.stdin.isatty():
        interactive_cli()
    else:
        info("Mode non-interaktif terdeteksi (stdin bukan TTY). Melewati loop input CLI.")


if __name__ == "__main__":
    main()

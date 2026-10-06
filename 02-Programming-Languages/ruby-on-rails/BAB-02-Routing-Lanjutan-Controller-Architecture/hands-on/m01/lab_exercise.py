#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Engine Routing Lanjutan & Controller Architecture Ruby on Rails
Modul: BAB-02 Routing Lanjutan & Controller Architecture
"""

import re
import sys
import time
from typing import Callable, Dict, Any, List, Optional, Tuple

# ANSI Color Codes untuk output visual terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"


class ActionControllerError(Exception):
    """Base exception controller."""
    pass


class ParameterMissingError(ActionControllerError):
    """Simulasi ActionController::ParameterMissing."""
    def __init__(self, param: str):
        super().__init__(f"param is missing or the value is empty: {param}")
        self.param = param


class RecordNotFoundError(ActionControllerError):
    """Simulasi ActiveRecord::RecordNotFound."""
    def __init__(self, resource: str, record_id: Any):
        super().__init__(f"Couldn't find {resource} with 'id'={record_id}")
        self.resource = resource
        self.record_id = record_id


class RoutingError(ActionControllerError):
    """Simulasi ActionController::RoutingError."""
    pass


class Parameters:
    """
    Simulasi ActionController::Parameters & Strong Parameters:
    params.require(:key).permit(:field1, :field2)
    """
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def require(self, key: str) -> "Parameters":
        if key not in self._data or not isinstance(self._data[key], dict):
            raise ParameterMissingError(key)
        return Parameters(self._data[key])

    def permit(self, *allowed_fields: str) -> Dict[str, Any]:
        return {k: v for k, v in self._data.items() if k in allowed_fields}

    def __getitem__(self, item: str) -> Any:
        return self._data.get(item)

    def to_dict(self) -> Dict[str, Any]:
        return self._data


class Route:
    """Representasi satu entri route dalam routing table Rails."""
    def __init__(
        self,
        verb: str,
        path_pattern: str,
        controller_cls: type,
        action: str,
        constraints: Optional[Dict[str, str]] = None,
        helper_name: Optional[str] = None
    ):
        self.verb = verb.upper()
        self.path_pattern = path_pattern
        self.controller_cls = controller_cls
        self.action = action
        self.constraints = constraints or {}
        self.helper_name = helper_name
        self.regex, self.param_keys = self._compile_pattern(path_pattern)

    def _compile_pattern(self, pattern: str) -> Tuple[re.Pattern, List[str]]:
        segments = pattern.strip("/").split("/")
        param_keys = []
        regex_parts = []

        for seg in segments:
            if not seg:
                continue
            if seg.startswith(":"):
                param_name = seg[1:]
                param_keys.append(param_name)
                constraint = self.constraints.get(param_name, r"[^/]+")
                regex_parts.append(f"(?P<{param_name}>{constraint})")
            else:
                regex_parts.append(re.escape(seg))

        compiled_regex = re.compile(r"^/" + r"/".join(regex_parts) + r"/?$")
        return compiled_regex, param_keys

    def match(self, verb: str, path: str) -> Optional[Dict[str, Any]]:
        if self.verb != verb.upper():
            return None
        match = self.regex.match(path)
        if match:
            return match.groupdict()
        return None


class Router:
    """
    Simulasi DSL ActionDispatch::Routing::RouteSet.
    Mendukung nested resources, member/collection routes, dan namespace.
    """
    def __init__(self):
        self.routes: List[Route] = []

    def add_route(
        self,
        verb: str,
        path: str,
        controller_cls: type,
        action: str,
        constraints: Optional[Dict[str, str]] = None,
        helper_name: Optional[str] = None
    ):
        self.routes.append(Route(verb, path, controller_cls, action, constraints, helper_name))

    def draw_resources(
        self,
        resource_name: str,
        controller_cls: type,
        only: Optional[List[str]] = None,
        constraints: Optional[Dict[str, str]] = None,
        member_actions: Optional[Dict[str, str]] = None,      # {"publish": "POST"}
        collection_actions: Optional[Dict[str, str]] = None   # {"search": "GET"}
    ):
        id_constraint = constraints or {"id": r"\d+"}
        standard = [
            ("GET", f"/{resource_name}", "index", f"{resource_name}_path"),
            ("POST", f"/{resource_name}", "create", f"{resource_name}_path"),
            ("GET", f"/{resource_name}/:id", "show", f"{resource_name.rstrip('s')}_path"),
            ("PUT", f"/{resource_name}/:id", "update", f"{resource_name.rstrip('s')}_path"),
            ("PATCH", f"/{resource_name}/:id", "update", f"{resource_name.rstrip('s')}_path"),
            ("DELETE", f"/{resource_name}/:id", "destroy", f"{resource_name.rstrip('s')}_path")
        ]

        if collection_actions:
            for act, verb in collection_actions.items():
                self.add_route(verb, f"/{resource_name}/{act}", controller_cls, act, id_constraint, f"{act}_{resource_name}_path")

        for verb, path, act, helper in standard:
            if only is None or act in only:
                self.add_route(verb, path, controller_cls, act, id_constraint, helper)

        if member_actions:
            for act, verb in member_actions.items():
                self.add_route(verb, f"/{resource_name}/:id/{act}", controller_cls, act, id_constraint, f"{act}_{resource_name.rstrip('s')}_path")

    def recognize(self, verb: str, path: str) -> Tuple[Route, Dict[str, Any]]:
        for route in self.routes:
            params = route.match(verb, path)
            if params is not None:
                return route, params
        raise RoutingError(f"No route matches [{verb.upper()}] \"{path}\"")

    def print_routes(self):
        print(f"\n{BOLD}{CYAN}=== DAFTAR ROUTES (RAILS ROUTES) ==={RESET}")
        print(f"{'PREFIX':<24} {'VERB':<8} {'URI PATTERN':<32} {'CONTROLLER#ACTION'}")
        print("-" * 80)
        for r in self.routes:
            prefix = r.helper_name or ""
            c_name = r.controller_cls.__name__.replace("Controller", "").lower()
            target = f"{c_name}#{r.action}"
            print(f"{GREEN}{prefix:<24}{RESET} {YELLOW}{r.verb:<8}{RESET} {r.path_pattern:<32} {target}")
        print("-" * 80)


class BaseController:
    """
    Simulasi ActionController::Base dengan callback filter,
    exception handling (rescue_from), dan context response.
    """
    def __init__(self, request_params: Dict[str, Any]):
        self.params = Parameters(request_params)
        self.response_body: Optional[Any] = None
        self.status_code: int = 200
        self.before_actions: List[Tuple[Callable, Optional[List[str]]]] = []
        self.around_actions: List[Tuple[Callable, Optional[List[str]]]] = []
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Override untuk mendaftarkan callback filter."""
        pass

    def add_before_action(self, filter_fn: Callable, only: Optional[List[str]] = None):
        self.before_actions.append((filter_fn, only))

    def add_around_action(self, filter_fn: Callable, only: Optional[List[str]] = None):
        self.around_actions.append((filter_fn, only))

    def render(self, body: Any, status: int = 200):
        self.response_body = body
        self.status_code = status

    def dispatch(self, action_name: str) -> Tuple[int, Any]:
        """Eksekusi siklus hidup request controller Rails."""
        try:
            # 1. Jalankan before_action filter
            for filter_fn, only_list in self.before_actions:
                if only_list is None or action_name in only_list:
                    filter_fn(action_name)
                    if self.response_body is not None:
                        # Early return/redirect di filter
                        return self.status_code, self.response_body

            # 2. Jalankan action dengan around_action jika ada
            action_method = getattr(self, action_name, None)
            if not action_method:
                raise ActionControllerError(f"Action '{action_name}' tidak ditemukan pada {self.__class__.__name__}")

            # Eksekusi aksi utama
            action_method()
            return self.status_code, self.response_body

        except RecordNotFoundError as exc:
            return self.rescue_record_not_found(exc)
        except ParameterMissingError as exc:
            return self.rescue_parameter_missing(exc)
        except Exception as exc:
            return self.rescue_standard_error(exc)

    def rescue_record_not_found(self, exc: RecordNotFoundError) -> Tuple[int, Any]:
        """Simulasi rescue_from ActiveRecord::RecordNotFound."""
        return 404, {"error": "Not Found", "detail": str(exc)}

    def rescue_parameter_missing(self, exc: ParameterMissingError) -> Tuple[int, Any]:
        """Simulasi rescue_from ActionController::ParameterMissing."""
        return 400, {"error": "Bad Request", "detail": str(exc)}

    def rescue_standard_error(self, exc: Exception) -> Tuple[int, Any]:
        """Simulasi rescue_from StandardError."""
        return 500, {"error": "Internal Server Error", "exception": str(exc)}


# Mock Database State
ARTICLES_DB = {
    "1": {"id": 1, "title": "Arsitektur Ruby on Rails", "body": "Membahas MVC dan Router", "status": "draft"},
    "2": {"id": 2, "title": "Deep Dive Controller Lifecycle", "body": "Before action dan Strong Params", "status": "published"}
}


class ArticlesController(BaseController):
    """
    Contoh implementasi controller lengkap dengan:
    - Callback before_action :set_article
    - Strong Parameters
    - Member Action (:publish) & Collection Action (:search)
    """
    def _setup_callbacks(self):
        self.article: Optional[Dict[str, Any]] = None
        self.add_before_action(self._set_article, only=["show", "update", "publish", "destroy"])

    def _set_article(self, action_name: str):
        article_id = str(self.params["id"])
        if article_id not in ARTICLES_DB:
            raise RecordNotFoundError("Article", article_id)
        self.article = ARTICLES_DB[article_id]
        print(f"  {BLUE}[Filter Callback]{RESET} `before_action :set_article` dimuat untuk ID: {article_id}")

    def article_params(self) -> Dict[str, Any]:
        """Simulasi Strong Parameters: params.require(:article).permit(:title, :body, :status)"""
        return self.params.require("article").permit("title", "body", "status")

    def index(self):
        self.render({"articles": list(ARTICLES_DB.values()), "total": len(ARTICLES_DB)}, 200)

    def show(self):
        self.render({"article": self.article}, 200)

    def create(self):
        permitted = self.article_params()
        new_id = str(max([int(k) for k in ARTICLES_DB.keys()] or [0]) + 1)
        new_article = {"id": int(new_id), **permitted}
        ARTICLES_DB[new_id] = new_article
        self.render({"status": "created", "article": new_article}, 201)

    def update(self):
        permitted = self.article_params()
        self.article.update(permitted)
        self.render({"status": "updated", "article": self.article}, 200)

    def publish(self):
        """Member Route: POST /articles/:id/publish"""
        self.article["status"] = "published"
        self.render({"status": "published", "article": self.article}, 200)

    def search(self):
        """Collection Route: GET /articles/search?q=..."""
        query = str(self.params.to_dict().get("q", "")).lower()
        results = [
            a for a in ARTICLES_DB.values()
            if query in a["title"].lower() or query in a["body"].lower()
        ]
        self.render({"query": query, "matches": results, "count": len(results)}, 200)


def build_application_router() -> Router:
    """Membangun tabel routing Rails dengan arsitektur RESTful & Lanjutan."""
    router = Router()
    router.draw_resources(
        resource_name="articles",
        controller_cls=ArticlesController,
        constraints={"id": r"\d+"},
        member_actions={"publish": "POST"},
        collection_actions={"search": "GET"}
    )
    return router


def simulate_request(router: Router, verb: str, path: str, payload: Optional[Dict[str, Any]] = None):
    """Menjalankan simulasi request pipeline Rails dari router hingga controller response."""
    print(f"\n{BOLD}{MAGENTA}>>> INCOMING REQUEST:{RESET} {BOLD}{verb.upper()} {path}{RESET}")
    start_time = time.perf_counter()

    try:
        route, path_params = router.recognize(verb, path)
        print(f"  {GREEN}[Router Matched]{RESET} Route -> {route.path_pattern} ({route.controller_cls.__name__}#{route.action})")
        print(f"  {CYAN}[Path Params]{RESET} {path_params}")

        # Gabungkan path parameters dengan request payload
        merged_params = dict(path_params)
        if payload:
            merged_params.update(payload)

        # Inisialisasi Controller dan dispatch aksi
        controller = route.controller_cls(merged_params)
        status, response = controller.dispatch(route.action)

        duration = (time.perf_counter() - start_time) * 1000
        status_color = GREEN if status < 400 else (YELLOW if status < 500 else RED)
        print(f"  {BOLD}HTTP Status:{RESET} {status_color}{status}{RESET} ({duration:.2f}ms)")
        print(f"  {BOLD}Response Body:{RESET} {response}")

    except RoutingError as err:
        duration = (time.perf_counter() - start_time) * 1000
        print(f"  {RED}[Routing Error - 404 ActionController::RoutingError]{RESET} {err} ({duration:.2f}ms)")


def interactive_menu(router: Router):
    """Menu interaktif simulasi terminal Rails."""
    while True:
        print(f"\n{BOLD}{BG_BLUE}   RUBY ON RAILS ROUTING & CONTROLLER LAB   {RESET}")
        print(f"1. Tampilkan Rails Route Table ({CYAN}rails routes{RESET})")
        print("2. Simulasi GET /articles (Index)")
        print("3. Simulasi GET /articles/1 (Show Article Valid)")
        print("4. Simulasi GET /articles/999 (Show Article 404 - RecordNotFound)")
        print("5. Simulasi POST /articles (Create - Strong Parameters Valid)")
        print("6. Simulasi POST /articles (Create - ParameterMissing Error)")
        print("7. Simulasi POST /articles/1/publish (Member Route)")
        print("8. Simulasi GET /articles/search?q=rails (Collection Route)")
        print("9. Simulasi Custom Path & Method Manual")
        print("0. Keluar")
        choice = input(f"\n{YELLOW}Pilih opsi (0-9): {RESET}").strip()

        if choice == "1":
            router.print_routes()
        elif choice == "2":
            simulate_request(router, "GET", "/articles")
        elif choice == "3":
            simulate_request(router, "GET", "/articles/1")
        elif choice == "4":
            simulate_request(router, "GET", "/articles/999")
        elif choice == "5":
            payload = {
                "article": {
                    "title": "Routing Lanjutan dan Shallow Nesting",
                    "body": "Penerapan clean URI design pattern",
                    "status": "draft",
                    "hacker_field": "hacked!"  # akan disaring oleh strong params
                }
            }
            simulate_request(router, "POST", "/articles", payload)
        elif choice == "6":
            # Payload salah: lupa membungkus dalam key 'article'
            bad_payload = {"title": "Lupa root parameter"}
            simulate_request(router, "POST", "/articles", bad_payload)
        elif choice == "7":
            simulate_request(router, "POST", "/articles/1/publish")
        elif choice == "8":
            simulate_request(router, "GET", "/articles/search", {"q": "rails"})
        elif choice == "9":
            verb = input("HTTP Verb (GET/POST/PUT/DELETE): ").strip().upper()
            path = input("Request URI path: ").strip()
            simulate_request(router, verb, path)
        elif choice == "0":
            print(f"\n{GREEN}Sesi lab selesai.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


if __name__ == "__main__":
    app_router = build_application_router()
    # Jika dijalankan dengan argumen --auto-test, eksekusi tes tanpa menunggu interaksi
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-test":
        print(f"{BOLD}{BG_GREEN} MENJALANKAN AUTOMATED VERIFICATION SUITE {RESET}")
        app_router.print_routes()
        simulate_request(app_router, "GET", "/articles")
        simulate_request(app_router, "GET", "/articles/1")
        simulate_request(app_router, "GET", "/articles/999")
        simulate_request(app_router, "POST", "/articles", {"article": {"title": "Automated", "body": "Auto test", "status": "draft"}})
        simulate_request(app_router, "POST", "/articles", {"wrong_root": 123})
        simulate_request(app_router, "POST", "/articles/1/publish")
        simulate_request(app_router, "GET", "/articles/search", {"q": "MVC"})
        simulate_request(app_router, "GET", "/non_existent_route")
        print(f"\n{GREEN}Semua skenario simulasi berhasil dijalankan.{RESET}")
    else:
        interactive_menu(app_router)

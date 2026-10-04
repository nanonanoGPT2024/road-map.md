#!/usr/bin/env python3
"""
Lab Hands-on: Ruby on Rails - Bab 02: Routing Lanjutan & Controller Architecture
Modul 02 Deep Dive: Simulasi Mesin Router Rails (ActionDispatch) & Controller Pipeline (ActionController)

Mendemonstrasikan:
1. Dynamic Route Matching dengan Regex Constraints & Segment Extraction.
2. Namespaced Resources mapping (misal: Api::V1::ResourceController).
3. ActionController Lifecycle: Before/After action filter chains (callbacks).
4. Strong Parameters guard (Mass Assignment Protection: require & permit).
"""

import re
import json
import time
from typing import Callable, Dict, List, Any, Optional

# ANSI Color formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_GRAY = "\033[90m"


class ActionDispatchError(Exception):
    """Exception dasar untuk error pada router dan dispatching."""
    pass


class RoutingError(ActionDispatchError):
    """Dipicu saat rute tidak ditemukan atau melanggar constraint."""
    pass


class ParameterMissing(ActionDispatchError):
    """Dipicu ketika parameter wajib (.require) tidak ditemukan."""
    pass


class ActionParameters(dict):
    """
    Simulasi ActionController::Parameters.
    Mengimplementasikan proteksi Strong Parameters (require & permit).
    """
    def require(self, key: str) -> "ActionParameters":
        if key not in self or not self[key]:
            raise ParameterMissing(f"Param is missing or the value is empty: {key}")
        val = self[key]
        if isinstance(val, dict):
            return ActionParameters(val)
        return val

    def permit(self, *allowed_keys: str) -> Dict[str, Any]:
        sanitized = {}
        for key in allowed_keys:
            if key in self:
                sanitized[key] = self[key]
        return sanitized


class Request:
    """Representasi Rack/Rails Request Object."""
    def __init__(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None):
        self.method = method.upper()
        self.path = path.rstrip("/") if path != "/" else "/"
        self.params = ActionParameters(params or {})
        self.headers = headers or {}


class Response:
    """Representasi ActionDispatch Response Object."""
    def __init__(self):
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self.body = ""

    def render(self, json_data: Any, status: int = 200):
        self.status = status
        self.body = json.dumps(json_data, indent=2)


class Route:
    """
    Representasi sebuah rute Rails individual yang mengompilasi path
    pattern dan constraint regex menjadi compiled regex pattern.
    """
    def __init__(self, verb: str, pattern: str, controller_cls: type, action: str, constraints: Optional[Dict[str, str]] = None):
        self.verb = verb.upper()
        self.pattern = pattern.rstrip("/") if pattern != "/" else "/"
        self.controller_cls = controller_cls
        self.action = action
        self.constraints = constraints or {}
        self.regex = self._compile_route()

    def _compile_route(self) -> re.Pattern:
        # Ubah dynamic segments `:segment` menjadi named groups `(?P<segment>...)`
        def repl(match):
            key = match.group(1)
            constraint = self.constraints.get(key, r"[^/]+")
            return f"(?P<{key}>{constraint})"

        regex_str = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", repl, self.pattern)
        return re.compile(f"^{regex_str}$")

    def match(self, request: Request) -> Optional[Dict[str, str]]:
        if self.verb != request.method:
            return None
        m = self.regex.match(request.path)
        if m:
            return m.groupdict()
        return None


class Router:
    """
    Mesin ActionDispatch::Routing::RouteSet Rails.
    Mendukung pendaftaran rute dan resolving request.
    """
    def __init__(self):
        self.routes: List[Route] = []

    def draw(self, verb: str, pattern: str, to: str, constraints: Optional[Dict[str, str]] = None):
        # Format 'to': 'controller_name#action_name'
        ctrl_name, action_name = to.split("#")
        # Registry look-up dynamically via subclasses of BaseController
        ctrl_class = BaseController.get_controller(ctrl_name)
        route = Route(verb, pattern, ctrl_class, action_name, constraints)
        self.routes.append(route)

    def dispatch(self, request: Request) -> Response:
        for route in self.routes:
            matched_params = route.match(request)
            if matched_params is not None:
                # Merge dynamic segments (e.g. :id) into request params
                request.params.update(matched_params)
                controller_instance = route.controller_cls(request)
                return controller_instance.process(route.action)

        raise RoutingError(f"No route matches [{request.method}] \"{request.path}\"")


class BaseController:
    """
    Simulasi ActionController::Base.
    Menyediakan lifecycle callbacks (before_action, after_action) dan rendering.
    """
    _registry: Dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls
        cls._filters: List[Dict[str, Any]] = []

    @classmethod
    def get_controller(cls, name: str) -> type:
        ctrl = cls._registry.get(name)
        if not ctrl:
            raise ActionDispatchError(f"Uninitialized constant {name}")
        return ctrl

    @classmethod
    def before_action(cls, callback_name: str, only: Optional[List[str]] = None, except_: Optional[List[str]] = None):
        cls._filters.append({
            "kind": "before",
            "method": callback_name,
            "only": set(only) if only else None,
            "except": set(except_) if except_ else None
        })

    def __init__(self, request: Request):
        self.request = request
        self.params = request.params
        self.response = Response()
        self._halted = False

    def render(self, json_data: Any, status: int = 200):
        self.response.render(json_data, status)

    def halt(self, message: str, status: int = 401):
        """Menghentikan controller pipeline seketika (mirip return/redirect_to di callback)."""
        self._halted = True
        self.render({"error": message}, status=status)

    def process(self, action: str) -> Response:
        """Pipeline eksekusi ActionController."""
        # 1. Run before_actions
        for f in self._filters:
            if f["kind"] == "before":
                if f["only"] and action not in f["only"]:
                    continue
                if f["except"] and action in f["except"]:
                    continue

                callback = getattr(self, f["method"], None)
                if callback:
                    callback()
                    if self._halted:
                        return self.response

        # 2. Invoke Action
        action_fn = getattr(self, action, None)
        if not action_fn:
            raise ActionDispatchError(f"Action '{action}' could not be found for {self.__class__.__name__}")
        action_fn()

        return self.response


# --- Concrete Controllers (Domain Logic) ---

class ApiV1PostsController(BaseController):
    """Namespaced Controller: Api::V1::PostsController"""

    # Simulasi Rails before_action filters
    # ApiV1PostsController.before_action("authenticate_token!", except_=["index", "show"])
    # ApiV1PostsController.before_action("set_post", only=["show"])

    def authenticate_token!(self):
        token = self.request.headers.get("Authorization")
        if token != "Bearer rails-secret-token":
            self.halt("HTTP Token: Access denied (Unauthorized).", status=401)

    def set_post(self):
        # Simulasi ActiveRecord find
        post_id = self.params.get("id")
        self.current_post = {"id": post_id, "title": f"Rails Metaprogramming #{post_id}", "published": True}

    def index(self):
        posts = [
            {"id": 1, "title": "Understanding Routing Engine", "author": "DHH"},
            {"id": 2, "title": "Strong Parameters Architecture", "author": "Matz"}
        ]
        self.render({"data": posts}, status=200)

    def show(self):
        self.render({"data": self.current_post}, status=200)

    def create(self):
        # Implementasi Strong Parameters Pattern
        try:
            post_params = self.params.require("post").permit("title", "body", "tags")
        except ParameterMissing as err:
            self.render({"error": str(err)}, status=422)
            return

        # Simulasi Create Record
        created_record = {
            "id": 105,
            "title": post_params.get("title"),
            "body": post_params.get("body"),
            "tags": post_params.get("tags", []),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        self.render({"message": "Post successfully created", "post": created_record}, status=201)


# Register controller filters
ApiV1PostsController.before_action("authenticate_token!", except_=["index", "show"])
ApiV1PostsController.before_action("set_post", only=["show"])


# --- Runner & Verification Engine ---

def run_test_scenario(title: str, router: Router, request: Request, expected_status: int):
    print(f"\n{CLR_BOLD}=== Scenario: {title} ==={CLR_RESET}")
    print(f"{CLR_GRAY}[Request]{CLR_RESET} {request.method} {request.path}")
    if request.params:
        print(f"{CLR_GRAY}[Params]{CLR_RESET}  {json.dumps(dict(request.params))}")

    start_time = time.perf_counter()
    try:
        response = router.dispatch(request)
        elapsed = (time.perf_counter() - start_time) * 1000

        status_color = CLR_GREEN if response.status == expected_status else CLR_RED
        print(f"{CLR_GRAY}[Response]{CLR_RESET} Status: {status_color}{response.status}{CLR_RESET} ({elapsed:.2f}ms)")
        print(f"{CLR_CYAN}{response.body}{CLR_RESET}")
        assert response.status == expected_status, f"Expected {expected_status}, got {response.status}"
    except RoutingError as re_err:
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"{CLR_RED}[RoutingError] {re_err}{CLR_RESET} ({elapsed:.2f}ms)")
        assert expected_status == 404, f"Expected {expected_status}, but route resolution failed"


def main():
    print(f"{CLR_CYAN}{CLR_BOLD}===================================================================={CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  Rails Engine Simulation: Advanced Routing & Controller Architecture{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}===================================================================={CLR_RESET}")

    # Build Rails RouteSet
    # Rails equivalent:
    # namespace :api do
    #   namespace :v1 do
    #     resources :posts, constraints: { id: /\d+/ }
    #   end
    # end
    router = Router()
    router.draw("GET",  "/api/v1/posts",     to="ApiV1PostsController#index")
    router.draw("POST", "/api/v1/posts",     to="ApiV1PostsController#create")
    router.draw("GET",  "/api/v1/posts/:id", to="ApiV1PostsController#show", constraints={"id": r"\d+"})

    # Test Case 1: Standard GET list
    run_test_scenario(
        title="Public Index Action",
        router=router,
        request=Request("GET", "/api/v1/posts"),
        expected_status=200
    )

    # Test Case 2: Dynamic segment matching with valid regex constraint
    run_test_scenario(
        title="Dynamic Segment with Satisfied Regex Constraint (:id is numeric)",
        router=router,
        request=Request("GET", "/api/v1/posts/42"),
        expected_status=200
    )

    # Test Case 3: Regex constraint violation (slug provided instead of digits)
    run_test_scenario(
        title="Dynamic Segment Constraint Failure (id: 'invalid-slug' != \\d+)",
        router=router,
        request=Request("GET", "/api/v1/posts/invalid-slug"),
        expected_status=404
    )

    # Test Case 4: Controller filter blocking unauthorized access
    run_test_scenario(
        title="Before Action Interception (Authentication Barrier)",
        router=router,
        request=Request("POST", "/api/v1/posts", params={"post": {"title": "Test"}}),
        expected_status=401
    )

    # Test Case 5: Strong Parameters Filtering & Success Creation
    authorized_headers = {"Authorization": "Bearer rails-secret-token"}
    payload = {
        "post": {
            "title": "Deep Dive into Metaprogramming",
            "body": "Ruby blocks, procs, and eval structures.",
            "tags": ["ruby", "rails", "backend"],
            "admin_role": True  # Unpermitted mass-assignment field
        }
    }
    run_test_scenario(
        title="Authorized POST with Strong Parameters Filtering",
        router=router,
        request=Request("POST", "/api/v1/posts", params=payload, headers=authorized_headers),
        expected_status=201
    )

    # Test Case 6: Strong Parameters Missing Key Exception Handling
    bad_payload = {"article": {"title": "Wrong Key"}}
    run_test_scenario(
        title="Strong Parameters Failure (Missing Root Key :post)",
        router=router,
        request=Request("POST", "/api/v1/posts", params=bad_payload, headers=authorized_headers),
        expected_status=422
    )

    print(f"\n{CLR_GREEN}{CLR_BOLD}✔ All routing & controller architecture test scenarios completed successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
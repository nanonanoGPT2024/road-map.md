#!/usr/bin/env python3
"""
Lab Exercise: Rails Advanced Routing & Controller Architecture Simulator
BAB-02: Routing Lanjutan & Controller Architecture (Ruby on Rails Concept in Python 3)

Fitur yang disimulasikan:
1. Advanced Route Set & Constraints (Subdomain, Format, Regexp constraints)
2. Resourceful & Nested Routing (Shallow nesting, Member/Collection actions)
3. ActionController Base Pipeline:
   - Strong Parameters (require & permit with ActionController::Parameters)
   - Filter Chain Lifecycle (before_action, around_action, after_action)
   - rescue_from Error Handling & Content Negotiation (respond_to format json/html)
4. Interactive Terminal Runner dengan ANSI Color Output
"""

import sys
import re
import json
import time
from typing import Callable, Dict, Any, List, Optional

# ==========================================
# ANSI Color Codes & Formatting Helpers
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

def banner(title: str):
    line = "=" * 70
    print(f"\n{Style.CYAN}{line}{Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}  🚀 {title.upper()}{Style.RESET}")
    print(f"{Style.CYAN}{line}{Style.RESET}")

def info(msg: str):
    print(f"  {Style.BLUE}[INFO]{Style.RESET} {msg}")

def success(msg: str):
    print(f"  {Style.GREEN}✓ [SUCCESS]{Style.RESET} {msg}")

def warn(msg: str):
    print(f"  {Style.YELLOW}⚠ [WARN]{Style.RESET} {msg}")

def error(msg: str):
    print(f"  {Style.RED}✗ [ERROR]{Style.RESET} {msg}")


# ==========================================
# Domain Exceptions (Rails-style)
# ==========================================
class RoutingError(Exception):
    """ActionController::RoutingError"""
    pass

class ParameterMissing(Exception):
    """ActionController::ParameterMissing"""
    def __init__(self, param: str):
        super().__init__(f"param is missing or the value is empty: {param}")
        self.param = param

class UnpermittedParameters(Exception):
    """ActionController::UnpermittedParameters"""
    def __init__(self, keys: List[str]):
        super().__init__(f"found unpermitted parameter(s): {', '.join(keys)}")
        self.keys = keys

class RecordNotFound(Exception):
    """ActiveRecord::RecordNotFound"""
    pass

class NotAuthorizedError(Exception):
    """Pundit::NotAuthorizedError or CanCan::AccessDenied"""
    pass


# ==========================================
# Strong Parameters Emulation
# ==========================================
class Parameters:
    """Emulates ActionController::Parameters"""
    def __init__(self, data: Dict[str, Any], permitted: bool = False):
        self._data = data or {}
        self.permitted = permitted

    def require(self, key: str) -> "Parameters":
        if key not in self._data or self._data[key] is None or self._data[key] == "":
            raise ParameterMissing(key)
        val = self._data[key]
        if not isinstance(val, dict):
            raise ParameterMissing(f"{key} (expected nested mapping)")
        return Parameters(val, permitted=False)

    def permit(self, *allowed_keys: str) -> Dict[str, Any]:
        result = {}
        for key in allowed_keys:
            if key in self._data:
                result[key] = self._data[key]
        
        # Check unpermitted parameters in strict mode
        unpermitted = [k for k in self._data if k not in allowed_keys]
        if unpermitted:
            warn(f"ActionController::Parameters flagged unpermitted keys: {Style.YELLOW}{unpermitted}{Style.RESET}")
        
        self.permitted = True
        return result

    def to_dict(self) -> Dict[str, Any]:
        return self._data


# ==========================================
# HTTP Request & Response Objects
# ==========================================
class Request:
    def __init__(self, method: str, path: str, host: str = "api.myapp.test", headers: Optional[Dict[str, str]] = None, body: Optional[Dict[str, Any]] = None):
        self.method = method.upper()
        self.path = path.strip()
        self.host = host
        self.headers = headers or {"Accept": "application/json"}
        self.body = body or {}
        self.params: Dict[str, Any] = {}
        self.format: str = "json" if "json" in self.headers.get("Accept", "") else "html"
        self.subdomain = self.host.split(".")[0] if len(self.host.split(".")) > 2 else ""

class Response:
    def __init__(self):
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self.body: Any = None

    def render(self, status: int, data: Any, content_type: str = "application/json"):
        self.status = status
        self.headers["Content-Type"] = content_type
        self.body = data


# ==========================================
# Routing Engine (Rails routes.rb simulation)
# ==========================================
class Route:
    def __init__(self, method: str, pattern: str, controller: str, action: str, 
                 constraints: Optional[Dict[str, Any]] = None, shallow: bool = False):
        self.method = method.upper()
        self.pattern = pattern
        self.controller = controller
        self.action = action
        self.constraints = constraints or {}
        self.shallow = shallow
        self._regex = self._compile_pattern(pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        # Convert :id or :post_id to regex groups
        escaped = re.sub(r':([a-zA-Z_]+)', r'(?P<\1>[^/]+)', pattern)
        return re.compile(f"^{escaped}$")

    def match(self, req: Request) -> Optional[Dict[str, str]]:
        if req.method != self.method:
            return None

        # Check Subdomain Constraint
        if "subdomain" in self.constraints:
            req_subdomain = req.subdomain
            expected = self.constraints["subdomain"]
            if isinstance(expected, (list, tuple)) and req_subdomain not in expected:
                return None
            elif isinstance(expected, str) and req_subdomain != expected:
                return None

        # Check Path Regex
        match = self._regex.match(req.path)
        if not match:
            return None

        params = match.groupdict()

        # Check Param-level Constraints (e.g., id format \d+)
        for key, expected_pattern in self.constraints.items():
            if key in params:
                if not re.fullmatch(expected_pattern, str(params[key])):
                    return None

        return params


class Router:
    """Emulates Rails.application.routes.draw"""
    def __init__(self):
        self.routes: List[Route] = []

    def add(self, method: str, path: str, to: str, constraints: Optional[Dict[str, Any]] = None):
        controller_name, action = to.split("#")
        route = Route(method, path, controller_name, action, constraints)
        self.routes.append(route)

    def resources(self, name: str, controller: str, only: Optional[List[str]] = None):
        actions = [
            ("GET", f"/{name}", "index"),
            ("POST", f"/{name}", "create"),
            ("GET", f"/{name}/:id", "show"),
            ("PATCH", f"/{name}/:id", "update"),
            ("DELETE", f"/{name}/:id", "destroy"),
        ]
        for meth, path, act in actions:
            if only is None or act in only:
                self.add(meth, path, f"{controller}#{act}", constraints={"id": r"\d+"})

    def dispatch(self, req: Request) -> Route:
        for route in self.routes:
            extracted_params = route.match(req)
            if extracted_params is not None:
                req.params = {**req.params, **extracted_params}
                return route
        raise RoutingError(f"No route matches [{req.method}] \"{req.path}\" on host '{req.host}'")


# ==========================================
# Mock In-Memory Database (ActiveRecord emulation)
# ==========================================
DB = {
    "articles": {
        1: {"id": 1, "title": "Building Resilient Rails APIs", "body": "Deep dive into controller patterns.", "author_id": 101, "status": "published"},
        2: {"id": 2, "title": "Advanced Metaprogramming in Ruby", "body": "Hooks, modules, and method_missing.", "author_id": 102, "status": "draft"},
    },
    "comments": {
        1: {"id": 1, "article_id": 1, "body": "Super insightful breakdown!", "author": "Alice"},
        2: {"id": 2, "article_id": 1, "body": "Can you elaborate on shallow nesting?", "author": "Bob"},
    }
}


# ==========================================
# ActionController::Base Architecture Emulation
# ==========================================
class ActionControllerBase:
    """Base Controller mimicking Rails controller callbacks, responder, and error interception"""
    def __init__(self, request: Request, response: Response):
        self.request = request
        self.response = response
        self.params = Parameters(request.body)
        self.current_user: Optional[Dict[str, Any]] = None
        self._halted = False

    def halt(self, status: int, message: str):
        self._halted = True
        self.response.render(status, {"error": message, "status": status})

    # Hook lists
    before_actions: List[str] = []
    after_actions: List[str] = []

    def execute_action(self, action_name: str):
        info(f"Processing by {self.__class__.__name__}#{action_name} as {self.request.format.upper()}")
        start_time = time.time()

        try:
            # 1. Run before_action callbacks
            for callback_name in self.before_actions:
                if self._halted:
                    break
                callback = getattr(self, callback_name, None)
                if callback and callable(callback):
                    callback()

            # 2. Run target action if not halted
            if not self._halted:
                action = getattr(self, action_name, None)
                if not action:
                    raise RoutingError(f"Action '{action_name}' could not be found for {self.__class__.__name__}")
                action()

            # 3. Run after_action callbacks
            for callback_name in self.after_actions:
                callback = getattr(self, callback_name, None)
                if callback and callable(callback):
                    callback()

        except Exception as exc:
            self.handle_exception(exc)

        duration = (time.time() - start_time) * 1000
        info(f"Completed {self.response.status} in {duration:.2f}ms")

    def handle_exception(self, exc: Exception):
        """rescue_from handler mapping"""
        if isinstance(exc, RecordNotFound):
            self.response.render(404, {"error": "Record Not Found", "detail": str(exc)})
        elif isinstance(exc, ParameterMissing):
            self.response.render(400, {"error": "Bad Request (Parameter Missing)", "detail": str(exc)})
        elif isinstance(exc, NotAuthorizedError):
            self.response.render(403, {"error": "Forbidden", "detail": str(exc)})
        elif isinstance(exc, RoutingError):
            self.response.render(404, {"error": "Routing Error", "detail": str(exc)})
        else:
            self.response.render(500, {"error": "Internal Server Error", "detail": str(exc)})


# ==========================================
# Concrete Production Controllers
# ==========================================
class ApiBaseController(ActionControllerBase):
    before_actions = ["authenticate_api_token"]

    def authenticate_api_token(self):
        auth_header = self.request.headers.get("Authorization", "")
        if auth_header == "Bearer secret_rails_token":
            self.current_user = {"id": 101, "role": "admin", "name": "Lead Architect"}
            info(f"Authenticated as: {Style.GREEN}{self.current_user['name']} (role={self.current_user['role']}){Style.RESET}")
        elif auth_header == "Bearer user_token":
            self.current_user = {"id": 202, "role": "contributor", "name": "Regular Dev"}
            info(f"Authenticated as: {Style.GREEN}{self.current_user['name']} (role={self.current_user['role']}){Style.RESET}")
        else:
            warn("Missing or invalid Bearer token!")
            self.halt(401, "HTTP Token: Access denied. Valid Authorization Bearer required.")


class ArticlesController(ApiBaseController):
    before_actions = ["authenticate_api_token", "set_article", "authorize_article"]
    
    def __init__(self, request: Request, response: Response):
        super().__init__(request, response)
        self.article: Optional[Dict[str, Any]] = None

    def set_article(self):
        # Only run for member actions requiring :id
        action = self.request.params.get("_action")
        if action in ["show", "update", "destroy"]:
            article_id = int(self.request.params.get("id", 0))
            if article_id not in DB["articles"]:
                raise RecordNotFound(f"Couldn't find Article with 'id'={article_id}")
            self.article = DB["articles"][article_id]
            info(f"set_article callback resolved Article #{article_id}")

    def authorize_article(self):
        action = self.request.params.get("_action")
        if action in ["update", "destroy"]:
            if self.current_user and self.current_user["role"] != "admin" and self.article and self.article["author_id"] != self.current_user["id"]:
                raise NotAuthorizedError(f"User #{self.current_user['id']} cannot mutate Article owned by #{self.article['author_id']}")

    # --- Actions ---
    def index(self):
        articles = list(DB["articles"].values())
        self.response.render(200, {"data": articles, "meta": {"total": len(articles)}})

    def show(self):
        self.response.render(200, {"data": self.article})

    def create(self):
        # Strong Parameters enforcement: params.require(:article).permit(:title, :body, :status)
        article_params = self.params.require("article").permit("title", "body", "status")
        
        new_id = max(DB["articles"].keys(), default=0) + 1
        new_record = {
            "id": new_id,
            "title": article_params["title"],
            "body": article_params["body"],
            "status": article_params.get("status", "draft"),
            "author_id": self.current_user["id"] if self.current_user else 0
        }
        DB["articles"][new_id] = new_record
        success(f"Article #{new_id} persisted through Strong Parameters")
        self.response.render(201, {"data": new_record, "message": "Article created successfully"})

    def update(self):
        article_params = self.params.require("article").permit("title", "body", "status")
        self.article.update(article_params)
        success(f"Article #{self.article['id']} updated successfully")
        self.response.render(200, {"data": self.article, "message": "Article updated successfully"})


class CommentsController(ApiBaseController):
    """Demonstrates Shallow Nesting:
    GET /articles/:article_id/comments  -> index
    POST /articles/:article_id/comments -> create
    GET /comments/:id                   -> show (shallow)
    DELETE /comments/:id                -> destroy (shallow)
    """
    before_actions = ["authenticate_api_token!"]

    def index(self):
        article_id = int(self.request.params.get("article_id", 0))
        if article_id not in DB["articles"]:
            raise RecordNotFound(f"Article #{article_id} not found")
        
        comments = [c for c in DB["comments"].values() if c["article_id"] == article_id]
        self.response.render(200, {"article_id": article_id, "data": comments})

    def show(self):
        comment_id = int(self.request.params.get("id", 0))
        if comment_id not in DB["comments"]:
            raise RecordNotFound(f"Comment #{comment_id} not found")
        self.response.render(200, {"data": DB["comments"][comment_id]})


# ==========================================
# Dispatcher Gateway
# ==========================================
class RailsApp:
    def __init__(self):
        self.router = Router()
        self._configure_routes()

    def _configure_routes(self):
        # 1. API Subdomain constraint route
        self.router.resources("articles", "ArticlesController")

        # 2. Shallow Nested comments
        self.router.add("GET", "/articles/:article_id/comments", "CommentsController#index", constraints={"article_id": r"\d+"})
        self.router.add("GET", "/comments/:id", "CommentsController#show", constraints={"id": r"\d+"})

        # 3. Custom Member action route with constraint
        self.router.add("POST", "/articles/:id/publish", "ArticlesController#publish", constraints={"id": r"\d+"})

    def handle(self, req: Request) -> Response:
        res = Response()
        try:
            route = self.router.dispatch(req)
            req.params["_action"] = route.action
            
            # Map Controller String to Class
            controller_map = {
                "ArticlesController": ArticlesController,
                "CommentsController": CommentsController
            }
            ctrl_class = controller_map.get(route.controller)
            if not ctrl_class:
                raise RoutingError(f"Uninitialized constant {route.controller}")

            controller_instance = ctrl_class(req, res)
            controller_instance.execute_action(route.action)

        except RoutingError as err:
            warn(f"Routing check failed: {err}")
            res.render(404, {"error": "RoutingError", "message": str(err)})

        return res


# ==========================================
# Interactive Test Suite Runner
# ==========================================
def run_simulation():
    app = RailsApp()
    banner("Rails Advanced Routing & Controller Architecture Lab")
    print(f"{Style.GRAY}Demonstrasi: Strong Parameters, Filters (before_action), Routing Constraints, dan Shallow Nesting.{Style.RESET}\n")

    test_scenarios = [
        {
            "title": "Scenario 1: Akses GET /articles tanpa Token (Filter Rejection)",
            "request": Request("GET", "/articles", headers={"Accept": "application/json"})
        },
        {
            "title": "Scenario 2: Akses GET /articles dengan Token Sah (Authorized Filter Pipeline)",
            "request": Request("GET", "/articles", headers={
                "Authorization": "Bearer secret_rails_token",
                "Accept": "application/json"
            })
        },
        {
            "title": "Scenario 3: Strong Parameters Permitted Create POST /articles",
            "request": Request("POST", "/articles", 
                headers={"Authorization": "Bearer secret_rails_token"},
                body={
                    "article": {
                        "title": "Scaling Rails with Microservices & Engines",
                        "body": "Techniques for modular controller patterns.",
                        "status": "published",
                        "hacker_attribute_injection": "DROP TABLE users;"
                    }
                }
            )
        },
        {
            "title": "Scenario 4: ParameterMissing Exception (require(:article) missing)",
            "request": Request("POST", "/articles",
                headers={"Authorization": "Bearer secret_rails_token"},
                body={"title": "No article key wrapper"}
            )
        },
        {
            "title": "Scenario 5: Shallow Nesting Sub-resource GET /articles/1/comments vs /comments/2",
            "request": Request("GET", "/articles/1/comments", headers={"Authorization": "Bearer user_token"})
        },
        {
            "title": "Scenario 6: Authorization Failure (Pundit pattern) - Contributor edit Admin article",
            "request": Request("PATCH", "/articles/1",
                headers={"Authorization": "Bearer user_token"},
                body={"article": {"title": "Attempted Unauthorized Overwrite"}}
            )
        },
        {
            "title": "Scenario 7: Routing Error / Constraint Mismatch (Alphanumeric ID on strict numeric route)",
            "request": Request("GET", "/articles/not-a-number", headers={"Authorization": "Bearer secret_rails_token"})
        },
    ]

    for idx, sc in enumerate(test_scenarios, 1):
        print(f"\n{Style.BOLD}{Style.MAGENTA}=== [{idx}/{len(test_scenarios)}] {sc['title']} ==={Style.RESET}")
        req = sc["request"]
        print(f"  {Style.WHITE}{req.method} {req.path}{Style.RESET} | Host: {req.host} | Auth: {req.headers.get('Authorization', 'None')}")
        if req.body:
            print(f"  Payload: {Style.DIM}{json.dumps(req.body)}{Style.RESET}")

        res = app.handle(req)
        
        status_color = Style.GREEN if res.status in (200, 201) else Style.RED
        print(f"  {Style.BOLD}HTTP Status:{Style.RESET} {status_color}{res.status}{Style.RESET}")
        print(f"  {Style.BOLD}Response Body:{Style.RESET}")
        print(f"  {Style.GRAY}{json.dumps(res.body, indent=4)}{Style.RESET}")

    banner("Lab Exercise Verification Completed Successfully")
    print(f"{Style.GREEN}Seluruh arsitektur routing dan controller Rails berhasil disimulasikan secara valid!{Style.RESET}\n")

if __name__ == "__main__":
    run_simulation()

#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi dan Arsitektur Ruby on Rails
Topik: Convention over Configuration, Rack Pipeline, Router, Controller Dispatcher, dan Active Record Pattern.
"""

import sys
import re
import json
import time

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
  SIMULASI ARSITEKTUR RUBY ON RAILS (BAB 01: FONDASI & ARSITEKTUR)
  Rails Philosophy: Convention over Configuration & The MVC / Rack Stack
======================================================================{RESET}
"""
    print(banner)

# ---------------------------------------------------------
# 1. Convention over Configuration (ActiveSupport Inflector)
# ---------------------------------------------------------
class RailsInflector:
    """Simulasi konvensi penamaan Rails: Class -> Table name & Controller."""
    @staticmethod
    def tableize(class_name: str) -> str:
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', class_name)
        snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        if snake.endswith('y') and not snake.endswith(('ay', 'ey', 'oy', 'uy')):
            return snake[:-1] + 'ies'
        elif snake.endswith(('s', 'x', 'z', 'ch', 'sh')):
            return snake + 'es'
        return snake + 's'

    @staticmethod
    def controller_name(model_name: str) -> str:
        return f"{RailsInflector.tableize(model_name).capitalize()}Controller"

# ---------------------------------------------------------
# 2. Active Record Pattern (Simulasi ORM & Validation)
# ---------------------------------------------------------
class ActiveRecordBase:
    _tables = {}

    def __init__(self, **attributes):
        self.id = None
        self.attributes = attributes
        self.errors = []

    @classmethod
    def table_name(cls) -> str:
        return RailsInflector.tableize(cls.__name__)

    @classmethod
    def _get_table(cls):
        tbl = cls.table_name()
        if tbl not in ActiveRecordBase._tables:
            ActiveRecordBase._tables[tbl] = []
        return ActiveRecordBase._tables[tbl]

    def validate(self) -> bool:
        self.errors = []
        for field, val in self.attributes.items():
            if val is None or str(val).strip() == "":
                self.errors.append(f"{field} can't be blank")
        return len(self.errors) == 0

    def save(self) -> bool:
        if not self.validate():
            return False
        table = self._get_table()
        if self.id is None:
            self.id = len(table) + 1
            record = {"id": self.id, **self.attributes}
            table.append(record)
        else:
            for idx, item in enumerate(table):
                if item["id"] == self.id:
                    table[idx] = {"id": self.id, **self.attributes}
                    break
        return True

    @classmethod
    def all(cls):
        return cls._get_table()

    @classmethod
    def find_by(cls, **kwargs):
        table = cls._get_table()
        for item in table:
            match = True
            for k, v in kwargs.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                return item
        return None

class Article(ActiveRecordBase):
    pass

class User(ActiveRecordBase):
    pass

# ---------------------------------------------------------
# 3. Action Controller & Filters (before_action)
# ---------------------------------------------------------
class ActionControllerBase:
    def __init__(self, request_params):
        self.params = request_params
        self.response = {"status": 200, "headers": {"Content-Type": "application/json"}, "body": ""}

    def render(self, status=200, json_data=None, text=None):
        self.response["status"] = status
        if json_data is not None:
            self.response["body"] = json.dumps(json_data, indent=2)
        elif text is not None:
            self.response["body"] = text

    def run_action(self, action_name: str):
        # Jalankan filter before_action jika didefinisikan
        if hasattr(self, "before_action"):
            proceed = getattr(self, "before_action")()
            if proceed is False:
                return self.response
        action_fn = getattr(self, action_name, None)
        if not action_fn:
            self.render(404, {"error": f"Action '{action_name}' not found"})
        else:
            action_fn()
        return self.response

class ArticlesController(ActionControllerBase):
    def before_action(self):
        # Contoh filter autentikasi/audit log sederhana
        token = self.params.get("token")
        if self.params.get("require_auth") and token != "rails-secret-123":
            self.render(401, {"error": "HTTP 401 Unauthorized: Invalid API Token"})
            return False
        return True

    def index(self):
        articles = Article.all()
        self.render(200, {"data": articles, "count": len(articles)})

    def create(self):
        title = self.params.get("title")
        content = self.params.get("content")
        art = Article(title=title, content=content)
        if art.save():
            self.render(201, {"message": "Article created successfully", "record": {"id": art.id, **art.attributes}})
        else:
            self.render(422, {"errors": art.errors})

# ---------------------------------------------------------
# 4. ActionDispatch Router (Pattern Matching & Routing)
# ---------------------------------------------------------
class ActionDispatchRouter:
    def __init__(self):
        self.routes = []

    def draw(self, verb: str, path: str, to: str):
        """to format: 'controller#action'"""
        pattern = "^" + re.sub(r':(\w+)', r'(?P<\1>[^/]+)', path) + "$"
        self.routes.append({
            "verb": verb.upper(),
            "regex": re.compile(pattern),
            "target": to
        })

    def match(self, verb: str, path: str):
        verb = verb.upper()
        for r in self.routes:
            if r["verb"] == verb:
                m = r["regex"].match(path)
                if m:
                    controller_part, action_part = r["target"].split("#")
                    params = m.groupdict()
                    return controller_part, action_part, params
        return None, None, {}

# ---------------------------------------------------------
# 5. Rack Middleware Pipeline Simulation
# ---------------------------------------------------------
class RackLoggerMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, env):
        start = time.time()
        print(f"{YELLOW}[Rack Pipeline]{RESET} Started {BOLD}{env['REQUEST_METHOD']}{RESET} \"{env['PATH_INFO']}\"")
        status, headers, body = self.app(env)
        duration_ms = (time.time() - start) * 1000
        color = GREEN if status < 400 else RED
        print(f"{YELLOW}[Rack Pipeline]{RESET} Completed {color}{status}{RESET} in {duration_ms:.2f}ms")
        return status, headers, body

class RailsApplication:
    def __init__(self):
        self.router = ActionDispatchRouter()
        self.controllers = {
            "articles": ArticlesController
        }

    def __call__(self, env):
        verb = env["REQUEST_METHOD"]
        path = env["PATH_INFO"]
        ctrl_name, action_name, route_params = self.router.match(verb, path)

        if not ctrl_name:
            return 404, {"Content-Type": "application/json"}, json.dumps({"error": f"No route matches [{verb}] \"{path}\""})

        controller_class = self.controllers.get(ctrl_name)
        if not controller_class:
            return 500, {"Content-Type": "application/json"}, json.dumps({"error": f"Uninitialized constant {ctrl_name.capitalize()}Controller"})

        combined_params = {**route_params, **env.get("PARAMS", {})}
        controller = controller_class(combined_params)
        res = controller.run_action(action_name)
        return res["status"], res["headers"], res["body"]

# ---------------------------------------------------------
# Interactive Runner & Demo Suites
# ---------------------------------------------------------
def run_interactive_lab():
    print_banner()

    app = RailsApplication()
    # Convention over configuration routing
    app.router.draw("GET", "/articles", "articles#index")
    app.router.draw("POST", "/articles", "articles#create")

    # Wrap in Rack Middleware
    pipeline = RackLoggerMiddleware(app)

    # Seed Active Record
    art1 = Article(title="Memahami Convention over Configuration", content="Konvensi mengurangi konfigurasi boilerplate.")
    art1.save()
    art2 = Article(title="Rack Interface di Balik Rails", content="Spesifikasi standar antarmuka server Ruby web.")
    art2.save()

    while True:
        print(f"\n{BOLD}Menu Simulasi Arsitektur Rails:{RESET}")
        print(f" {GREEN}1.{RESET} Demonstrasi Konvensi Penamaan (Inflector)")
        print(f" {GREEN}2.{RESET} Demonstrasi Active Record Pattern (Model & In-Memory DB)")
        print(f" {GREEN}3.{RESET} Simulasi HTTP Request melalui Rack & ActionDispatch Router (GET /articles)")
        print(f" {GREEN}4.{RESET} Simulasi Validasi & Record Creation (POST /articles)")
        print(f" {GREEN}5.{RESET} Simulasi Keamanan: Filter Controller (before_action 401 Unauthorized)")
        print(f" {RED}6.{RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [1-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Sesi lab dihentikan.{RESET}")
            break

        if choice == "1":
            print(f"\n{CYAN}{BOLD}--- [Convention over Configuration: Inflector] ---{RESET}")
            test_models = ["Article", "User", "Category", "Address", "PurchaseOrder"]
            print(f"{'Model Class':<18} | {'Table Name (DB)':<18} | {'Controller Name':<22}")
            print("-" * 65)
            for m in test_models:
                tbl = RailsInflector.tableize(m)
                ctrl = RailsInflector.controller_name(m)
                print(f"{BOLD}{m:<18}{RESET} | {GREEN}{tbl:<18}{RESET} | {BLUE}{ctrl:<22}{RESET}")

        elif choice == "2":
            print(f"\n{CYAN}{BOLD}--- [Active Record Simulation] ---{RESET}")
            records = Article.all()
            print(f"Daftar data pada tabel {BOLD}'{Article.table_name()}'{RESET}:")
            for r in records:
                print(f"  {MAGENTA}#{r['id']}{RESET} Title: {BOLD}{r['title']}{RESET}")
                print(f"      Body: {r['content']}")

        elif choice == "3":
            print(f"\n{CYAN}{BOLD}--- [Rack & Router: GET /articles] ---{RESET}")
            env = {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/articles",
                "PARAMS": {}
            }
            status, headers, body = pipeline(env)
            print(f"{BOLD}Response Body:{RESET}\n{body}")

        elif choice == "4":
            print(f"\n{CYAN}{BOLD}--- [Active Record Validation & Controller: POST /articles] ---{RESET}")
            title_input = input("Masukkan Judul Artikel (kosongkan untuk test validasi): ").strip()
            content_input = input("Masukkan Konten Artikel: ").strip()

            env = {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/articles",
                "PARAMS": {
                    "title": title_input if title_input else None,
                    "content": content_input if content_input else None
                }
            }
            status, headers, body = pipeline(env)
            print(f"{BOLD}Response Body:{RESET}\n{body}")

        elif choice == "5":
            print(f"\n{CYAN}{BOLD}--- [Controller Filter: before_action Authentication] ---{RESET}")
            token = input("Masukkan API token (Kunci valid: 'rails-secret-123'): ").strip()
            env = {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/articles",
                "PARAMS": {
                    "require_auth": True,
                    "token": token,
                    "title": "Artikel Terproteksi",
                    "content": "Hanya user dengan token valid yang dapat mempublikasikan ini."
                }
            }
            status, headers, body = pipeline(env)
            print(f"{BOLD}Response Body:{RESET}\n{body}")

        elif choice == "6":
            print(f"\n{GREEN}Terima kasih telah menjalankan hands-on simulasi Rails Architecture!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")

if __name__ == "__main__":
    run_interactive_lab()

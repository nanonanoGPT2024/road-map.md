#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur & Pipeline Django REST Framework (DRF)
BAB-07: RESTful API Engineering dengan Django REST Framework

Skrip ini mendemonstrasikan secara mandiri cara kerja internal:
1. Request & Response Lifecycle
2. Serializer Serialization & Validation (field-level + object-level)
3. Authentication & Permission Classes
4. ViewSet Dispatcher & Router Mechanics
"""

import sys
import json
import time
from typing import Dict, Any, List, Optional, Tuple

# ANSI Escape Codes for Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"

def print_banner():
    banner = f"""
{C_CYAN}{C_BOLD}======================================================================
  DJANGO REST FRAMEWORK (DRF) - CORE ENGINE & PIPELINE SIMULATION
  Bab 07: RESTful API Engineering - Modul 01 Hands-on Lab
======================================================================{C_RESET}
"""
    print(banner)

# --- SIMULASI MODEL DATA ---
class ArticleModel:
    _storage: List[Dict[str, Any]] = [
        {"id": 1, "title": "Memahami Django ORM", "content": "QuerySet dieksekusi secara lazy.", "author": "admin", "is_published": True},
        {"id": 2, "title": "Arsitektur Serializer DRF", "content": "Serializer menjembatani JSON dan Python native.", "author": "dev_user", "is_published": True},
        {"id": 3, "title": "Draft API Security", "content": "Membahas Token vs JWT authentication.", "author": "guest_contributor", "is_published": False},
    ]
    _auto_id = 4

    @classmethod
    def all(cls) -> List[Dict[str, Any]]:
        return [dict(item) for item in cls._storage]

    @classmethod
    def get(cls, pk: int) -> Optional[Dict[str, Any]]:
        for item in cls._storage:
            if item["id"] == pk:
                return dict(item)
        return None

    @classmethod
    def create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(data)
        record["id"] = cls._auto_id
        cls._auto_id += 1
        cls._storage.append(record)
        return dict(record)

# --- SIMULASI SERIALIZER DRF ---
class ValidationError(Exception):
    def __init__(self, detail: Dict[str, List[str]]):
        super().__init__(detail)
        self.detail = detail

class ArticleSerializer:
    def __init__(self, instance: Optional[Any] = None, data: Optional[Dict[str, Any]] = None):
        self.instance = instance
        self.initial_data = data
        self._validated_data: Dict[str, Any] = {}
        self._errors: Dict[str, List[str]] = {}

    def validate_title(self, value: str) -> str:
        """Field-level validator: validate_<field_name>"""
        if len(value.strip()) < 5:
            raise ValueError("Judul artikel minimal harus terdiri dari 5 karakter.")
        return value.strip()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Object-level validator: cross-field check"""
        title = attrs.get("title", "")
        content = attrs.get("content", "")
        if title.lower() in content.lower() and len(content) < 15:
            raise ValueError("Konten terlalu pendek dan redundan dengan judul.")
        return attrs

    def is_valid(self, raise_exception: bool = False) -> bool:
        self._errors = {}
        cleaned_data: Dict[str, Any] = {}

        if not self.initial_data or not isinstance(self.initial_data, dict):
            self._errors["non_field_errors"] = ["Payload data harus berupa JSON object."]
            if raise_exception:
                raise ValidationError(self._errors)
            return False

        # Wajib ada: title & content
        for required_field in ["title", "content"]:
            if required_field not in self.initial_data:
                self._errors.setdefault(required_field, []).append("Field ini wajib diisi.")

        if self._errors:
            if raise_exception:
                raise ValidationError(self._errors)
            return False

        # Run field validators
        for field, value in self.initial_data.items():
            if field == "title":
                try:
                    cleaned_data[field] = self.validate_title(value)
                except ValueError as err:
                    self._errors.setdefault(field, []).append(str(err))
            else:
                cleaned_data[field] = value

        # Run object-level validator
        if not self._errors:
            try:
                cleaned_data = self.validate(cleaned_data)
            except ValueError as err:
                self._errors.setdefault("non_field_errors", []).append(str(err))

        if self._errors:
            if raise_exception:
                raise ValidationError(self._errors)
            return False

        self._validated_data = cleaned_data
        return True

    @property
    def validated_data(self) -> Dict[str, Any]:
        return self._validated_data

    @property
    def errors(self) -> Dict[str, List[str]]:
        return self._errors

    @property
    def data(self) -> Any:
        """to_representation simulation"""
        if self.instance is not None:
            if isinstance(self.instance, list):
                return [dict(x) for x in self.instance]
            return dict(self.instance)
        return self._validated_data

    def save(self, **kwargs) -> Dict[str, Any]:
        payload = {**self._validated_data, **kwargs}
        if "is_published" not in payload:
            payload["is_published"] = False
        return ArticleModel.create(payload)

# --- SIMULASI AUTHENTICATION & PERMISSIONS ---
class User:
    def __init__(self, username: str, is_authenticated: bool, is_staff: bool = False):
        self.username = username
        self.is_authenticated = is_authenticated
        self.is_staff = is_staff

class IsAuthenticatedPermission:
    @staticmethod
    def has_permission(user: User) -> bool:
        return user.is_authenticated

class IsAdminOrReadOnlyPermission:
    @staticmethod
    def has_permission(user: User, method: str) -> bool:
        if method in ["GET", "HEAD", "OPTIONS"]:
            return True
        return user.is_authenticated and user.is_staff

# --- SIMULASI REQUEST, RESPONSE & APIVIEW ---
class Request:
    def __init__(self, method: str, path: str, user: User, data: Optional[Dict[str, Any]] = None):
        self.method = method.upper()
        self.path = path
        self.user = user
        self.data = data or {}

class Response:
    def __init__(self, data: Any, status: int = 200):
        self.data = data
        self.status = status

    def render(self) -> str:
        return json.dumps(self.data, indent=2, ensure_ascii=False)

class ArticleViewSetSimulation:
    def __init__(self):
        self.permission_classes = [IsAdminOrReadOnlyPermission]

    def check_permissions(self, request: Request) -> bool:
        for perm in self.permission_classes:
            if not perm.has_permission(request.user, request.method):
                return False
        return True

    def dispatch(self, request: Request, pk: Optional[int] = None) -> Response:
        print(f"{C_BLUE}[DRF Dispatcher]{C_RESET} Incoming {C_BOLD}{request.method} {request.path}{C_RESET} by {C_YELLOW}'{request.user.username}'{C_RESET}")
        time.sleep(0.15)

        # 1. Permission check
        if not self.check_permissions(request):
            print(f"{C_RED}[Permission Denied]{C_RESET} 403 Forbidden - User lack required privileges.")
            return Response({"detail": "Anda tidak memiliki izin untuk melakukan aksi ini."}, status=403)

        # 2. Routing ke action method
        if request.method == "GET":
            if pk is not None:
                item = ArticleModel.get(pk)
                if not item:
                    return Response({"detail": "Not found."}, status=404)
                serializer = ArticleSerializer(instance=item)
                return Response(serializer.data, status=200)
            else:
                articles = ArticleModel.all()
                serializer = ArticleSerializer(instance=articles)
                return Response(serializer.data, status=200)

        elif request.method == "POST":
            serializer = ArticleSerializer(data=request.data)
            if serializer.is_valid():
                obj = serializer.save(author=request.user.username)
                print(f"{C_GREEN}[Database Created]{C_RESET} ID {obj['id']} persisted.")
                return Response(ArticleSerializer(instance=obj).data, status=201)
            else:
                print(f"{C_RED}[Validation Error]{C_RESET} Input data invalid.")
                return Response(serializer.errors, status=400)

        return Response({"detail": f"Method {request.method} not allowed."}, status=405)

# --- INTERACTIVE WORKFLOW RUNNER ---
def print_status_code(code: int):
    color = C_GREEN if code < 300 else (C_YELLOW if code < 400 else C_RED)
    return f"{color}{C_BOLD}HTTP {code}{C_RESET}"

def run_interactive_pipeline():
    print_banner()
    api = ArticleViewSetSimulation()

    current_user = User(username="anon", is_authenticated=False, is_staff=False)

    while True:
        print(f"\n{C_MAGENTA}--- MENU SIMULASI DRF ---{C_RESET}")
        print(f"Status Sesi User: {C_BOLD}{current_user.username}{C_RESET} (Auth: {current_user.is_authenticated}, Staff: {current_user.is_staff})")
        print("1. [GET /api/v1/articles/] List Articles (Read Only)")
        print("2. [GET /api/v1/articles/{id}/] Retrieve Detail Article")
        print("3. [POST /api/v1/articles/] Test Serializer Validasi & Simpan (Valid Payload)")
        print("4. [POST /api/v1/articles/] Test Serializer Failure Handling (Invalid Payload)")
        print("5. Ubah Status Pengguna (Anonim / Authenticated Regular / Staff Admin)")
        print("6. Keluar")

        try:
            choice = input(f"\n{C_CYAN}Pilih opsi [1-6]: {C_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            req = Request("GET", "/api/v1/articles/", current_user)
            res = api.dispatch(req)
            print(f"Status: {print_status_code(res.status)}")
            print(f"Payload Response:\n{C_RESET}{res.render()}")

        elif choice == "2":
            try:
                pk_val = int(input(f"Masukkan ID Artikel (contoh: 1 atau 99): ").strip())
            except ValueError:
                print(f"{C_RED}ID harus berupa angka integer.{C_RESET}")
                continue
            req = Request("GET", f"/api/v1/articles/{pk_val}/", current_user)
            res = api.dispatch(req, pk=pk_val)
            print(f"Status: {print_status_code(res.status)}")
            print(f"Payload Response:\n{C_RESET}{res.render()}")

        elif choice == "3":
            print(f"\n{C_YELLOW}Mempersiapkan POST Request dengan data valid...{C_RESET}")
            payload = {
                "title": "Django REST Framework ViewSet",
                "content": "Router secara otomatis memetakan aksi viewset ke endpoint RESTful standar."
            }
            print("Payload dikirim:\n" + json.dumps(payload, indent=2))
            req = Request("POST", "/api/v1/articles/", current_user, data=payload)
            res = api.dispatch(req)
            print(f"Status: {print_status_code(res.status)}")
            print(f"Response Body:\n{res.render()}")

        elif choice == "4":
            print(f"\n{C_YELLOW}Mempersiapkan POST Request dengan data melanggar validasi serializer...{C_RESET}")
            payload = {
                "title": "API",  # Melanggar aturan min 5 karakter
                "content": "Short"
            }
            print("Payload dikirim (Invalid title length):\n" + json.dumps(payload, indent=2))
            req = Request("POST", "/api/v1/articles/", current_user, data=payload)
            res = api.dispatch(req)
            print(f"Status: {print_status_code(res.status)}")
            print(f"Response Body:\n{res.render()}")

        elif choice == "5":
            print("\nPilih identitas:")
            print("a. Anonymous (Unauthenticated)")
            print("b. Normal User (Authenticated, Non-Staff)")
            print("c. Admin Staff (Authenticated, Is-Staff)")
            sub_choice = input("Pilihan [a/b/c]: ").strip().lower()
            if sub_choice == "a":
                current_user = User("anon", is_authenticated=False, is_staff=False)
            elif sub_choice == "b":
                current_user = User("john_doe", is_authenticated=True, is_staff=False)
            elif sub_choice == "c":
                current_user = User("super_admin", is_authenticated=True, is_staff=True)
            print(f"{C_GREEN}User berhasil diubah menjadi: {current_user.username}{C_RESET}")

        elif choice == "6":
            print(f"{C_GREEN}Terima kasih telah menjalankan simulasi Django REST Framework lab.{C_RESET}")
            break
        else:
            print(f"{C_RED}Pilihan tidak valid.{C_RESET}")

if __name__ == "__main__":
    run_interactive_pipeline()

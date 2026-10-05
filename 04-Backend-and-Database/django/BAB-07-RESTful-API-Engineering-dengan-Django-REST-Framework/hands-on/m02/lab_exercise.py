#!/usr/bin/env python3
"""
================================================================================
LAB EXERCISE M02: ADVANCED RESTFUL API ENGINEERING DENGAN DJANGO REST FRAMEWORK
Simulasi Komprehensif Arsitektur Produksi DRF (Standalone Python 3 Engine)
================================================================================
Topik yang Disimulasikan:
1. DRF Request-Response Lifecycle & APIView / ViewSet Dispatcher
2. Declarative Serializers & Nested Model Serializers dengan Cross-Field Validation
3. Pluggable Permission Classes (RBAC: IsAuthenticated, IsAdminUser, IsOwnerOrReadOnly)
4. Dynamic Sliding-Window Throttling (Rate Limiter: Burst & Sustained)
5. Custom Unified Exception Handler & RFC 7807 Error Envelope Standard
6. Query Optimization & Filter Backend Simulation
================================================================================
"""

import sys
import time
import json
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

# ==============================================================================
# ANSI Terminal Color Definitions
# ==============================================================================
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM       = '\033[2m'
    RESET     = '\033[0m'

CHECK = f"{Colors.GREEN}✓{Colors.RESET}"
CROSS = f"{Colors.RED}✗{Colors.RESET}"
ARROW = f"{Colors.CYAN}➔{Colors.RESET}"

# ==============================================================================
# Model Entities & In-Memory Storage
# ==============================================================================
@dataclass
class User:
    id: int
    username: str
    role: str  # 'admin', 'staff', 'customer'
    is_active: bool = True

@dataclass
class Product:
    id: int
    sku: str
    name: str
    price: float
    stock: int
    category: str
    owner_id: int

@dataclass
class OrderItem:
    product_id: int
    quantity: int
    unit_price: float

@dataclass
class Order:
    id: str
    customer_id: int
    items: List[OrderItem]
    total_amount: float
    status: str  # 'PENDING', 'PAID', 'CANCELLED'
    created_at: float = field(default_factory=time.time)

# Database State
DB = {
    "users": {
        1: User(1, "admin_user", "admin"),
        2: User(2, "engineer_staff", "staff"),
        3: User(3, "budi_santoso", "customer"),
        4: User(4, "citra_lestari", "customer"),
    },
    "products": {
        101: Product(101, "SKU-K8S-01", "Cloud Container Pod", 250000.0, 15, "Cloud", 2),
        102: Product(102, "SKU-DB-02", "PostgreSQL HA Cluster", 750000.0, 5, "Database", 2),
        103: Product(103, "SKU-REDIS-03", "Redis In-Memory Cache", 120000.0, 20, "Cache", 2),
    },
    "orders": {}
}

# ==============================================================================
# Exceptions & RFC 7807 Error Envelope
# ==============================================================================
class APIException(Exception):
    status_code = 500
    default_code = "error"
    default_detail = "A server error occurred."

    def __init__(self, detail: Any = None, code: Optional[str] = None):
        self.detail = detail or self.default_detail
        self.code = code or self.default_code

class AuthenticationFailed(APIException):
    status_code = 401
    default_code = "authentication_failed"
    default_detail = "Kredensial autentikasi tidak valid atau expired."

class PermissionDenied(APIException):
    status_code = 403
    default_code = "permission_denied"
    default_detail = "Anda tidak memiliki izin (permission) untuk mengakses resource ini."

class NotFound(APIException):
    status_code = 404
    default_code = "not_found"
    default_detail = "Resource target tidak ditemukan di sistem."

class ValidationError(APIException):
    status_code = 400
    default_code = "validation_error"
    default_detail = "Data input tidak memenuhi validasi skema serializer."

class Throttled(APIException):
    status_code = 429
    default_code = "throttled"

    def __init__(self, wait_seconds: int):
        super().__init__(
            detail=f"Batas laju request terlampaui. Harap tunggu {wait_seconds} detik.",
            code=self.default_code
        )
        self.wait_seconds = wait_seconds

def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """DRF Global Custom Exception Handler - RFC 7807 Problem Details Standard"""
    if isinstance(exc, APIException):
        response_data = {
            "type": f"https://api.internal.net/errors/{exc.code}",
            "status": exc.status_code,
            "error_code": exc.code.upper(),
            "detail": exc.detail,
            "instance": f"/api/v1/request/{uuid.uuid4().hex[:8]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "context": {
                "view": context.get("view", "UnknownView"),
                "action": context.get("action", "unknown")
            }
        }
        return {"status_code": exc.status_code, "data": response_data}
    
    # Unhandled 500
    return {
        "status_code": 500,
        "data": {
            "type": "https://api.internal.net/errors/internal_error",
            "status": 500,
            "error_code": "INTERNAL_SERVER_ERROR",
            "detail": str(exc),
            "instance": f"/api/v1/request/{uuid.uuid4().hex[:8]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    }

# ==============================================================================
# Security & Permissions (RBAC)
# ==============================================================================
class BasePermission:
    def has_permission(self, request, view) -> bool:
        return True

    def has_object_permission(self, request, view, obj) -> bool:
        return True

class IsAuthenticated(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_active)

class IsAdminUser(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.role == "admin")

class IsOwnerOrReadOnly(BasePermission):
    """
    Izin kustom: Pembacaan diizinkan untuk siapapun yang terotentikasi,
    tetapi modifikasi (PUT, PATCH, DELETE) hanya untuk pemilik objek atau admin.
    """
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True
        if not request.user:
            return False
        if request.user.role == "admin":
            return True
        return hasattr(obj, "owner_id") and obj.owner_id == request.user.id

# ==============================================================================
# Throttling Engine (Sliding Window Algorithm)
# ==============================================================================
class SimpleRateThrottle:
    def __init__(self, rate: str):
        # Format: "5/min", "10/sec"
        num, period = rate.split('/')
        self.num_requests = int(num)
        self.duration = 60 if period.startswith("min") else 1
        self.history: Dict[str, List[float]] = {}

    def get_ident(self, request) -> str:
        if request.user:
            return f"user_{request.user.id}"
        return f"ip_{request.client_ip}"

    def allow_request(self, request) -> Tuple[bool, Optional[int]]:
        key = self.get_ident(request)
        now = time.time()
        
        if key not in self.history:
            self.history[key] = []
        
        # Hapus timestamp di luar window
        self.history[key] = [ts for ts in self.history[key] if now - ts < self.duration]
        
        if len(self.history[key]) >= self.num_requests:
            oldest = self.history[key][0]
            remaining = int(self.duration - (now - oldest)) + 1
            return False, max(1, remaining)
            
        self.history[key].append(now)
        return True, None

# ==============================================================================
# Serializers
# ==============================================================================
class ProductSerializer:
    def __init__(self, instance=None, data=None):
        self.instance = instance
        self.data = data
        self.validated_data = {}
        self.errors = {}

    def is_valid(self) -> bool:
        if not self.data:
            self.errors["non_field_errors"] = ["Payload kosong."]
            return False
            
        name = self.data.get("name")
        price = self.data.get("price")
        stock = self.data.get("stock")
        category = self.data.get("category", "General")

        if not name or len(name) < 3:
            self.errors["name"] = ["Nama produk minimal 3 karakter."]
        if price is None or price <= 0:
            self.errors["price"] = ["Harga harus berupa angka positif lebih dari nol."]
        if stock is None or stock < 0:
            self.errors["stock"] = ["Stok tidak boleh bernilai negatif."]

        if self.errors:
            return False

        self.validated_data = {
            "name": name,
            "price": float(price),
            "stock": int(stock),
            "category": category
        }
        return True

    def to_representation(self, instance: Product) -> Dict[str, Any]:
        return {
            "id": instance.id,
            "sku": instance.sku,
            "name": instance.name,
            "price": instance.price,
            "formatted_price": f"Rp {instance.price:,.2f}",
            "stock": instance.stock,
            "category": instance.category,
            "owner_id": instance.owner_id,
            "is_in_stock": instance.stock > 0
        }

class OrderCreateSerializer:
    """Nested Serializer untuk Transaksi Pembuatan Order"""
    def __init__(self, data=None, customer_id: int = None):
        self.data = data
        self.customer_id = customer_id
        self.validated_data = {}
        self.errors = {}

    def is_valid(self) -> bool:
        items_data = self.data.get("items")
        if not items_data or not isinstance(items_data, list):
            self.errors["items"] = ["Field 'items' harus berupa array item order non-kosong."]
            return False

        validated_items = []
        total_calculated = 0.0

        for idx, item in enumerate(items_data):
            p_id = item.get("product_id")
            qty = item.get("quantity")

            if not p_id or p_id not in DB["products"]:
                self.errors[f"items[{idx}].product_id"] = [f"Produk ID {p_id} tidak valid."]
                continue

            product = DB["products"][p_id]
            if not qty or qty <= 0:
                self.errors[f"items[{idx}].quantity"] = ["Jumlah pesanan harus > 0."]
                continue

            if product.stock < qty:
                self.errors[f"items[{idx}].stock"] = [
                    f"Stok produk '{product.name}' tidak mencukupi (Tersedia: {product.stock}, Diminta: {qty})."
                ]
                continue

            line_total = product.price * qty
            total_calculated += line_total
            validated_items.append(OrderItem(product_id=p_id, quantity=qty, unit_price=product.price))

        if self.errors:
            return False

        self.validated_data = {
            "customer_id": self.customer_id,
            "items": validated_items,
            "total_amount": total_calculated
        }
        return True

    def save(self) -> Order:
        # Atomic Transaction Simulation
        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        for item in self.validated_data["items"]:
            DB["products"][item.product_id].stock -= item.quantity

        order = Order(
            id=order_id,
            customer_id=self.validated_data["customer_id"],
            items=self.validated_data["items"],
            total_amount=self.validated_data["total_amount"],
            status="PAID"
        )
        DB["orders"][order.id] = order
        return order

# ==============================================================================
# HTTP Request & ViewSet Dispatcher Engine
# ==============================================================================
@dataclass
class APIRequest:
    method: str
    path: str
    user: Optional[User] = None
    data: Optional[Dict[str, Any]] = None
    query_params: Dict[str, str] = field(default_factory=dict)
    client_ip: str = "127.0.0.1"

class ProductViewSet:
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    throttle_classes = [SimpleRateThrottle(rate="5/min")]

    def __init__(self):
        self.action = "unknown"

    def initial(self, request: APIRequest, action: str):
        self.action = action
        # 1. Throttling Check
        for throttle in self.throttle_classes:
            allowed, wait = throttle.allow_request(request)
            if not allowed:
                raise Throttled(wait_seconds=wait)

        # 2. Permissions Check
        for perm_class in self.permission_classes:
            perm = perm_class()
            if not perm.has_permission(request, self):
                raise PermissionDenied()

    def check_object_permissions(self, request: APIRequest, obj: Any):
        for perm_class in self.permission_classes:
            perm = perm_class()
            if not perm.has_object_permission(request, self, obj):
                raise PermissionDenied()

    def list(self, request: APIRequest) -> Dict[str, Any]:
        self.initial(request, "list")
        products = list(DB["products"].values())

        # Filter backend simulation
        category = request.query_params.get("category")
        if category:
            products = [p for p in products if p.category.lower() == category.lower()]

        serializer = ProductSerializer()
        results = [serializer.to_representation(p) for p in products]
        return {
            "count": len(results),
            "next": None,
            "previous": None,
            "results": results
        }

    def update(self, request: APIRequest, pk: int) -> Dict[str, Any]:
        self.initial(request, "update")
        product = DB["products"].get(pk)
        if not product:
            raise NotFound(detail=f"Produk #{pk} tidak ditemukan.")

        self.check_object_permissions(request, product)

        serializer = ProductSerializer(instance=product, data=request.data)
        if not serializer.is_valid():
            raise ValidationError(detail=serializer.errors)

        # Update attributes
        for k, v in serializer.validated_data.items():
            setattr(product, k, v)

        return serializer.to_representation(product)

class OrderViewSet:
    permission_classes = [IsAuthenticated]
    throttle_classes = [SimpleRateThrottle(rate="10/min")]

    def initial(self, request: APIRequest, action: str):
        for throttle in self.throttle_classes:
            allowed, wait = throttle.allow_request(request)
            if not allowed:
                raise Throttled(wait_seconds=wait)
        for perm_class in self.permission_classes:
            if not perm_class().has_permission(request, self):
                raise PermissionDenied()

    def create(self, request: APIRequest) -> Dict[str, Any]:
        self.initial(request, "create")
        serializer = OrderCreateSerializer(data=request.data, customer_id=request.user.id)
        if not serializer.is_valid():
            raise ValidationError(detail=serializer.errors)
        order = serializer.save()
        return {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "total_amount": order.total_amount,
            "status": order.status,
            "items_count": len(order.items),
            "message": "Pesanan berhasil diproses secara atomik."
        }

# ==============================================================================
# Dispatch Gateway & Pipeline Visualizer
# ==============================================================================
def dispatch(request: APIRequest, view_class: Any, action_name: str, **kwargs) -> Tuple[int, Dict[str, Any]]:
    view_instance = view_class()
    try:
        method = getattr(view_instance, action_name)
        response_data = method(request, **kwargs)
        return (200 if action_name != "create" else 201), response_data
    except Exception as exc:
        err = custom_exception_handler(exc, {"view": view_class.__name__, "action": action_name})
        return err["status_code"], err["data"]

def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════════════╗
║     DJANGO REST FRAMEWORK (DRF) ADVANCED ARCHITECTURE SIMULATOR LAB       ║
║     Production-Grade Lifecycle: Auth, Serializers, Throttles & RBAC       ║
╚═══════════════════════════════════════════════════════════════════════════╝{Colors.RESET}"""
    print(banner)

def print_pipeline(method: str, path: str, user: Optional[User], status_code: int, payload: Any):
    user_str = f"{user.username} ({user.role})" if user else "Anonymous (Unauthenticated)"
    status_color = Colors.GREEN if status_code < 400 else Colors.RED
    
    print(f"\n{Colors.BOLD}{'='*75}{Colors.RESET}")
    print(f"{ARROW} {Colors.BOLD}HTTP Request:{Colors.RESET} {Colors.YELLOW}{method}{Colors.RESET} {path}")
    print(f"{ARROW} {Colors.BOLD}Principal:{Colors.RESET}    {Colors.BLUE}{user_str}{Colors.RESET}")
    print(f"{ARROW} {Colors.BOLD}Status Code:{Colors.RESET}  {status_color}{status_code}{Colors.RESET}")
    print(f"{Colors.DIM}Payload Response:{Colors.RESET}")
    print(json.dumps(payload, indent=2))
    print(f"{Colors.BOLD}{'='*75}{Colors.RESET}")

# ==============================================================================
# Automated Test Suites & Demonstrations
# ==============================================================================
def run_scenario_1_unauthenticated():
    print(f"\n{Colors.HEADER}[SCENARIO 1] Akses Tanpa Autentikasi (Anonymous User){Colors.RESET}")
    req = APIRequest(method="GET", path="/api/v1/products/", user=None)
    status, res = dispatch(req, ProductViewSet, "list")
    print_pipeline("GET", "/api/v1/products/", None, status, res)
    assert status == 403, f"Expected 403 Forbidden, got {status}"
    print(f"{CHECK} Verifikasi Sukses: Anonymous ditolak dengan PermissionDenied.")

def run_scenario_2_authenticated_list():
    print(f"\n{Colors.HEADER}[SCENARIO 2] Customer Terautentikasi Melakukan Filtering List{Colors.RESET}")
    user = DB["users"][3]  # budi_santoso (customer)
    req = APIRequest(method="GET", path="/api/v1/products/?category=Database", user=user, query_params={"category": "Database"})
    status, res = dispatch(req, ProductViewSet, "list")
    print_pipeline("GET", "/api/v1/products/?category=Database", user, status, res)
    assert status == 200 and res["count"] == 1
    print(f"{CHECK} Verifikasi Sukses: Serializer berhasil merepresentasikan data tersaring.")

def run_scenario_3_object_permission():
    print(f"\n{Colors.HEADER}[SCENARIO 3] Object-Level Permission (IsOwnerOrReadOnly){Colors.RESET}")
    customer = DB["users"][3]  # budi_santoso (Bukan owner produk 101)
    staff_owner = DB["users"][2] # engineer_staff (Owner produk 101)

    print(f"{ARROW} Percobaan 1: Customer mencoba memodifikasi resource milik Staff...")
    req_fail = APIRequest(method="PUT", path="/api/v1/products/101/", user=customer, data={"name": "Hacked Pod", "price": 100, "stock": 5})
    status_fail, res_fail = dispatch(req_fail, ProductViewSet, "update", pk=101)
    print_pipeline("PUT", "/api/v1/products/101/", customer, status_fail, res_fail)
    assert status_fail == 403

    print(f"{ARROW} Percobaan 2: Owner sah memodifikasi resource...")
    req_ok = APIRequest(method="PUT", path="/api/v1/products/101/", user=staff_owner, data={"name": "Kubernetes Pod v2", "price": 310000.0, "stock": 18})
    status_ok, res_ok = dispatch(req_ok, ProductViewSet, "update", pk=101)
    print_pipeline("PUT", "/api/v1/products/101/", staff_owner, status_ok, res_ok)
    assert status_ok == 200
    print(f"{CHECK} Verifikasi Sukses: RBAC Object-Level Permission bekerja presisi.")

def run_scenario_4_atomic_order():
    print(f"\n{Colors.HEADER}[SCENARIO 4] Transaksi Order Bersarang (Nested Serializer & Stock Deduction){Colors.RESET}")
    customer = DB["users"][3]
    initial_stock = DB["products"][102].stock

    order_payload = {
        "items": [
            {"product_id": 102, "quantity": 2},
            {"product_id": 103, "quantity": 3}
        ]
    }
    req = APIRequest(method="POST", path="/api/v1/orders/", user=customer, data=order_payload)
    status, res = dispatch(req, OrderViewSet, "create")
    print_pipeline("POST", "/api/v1/orders/", customer, status, res)
    
    assert status == 201
    assert DB["products"][102].stock == initial_stock - 2
    print(f"{CHECK} Verifikasi Sukses: Transaksi atomik berhasil, stok terpotong dari {initial_stock} menjadi {DB['products'][102].stock}.")

def run_scenario_5_throttling():
    print(f"\n{Colors.HEADER}[SCENARIO 5] Burst Throttling Test (Rate Limit: 5 req/min){Colors.RESET}")
    user = DB["users"][4] # citra_lestari
    throttle_hit = False

    for req_idx in range(1, 8):
        req = APIRequest(method="GET", path="/api/v1/products/", user=user)
        status, res = dispatch(req, ProductViewSet, "list")
        color = Colors.GREEN if status == 200 else Colors.RED
        print(f"Request #{req_idx:02d}: {color}Status {status}{Colors.RESET} -> {res.get('detail', 'OK: Processed')}")
        if status == 429:
            throttle_hit = True
            break

    assert throttle_hit, "Throttle 429 harus dipicu pada request berlebih!"
    print(f"{CHECK} Verifikasi Sukses: Throttler sliding-window menghentikan flood request.")

# ==============================================================================
# Interactive CLI Menu
# ==============================================================================
def interactive_menu():
    print_banner()
    while True:
        print(f"\n{Colors.BOLD}PILIHAN EKSEKUSI LAB:{Colors.RESET}")
        print(" [1] Jalankan Skenario 1: Anonymous Access (403 Permission Denied)")
        print(" [2] Jalankan Skenario 2: Authenticated Filter List (200 OK)")
        print(" [3] Jalankan Skenario 3: Object-Level RBAC Permissions (Owner Check)")
        print(" [4] Jalankan Skenario 4: Nested Serializer & Atomic Order Create (201 Created)")
        print(" [5] Jalankan Skenario 5: Throttling / Rate-Limiter Burst Test (429 Throttled)")
        print(" [6] Jalankan Seluruh Skenario Produksi (Automated Test Suite)")
        print(" [0] Keluar (Exit)")

        choice = input(f"\n{Colors.YELLOW}Pilih opsi [0-6]: {Colors.RESET}").strip()
        if choice == "1":
            run_scenario_1_unauthenticated()
        elif choice == "2":
            run_scenario_2_authenticated_list()
        elif choice == "3":
            run_scenario_3_object_permission()
        elif choice == "4":
            run_scenario_4_atomic_order()
        elif choice == "5":
            run_scenario_5_throttling()
        elif choice == "6":
            print(f"\n{Colors.BOLD}Memulai Eksekusi Pipeline Otomatis Komprehensif...{Colors.RESET}")
            run_scenario_1_unauthenticated()
            run_scenario_2_authenticated_list()
            run_scenario_3_object_permission()
            run_scenario_4_atomic_order()
            run_scenario_5_throttling()
            print(f"\n{Colors.GREEN}{Colors.BOLD}Seluruh 5 Skenario Arsitektur Lolos Verifikasi DRF 100%!{Colors.RESET}\n")
        elif choice == "0":
            print(f"{Colors.CYAN}Lab exercise selesai. Terima kasih.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid, silakan coba lagi.{Colors.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_scenario_1_unauthenticated()
        run_scenario_2_authenticated_list()
        run_scenario_3_object_permission()
        run_scenario_4_atomic_order()
        run_scenario_5_throttling()
        print(f"\n{Colors.GREEN}{Colors.BOLD}Semua pengujian otomatis sukses!{Colors.RESET}")
    else:
        interactive_menu()

#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Clean Architecture Backend Kotlin (Ktor/Spring Boot Enterprise)
BAB-09: Modern Backend Clean Architecture

Simulasi ini mendemonstrasikan pembagian 4 layer arsitektural:
1. Domain Layer (Entity, Value Object, Domain Event, Repository Interface)
2. Use Case / Application Layer (Command/Query Handler, Port Input/Output)
3. Infrastructure Layer (In-Memory Data Store, Event Bus, Logging Adapter)
4. Presentation / Delivery Layer (REST Controller Simulation, Middleware & Request Context)
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Protocol, Any
from enum import Enum


# ============================================================================
# ANSI Color Codes & UI Helper
# ============================================================================
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


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
================================================================================
   KOTLIN BACKEND CLEAN ARCHITECTURE SIMULATOR (BAB-09)
   Enterprise Order & Payment Workflow Engine
================================================================================{Color.RESET}"""
    print(banner)


def log_layer(layer: str, message: str, color: str = Color.WHITE):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} {color}[{layer.upper():<14}]{Color.RESET} {message}")


# ============================================================================
# 1. DOMAIN LAYER (Pure Business Rules & Contracts)
# ============================================================================
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    SHIPPED = "SHIPPED"


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "IDR"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Nominal uang tidak boleh bernilai negatif.")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Mata uang harus identik untuk kalkulasi.")
        return Money(self.amount + other.amount, self.currency)


@dataclass
class OrderItem:
    item_id: str
    product_name: str
    price: Money
    quantity: int

    @property
    def subtotal(self) -> Money:
        return Money(self.price.amount * self.quantity, self.price.currency)


@dataclass
class Order:
    id: str
    customer_id: str
    items: List[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_amount(self) -> Money:
        total = 0.0
        for item in self.items:
            total += item.subtotal.amount
        return Money(total, "IDR")

    def mark_as_paid(self):
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Order {self.id} tidak dapat dibayar (Status saat ini: {self.status.value})")
        self.status = OrderStatus.PAID

    def cancel(self):
        if self.status == OrderStatus.PAID:
            raise ValueError("Order yang sudah berstatus PAID tidak dapat dibatalkan sembarangan.")
        self.status = OrderStatus.CANCELLED


# Domain Repository Interface (Port SPI / Output Port)
class OrderRepositoryPort(Protocol):
    def save(self, order: Order) -> Order: ...
    def find_by_id(self, order_id: str) -> Optional[Order]: ...
    def list_all(self) -> List[Order]: ...


class EventPublisherPort(Protocol):
    def publish(self, event_name: str, payload: Dict[str, Any]) -> None: ...


# ============================================================================
# 2. APPLICATION / USE CASE LAYER
# ============================================================================
@dataclass
class CreateOrderCommand:
    customer_id: str
    items: List[Dict[str, Any]]


@dataclass
class PayOrderCommand:
    order_id: str
    payment_reference: str


class CreateOrderUseCase:
    """Implementasi Interactor / Use Case untuk pendaftaran Order baru"""
    def __init__(self, repository: OrderRepositoryPort, event_publisher: EventPublisherPort):
        self.repository = repository
        self.event_publisher = event_publisher

    def execute(self, cmd: CreateOrderCommand) -> Order:
        log_layer("Use Case", f"Mengeksekusi CreateOrderUseCase untuk Customer ID: {cmd.customer_id}", Color.BLUE)
        order_items = []
        for raw in cmd.items:
            item = OrderItem(
                item_id=str(uuid.uuid4())[:8],
                product_name=raw["name"],
                price=Money(raw["price"]),
                quantity=raw["qty"]
            )
            order_items.append(item)

        new_order = Order(
            id=f"ORD-{str(uuid.uuid4())[:8].upper()}",
            customer_id=cmd.customer_id,
            items=order_items
        )

        saved = self.repository.save(new_order)
        self.event_publisher.publish("OrderCreatedDomainEvent", {
            "order_id": saved.id,
            "total": saved.total_amount.amount,
            "customer_id": saved.customer_id
        })
        return saved


class PayOrderUseCase:
    """Implementasi Interactor / Use Case untuk penyelesaian transaksi pembayaran"""
    def __init__(self, repository: OrderRepositoryPort, event_publisher: EventPublisherPort):
        self.repository = repository
        self.event_publisher = event_publisher

    def execute(self, cmd: PayOrderCommand) -> Order:
        log_layer("Use Case", f"Mengeksekusi PayOrderUseCase untuk Order ID: {cmd.order_id}", Color.BLUE)
        order = self.repository.find_by_id(cmd.order_id)
        if not order:
            raise KeyError(f"Order ID {cmd.order_id} tidak ditemukan.")

        order.mark_as_paid()
        updated = self.repository.save(order)

        self.event_publisher.publish("OrderPaidDomainEvent", {
            "order_id": updated.id,
            "payment_ref": cmd.payment_reference,
            "status": updated.status.value
        })
        return updated


# ============================================================================
# 3. INFRASTRUCTURE LAYER (Adapters & External Drivers)
# ============================================================================
class InMemoryOrderRepository(OrderRepositoryPort):
    def __init__(self):
        self._storage: Dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        log_layer("Database", f"Persisting Order {order.id} ke In-Memory Datastore...", Color.MAGENTA)
        self._storage[order.id] = order
        return order

    def find_by_id(self, order_id: str) -> Optional[Order]:
        log_layer("Database", f"Query SELECT order by id={order_id}", Color.MAGENTA)
        return self._storage.get(order_id)

    def list_all(self) -> List[Order]:
        return list(self._storage.values())


class ConsoleKafkaEventPublisher(EventPublisherPort):
    def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        log_layer("Kafka Broker", f"Mengirim event -> {Color.BOLD}{event_name}{Color.RESET}: {payload}", Color.YELLOW)


# ============================================================================
# 4. PRESENTATION / ADAPTER LAYER (Controller & Middleware)
# ============================================================================
class OrderRestController:
    """Simulasi Ktor Routing / Spring Web MVC Controller"""
    def __init__(self, create_use_case: CreateOrderUseCase, pay_use_case: PayOrderUseCase, repo: OrderRepositoryPort):
        self.create_use_case = create_use_case
        self.pay_use_case = pay_use_case
        self.repo = repo

    def post_create_order(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        correlation_id = str(uuid.uuid4())[:8]
        log_layer("HTTP Inbound", f"POST /api/v1/orders (trace_id={correlation_id})", Color.CYAN)
        
        cmd = CreateOrderCommand(
            customer_id=request_body["customer_id"],
            items=request_body["items"]
        )
        created_order = self.create_use_case.execute(cmd)

        return {
            "status": 201,
            "trace_id": correlation_id,
            "data": {
                "order_id": created_order.id,
                "total_amount": created_order.total_amount.amount,
                "currency": created_order.total_amount.currency,
                "items_count": len(created_order.items),
                "order_status": created_order.status.value
            }
        }

    def post_pay_order(self, order_id: str, request_body: Dict[str, Any]) -> Dict[str, Any]:
        correlation_id = str(uuid.uuid4())[:8]
        log_layer("HTTP Inbound", f"POST /api/v1/orders/{order_id}/pay (trace_id={correlation_id})", Color.CYAN)
        
        cmd = PayOrderCommand(order_id=order_id, payment_reference=request_body.get("ref", "TRX-AUTO"))
        updated = self.pay_use_case.execute(cmd)

        return {
            "status": 200,
            "trace_id": correlation_id,
            "data": {
                "order_id": updated.id,
                "order_status": updated.status.value,
                "message": "Pembayaran diverifikasi secara sukses."
            }
        }

    def get_orders(self) -> Dict[str, Any]:
        log_layer("HTTP Inbound", "GET /api/v1/orders", Color.CYAN)
        orders = self.repo.list_all()
        return {
            "status": 200,
            "count": len(orders),
            "data": [
                {
                    "order_id": o.id,
                    "customer_id": o.customer_id,
                    "total": f"{o.total_amount.amount:,.2f} {o.total_amount.currency}",
                    "status": o.status.value
                } for o in orders
            ]
        }


# ============================================================================
# INTERACTIVE CLI & DEMONSTRATION WORKFLOW
# ============================================================================
def run_automated_pipeline():
    print(f"\n{Color.BOLD}{Color.GREEN}>>> Memulai Skrip Demonstrasi Otomatis (Clean Architecture Pipeline) <<<{Color.RESET}\n")

    # Inisialisasi Dependensi (IoC Container / Manual Dependency Injection)
    repo = InMemoryOrderRepository()
    event_bus = ConsoleKafkaEventPublisher()

    create_uc = CreateOrderUseCase(repository=repo, event_publisher=event_bus)
    pay_uc = PayOrderUseCase(repository=repo, event_publisher=event_bus)

    controller = OrderRestController(create_uc, pay_uc, repo)

    # 1. Skenario Sukses: Create Order 1
    sample_request_1 = {
        "customer_id": "CUST-8801",
        "items": [
            {"name": "Buku 'Kotlin Coroutines in Action'", "price": 185000.0, "qty": 1},
            {"name": "Domain-Driven Design Reference Card", "price": 45000.0, "qty": 2}
        ]
    }
    res_1 = controller.post_create_order(sample_request_1)
    order_1_id = res_1["data"]["order_id"]
    print(f"{Color.GREEN}✔ Order Berhasil Dibuat:{Color.RESET} {res_1}\n")
    time.sleep(0.3)

    # 2. Skenario Sukses: Create Order 2
    sample_request_2 = {
        "customer_id": "CUST-9922",
        "items": [
            {"name": "Cloud Architecture Handbook", "price": 320000.0, "qty": 1}
        ]
    }
    res_2 = controller.post_create_order(sample_request_2)
    order_2_id = res_2["data"]["order_id"]
    print(f"{Color.GREEN}✔ Order Berhasil Dibuat:{Color.RESET} {res_2}\n")
    time.sleep(0.3)

    # 3. Bayar Order 1
    pay_res_1 = controller.post_pay_order(order_1_id, {"ref": "BCA-VA-98124012"})
    print(f"{Color.GREEN}✔ Status Pembayaran:{Color.RESET} {pay_res_1}\n")
    time.sleep(0.3)

    # 4. Uji Coba Domain Rule Violation (Idempotency / Double Pay)
    print(f"{Color.YELLOW}⚠ Menguji Domain Rule Protection: Membayar ulang order yang sudah PAID...{Color.RESET}")
    try:
        controller.post_pay_order(order_1_id, {"ref": "BCA-VA-DUPLICATE"})
    except ValueError as e:
        print(f"{Color.RED}✖ Domain Guard Bekerja Semestinya:{Color.RESET} {e}\n")

    # 5. List All Orders
    all_orders = controller.get_orders()
    print(f"{Color.BOLD}{Color.WHITE}--- RANGKUMAN STATE DATABASE ---{Color.RESET}")
    for item in all_orders["data"]:
        status_color = Color.GREEN if item["status"] == "PAID" else Color.YELLOW
        print(f" • ID: {Color.BOLD}{item['order_id']}{Color.RESET} | Customer: {item['customer_id']} | Total: {item['total']} | Status: {status_color}{item['status']}{Color.RESET}")
    print()


def interactive_menu():
    print_banner()

    # Manual DI Container
    repo = InMemoryOrderRepository()
    event_bus = ConsoleKafkaEventPublisher()
    create_uc = CreateOrderUseCase(repository=repo, event_publisher=event_bus)
    pay_uc = PayOrderUseCase(repository=repo, event_publisher=event_bus)
    controller = OrderRestController(create_uc, pay_uc, repo)

    while True:
        print(f"{Color.BOLD}PILIH MENU INTERAKTIF:{Color.RESET}")
        print(" [1] Jalankan Simulasi Otomatis (End-to-End Test)")
        print(" [2] Tambah Order Baru (Manual HTTP POST Simulation)")
        print(" [3] Bayar Order (Manual HTTP POST Pay Simulation)")
        print(" [4] Tampilkan Seluruh Order")
        print(" [5] Keluar")
        
        try:
            choice = input(f"\n{Color.CYAN}Masukkan pilihan [1-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nProgram dihentikan.")
            break

        if choice == "1":
            run_automated_pipeline()
        elif choice == "2":
            cust_id = input("Customer ID: ").strip() or "CUST-ANON"
            p_name = input("Nama Produk: ").strip() or "Produk Uji Coba"
            try:
                p_price = float(input("Harga Satuan (IDR): ").strip() or "50000")
                p_qty = int(input("Kuantitas (Qty): ").strip() or "1")
            except ValueError:
                print(f"{Color.RED}Input numerik tidak valid!{Color.RESET}\n")
                continue

            payload = {
                "customer_id": cust_id,
                "items": [{"name": p_name, "price": p_price, "qty": p_qty}]
            }
            res = controller.post_create_order(payload)
            print(f"{Color.GREEN}Respon Server:{Color.RESET} {res}\n")

        elif choice == "3":
            oid = input("Masukkan Order ID: ").strip()
            ref = input("Referensi Pembayaran (contoh: VA-12345): ").strip() or "MANUAL-PAY"
            try:
                res = controller.post_pay_order(oid, {"ref": ref})
                print(f"{Color.GREEN}Respon Server:{Color.RESET} {res}\n")
            except Exception as e:
                print(f"{Color.RED}Error saat memproses pembayaran:{Color.RESET} {e}\n")

        elif choice == "4":
            res = controller.get_orders()
            print(f"{Color.BOLD}Daftar Order ({res['count']} record):{Color.RESET}")
            for row in res["data"]:
                print(f" - {row}")
            print()

        elif choice == "5":
            print(f"{Color.GREEN}Terima kasih telah menjalankan simulasi Clean Architecture.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak dikenali.{Color.RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        run_automated_pipeline()
    else:
        # Jika dijalankan tanpa terminal interaktif (stdin bukan TTY), jalankan otomatis
        if not sys.stdin.isatty():
            print_banner()
            run_automated_pipeline()
        else:
            interactive_menu()

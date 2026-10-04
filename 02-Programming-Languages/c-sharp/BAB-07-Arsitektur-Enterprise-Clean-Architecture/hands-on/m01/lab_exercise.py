#!/usr/bin/env python3
"""
Simulasi Interaktif Arsitektur Enterprise C# (.NET Clean Architecture)
BAB-07: Clean Architecture, Domain-Driven Design (DDD) & CQRS Pattern

Materi Representasi:
  1. Domain Layer: Entity, Value Object, Domain Event, Aggregate Root, Repository Contract
  2. Application Layer: CQRS (Command/Query/Handler), MediatR Pipeline Behavior, DTO, Result Pattern
  3. Infrastructure Layer: Repository Implementation, DbContext Simulation, Event Dispatcher
  4. Presentation / WebAPI Layer: Controller Simulation, Dependency Injection (DI) Container

Dapat dijalankan langsung dengan:
    python3 lab_exercise.py
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

# ANSI Escape Sequences untuk Terminal Cantik
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"

def print_banner():
    banner = f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════════════════╗
║              ENTERPRISE C# CLEAN ARCHITECTURE SIMULATOR                      ║
║       Core Domain | CQRS Application | EF Core Infra | Minimal API           ║
╚══════════════════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)

def print_layer_badge(layer_name: str, color: str):
    print(f"\n{color}{BOLD}▶ [LAYER: {layer_name}]{RESET}")

# ==============================================================================
# 1. DOMAIN LAYER (Zero External Dependencies)
# ==============================================================================
class DomainException(Exception):
    """Representasi DomainException dalam C# Clean Architecture."""
    pass

@dataclass(frozen=True)
class Money:
    """Value Object: Immutable & Self-Validating."""
    amount: float
    currency: str = "IDR"

    def __post_init__(self):
        if self.amount < 0:
            raise DomainException("Nominal uang tidak boleh bernilai negatif.")

@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    occurred_on: datetime = field(default_factory=datetime.utcnow)

@dataclass
class OrderCreatedDomainEvent(DomainEvent):
    order_id: str = ""
    customer_id: str = ""
    total_amount: float = 0.0

@dataclass
class OrderPaidDomainEvent(DomainEvent):
    order_id: str = ""
    paid_at: datetime = field(default_factory=datetime.utcnow)

class AggregateRoot:
    """Base class untuk Entity Aggregate yang menampung Domain Events."""
    def __init__(self):
        self._domain_events: List[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent):
        self._domain_events.append(event)

    def pop_domain_events(self) -> List[DomainEvent]:
        events = list(self._domain_events)
        self._domain_events.clear()
        return events

class Order(AggregateRoot):
    """Aggregate Root Domain Entity."""
    def __init__(self, order_id: str, customer_id: str, total_price: Money):
        super().__init__()
        self.id = order_id
        self.customer_id = customer_id
        self.total_price = total_price
        self.status: str = "Submitted"
        self.created_at = datetime.utcnow()

        # Raise event saat terbuat
        self.add_domain_event(
            OrderCreatedDomainEvent(
                order_id=self.id,
                customer_id=self.customer_id,
                total_amount=self.total_price.amount
            )
        )

    def mark_as_paid(self):
        if self.status == "Paid":
            raise DomainException(f"Order #{self.id} sudah lunas sebelumnya.")
        self.status = "Paid"
        self.add_domain_event(OrderPaidDomainEvent(order_id=self.id))

    def cancel(self):
        if self.status == "Paid":
            raise DomainException(f"Order #{self.id} yang sudah lunas tidak dapat dibatalkan.")
        self.status = "Cancelled"

# Repository Interface (Contract dalam Domain)
class IOrderRepository:
    def get_by_id(self, order_id: str) -> Optional[Order]:
        raise NotImplementedError
    def add(self, order: Order) -> None:
        raise NotImplementedError
    def update(self, order: Order) -> None:
        raise NotImplementedError
    def list_all(self) -> List[Order]:
        raise NotImplementedError

# ==============================================================================
# 2. APPLICATION LAYER (Use Cases, CQRS, DTOs, Pipeline Behaviors)
# ==============================================================================
T = TypeVar("T")

@dataclass
class Result(Generic[T]):
    """C# Result Pattern: Functional error handling menggantikan try-catch biasa."""
    is_success: bool
    value: Optional[T] = None
    error: Optional[str] = None

    @classmethod
    def success(cls, value: T) -> "Result[T]":
        return cls(is_success=True, value=value)

    @classmethod
    def failure(cls, error: str) -> "Result[T]":
        return cls(is_success=False, error=error)

# Commands & Queries
@dataclass
class CreateOrderCommand:
    customer_id: str
    amount: float
    currency: str = "IDR"

@dataclass
class MarkOrderPaidCommand:
    order_id: str

@dataclass
class GetOrderByIdQuery:
    order_id: str

@dataclass
class OrderResponseDto:
    order_id: str
    customer_id: str
    total_amount: float
    currency: str
    status: str
    created_at: str

# MediatR Pipeline Behavior Simulation (Logging & Validation)
class PipelineContext:
    @staticmethod
    def execute_with_pipeline(request_name: str, handler_fn: Callable[[], Result[Any]]) -> Result[Any]:
        print(f"  {DIM}[Pipeline: LoggingBehavior] Entering Request: {request_name}{RESET}")
        start_time = time.perf_counter()
        try:
            result = handler_fn()
            duration_ms = (time.perf_counter() - start_time) * 1000
            status_tag = f"{GREEN}Success{RESET}" if result.is_success else f"{RED}Failure({result.error}){RESET}"
            print(f"  {DIM}[Pipeline: LoggingBehavior] Handled {request_name} in {duration_ms:.2f}ms -> {status_tag}")
            return result
        except Exception as ex:
            print(f"  {RED}[Pipeline: UnhandledExceptionBehavior] Exception in {request_name}: {ex}{RESET}")
            return Result.failure(str(ex))

class CreateOrderCommandHandler:
    def __init__(self, repository: IOrderRepository, event_publisher: Any):
        self._repo = repository
        self._publisher = event_publisher

    def handle(self, command: CreateOrderCommand) -> Result[OrderResponseDto]:
        # Validasi FluentValidation style
        if not command.customer_id.strip():
            return Result.failure("CustomerId tidak boleh kosong.")
        if command.amount <= 0:
            return Result.failure("Nilai transaksi order harus lebih besar dari 0.")

        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        money = Money(amount=command.amount, currency=command.currency)
        order = Order(order_id=order_id, customer_id=command.customer_id, total_price=money)

        self._repo.add(order)

        # Dispatch domain events
        events = order.pop_domain_events()
        self._publisher.publish_all(events)

        dto = OrderResponseDto(
            order_id=order.id,
            customer_id=order.customer_id,
            total_amount=order.total_price.amount,
            currency=order.total_price.currency,
            status=order.status,
            created_at=order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        return Result.success(dto)

class MarkOrderPaidCommandHandler:
    def __init__(self, repository: IOrderRepository, event_publisher: Any):
        self._repo = repository
        self._publisher = event_publisher

    def handle(self, command: MarkOrderPaidCommand) -> Result[str]:
        order = self._repo.get_by_id(command.order_id)
        if not order:
            return Result.failure(f"Order #{command.order_id} tidak ditemukan.")

        try:
            order.mark_as_paid()
        except DomainException as ex:
            return Result.failure(str(ex))

        self._repo.update(order)
        self._publisher.publish_all(order.pop_domain_events())
        return Result.success(f"Order #{command.order_id} status diperbarui menjadi PAID.")

class GetOrderByIdQueryHandler:
    def __init__(self, repository: IOrderRepository):
        self._repo = repository

    def handle(self, query: GetOrderByIdQuery) -> Result[OrderResponseDto]:
        order = self._repo.get_by_id(query.order_id)
        if not order:
            return Result.failure(f"Order #{query.order_id} tidak ditemukan.")

        dto = OrderResponseDto(
            order_id=order.id,
            customer_id=order.customer_id,
            total_amount=order.total_price.amount,
            currency=order.total_price.currency,
            status=order.status,
            created_at=order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        return Result.success(dto)

# ==============================================================================
# 3. INFRASTRUCTURE LAYER (EF Core Simulation & Event Broker)
# ==============================================================================
class AppDbContext:
    """Simulasi InMemory DbContext Entity Framework Core."""
    def __init__(self):
        self._orders: Dict[str, Order] = {}

    def save_changes(self):
        print(f"    {MAGENTA}[EF Core: DbContext] Saving changes to Database Context... OK.{RESET}")

class InMemoryOrderRepository(IOrderRepository):
    """Implementasi konkrit interface domain IOrderRepository."""
    def __init__(self, db: AppDbContext):
        self._db = db

    def get_by_id(self, order_id: str) -> Optional[Order]:
        return self._db._orders.get(order_id)

    def add(self, order: Order) -> None:
        self._db._orders[order.id] = order
        self._db.save_changes()

    def update(self, order: Order) -> None:
        self._db._orders[order.id] = order
        self._db.save_changes()

    def list_all(self) -> List[Order]:
        return list(self._db._orders.values())

class DomainEventNotificationDispatcher:
    """Simulasi MediatR INotificationHandler / Outbox Broker."""
    def publish_all(self, events: List[DomainEvent]):
        for ev in events:
            if isinstance(ev, OrderCreatedDomainEvent):
                print(f"    {YELLOW}⚡ [Domain Event Handler] OrderCreatedEvent fired! ID={ev.order_id}, Total={ev.total_amount:,.2f}{RESET}")
                print(f"       -> [Notif Service] Email notifikasi order dikirim ke customer {ev.customer_id}.")
            elif isinstance(ev, OrderPaidDomainEvent):
                print(f"    {YELLOW}⚡ [Domain Event Handler] OrderPaidEvent fired! Order={ev.order_id} at {ev.paid_at.strftime('%H:%M:%S')}{RESET}")
                print(f"       -> [Finance Service] Invoice lunas diterbitkan.")

# ==============================================================================
# 4. PRESENTATION LAYER (Minimal API / Controllers & DI Service Provider)
# ==============================================================================
class ServiceCollection:
    """Simulasi IServiceCollection & IServiceProvider C# .NET."""
    def __init__(self):
        self._services: Dict[Type, Any] = {}

    def add_singleton(self, service_type: Type, instance: Any):
        self._services[service_type] = instance

    def get_service(self, service_type: Type) -> Any:
        return self._services.get(service_type)

class OrdersController:
    """Simulasi ASP.NET Core Minimal API / Controller."""
    def __init__(self, services: ServiceCollection):
        self._repo: IOrderRepository = services.get_service(IOrderRepository)
        self._events: DomainEventNotificationDispatcher = services.get_service(DomainEventNotificationDispatcher)

    def post_create(self, customer_id: str, amount: float) -> Result[OrderResponseDto]:
        cmd = CreateOrderCommand(customer_id=customer_id, amount=amount)
        handler = CreateOrderCommandHandler(self._repo, self._events)
        return PipelineContext.execute_with_pipeline("CreateOrderCommand", lambda: handler.handle(cmd))

    def put_pay(self, order_id: str) -> Result[str]:
        cmd = MarkOrderPaidCommand(order_id=order_id)
        handler = MarkOrderPaidCommandHandler(self._repo, self._events)
        return PipelineContext.execute_with_pipeline("MarkOrderPaidCommand", lambda: handler.handle(cmd))

    def get_by_id(self, order_id: str) -> Result[OrderResponseDto]:
        query = GetOrderByIdQuery(order_id=order_id)
        handler = GetOrderByIdQueryHandler(self._repo)
        return PipelineContext.execute_with_pipeline("GetOrderByIdQuery", lambda: handler.handle(query))

    def get_all(self) -> List[Order]:
        return self._repo.list_all()

# ==============================================================================
# CLI RUNNER & INTERACTIVE LAB WORKFLOW
# ==============================================================================
def setup_application() -> OrdersController:
    """Bootstrapping DI Container (mirip Program.cs .NET 8)."""
    services = ServiceCollection()
    db = AppDbContext()
    repo = InMemoryOrderRepository(db)
    dispatcher = DomainEventNotificationDispatcher()

    services.add_singleton(AppDbContext, db)
    services.add_singleton(IOrderRepository, repo)
    services.add_singleton(DomainEventNotificationDispatcher, dispatcher)

    return OrdersController(services)

def interactive_loop():
    controller = setup_application()
    print_banner()

    # Pre-seed contoh transaksi awal
    print(f"{BLUE}[Bootstrapping]{RESET} Menginisialisasi DI Container & In-Memory Database...")
    controller.post_create("CUST-ALICE-01", 350000.0)
    controller.post_create("CUST-BOB-02", 725000.0)

    while True:
        print(f"\n{BOLD}PILIHAN AKSI BERDASARKAN LAYER CLEAN ARCHITECTURE:{RESET}")
        print(f"  {CYAN}1.{RESET} [Presentation] POST /api/orders (Buat Order Baru - CQRS Command)")
        print(f"  {CYAN}2.{RESET} [Presentation] PUT /api/orders/pay (Lunasi Order - Domain Event Trigger)")
        print(f"  {CYAN}3.{RESET} [Presentation] GET /api/orders/{{id}} (Query Order - CQRS Query)")
        print(f"  {CYAN}4.{RESET} [Infrastructure] Lihat isi InMemory DbContext (Tabel Order)")
        print(f"  {CYAN}5.{RESET} [Domain Engine] Uji Domain Exception & Validasi Negatif")
        print(f"  {CYAN}6.{RESET} Tampilkan Diagram Arsitektur C# Dependency Inversion")
        print(f"  {RED}0.{RESET} Keluar (Exit)")

        choice = input(f"\n{BOLD}Ketik angka menu [0-6]: {RESET}").strip()

        if choice == "1":
            print_layer_badge("APPLICATION / PRESENTATION: CreateOrderCommand", CYAN)
            cust = input("  Masukkan ID Customer (contoh: CUST-CHARLIE): ").strip()
            if not cust:
                cust = "CUST-DEFAULT"
            amt_str = input("  Masukkan Nominal Total Belanja (IDR): ").strip()
            try:
                amt = float(amt_str)
            except ValueError:
                print(f"  {RED}Error: Nilai nominal harus angka valid!{RESET}")
                continue

            res = controller.post_create(cust, amt)
            if res.is_success:
                dto = res.value
                print(f"  {GREEN}✔ HTTP 201 Created{RESET} -> Order ID: {BOLD}{dto.order_id}{RESET} | Status: {dto.status} | Total: {dto.currency} {dto.total_amount:,.2f}")
            else:
                print(f"  {RED}✖ HTTP 400 Bad Request{RESET} -> Error: {res.error}")

        elif choice == "2":
            print_layer_badge("DOMAIN / APPLICATION: MarkOrderPaidCommand", GREEN)
            oid = input("  Masukkan Order ID yang akan dilunasi (contoh: ORD-xxxxxx): ").strip()
            res = controller.put_pay(oid)
            if res.is_success:
                print(f"  {GREEN}✔ HTTP 200 OK{RESET} -> {res.value}")
            else:
                print(f"  {RED}✖ HTTP 400 Bad Request{RESET} -> Error: {res.error}")

        elif choice == "3":
            print_layer_badge("APPLICATION: GetOrderByIdQuery (CQRS Read)", BLUE)
            oid = input("  Masukkan Order ID: ").strip()
            res = controller.get_by_id(oid)
            if res.is_success:
                dto = res.value
                print(f"  {GREEN}✔ HTTP 200 OK{RESET}")
                print(f"    - ID        : {dto.order_id}")
                print(f"    - Customer  : {dto.customer_id}")
                print(f"    - Total     : {dto.currency} {dto.total_amount:,.2f}")
                print(f"    - Status    : {dto.status}")
                print(f"    - Dibuat    : {dto.created_at}")
            else:
                print(f"  {RED}✖ HTTP 404 Not Found{RESET} -> {res.error}")

        elif choice == "4":
            print_layer_badge("INFRASTRUCTURE: EF Core DbContext State", MAGENTA)
            all_orders = controller.get_all()
            if not all_orders:
                print("  Database kosong.")
            else:
                print(f"  {'ORDER ID':<15} {'CUSTOMER':<16} {'STATUS':<12} {'TOTAL':<15}")
                print("  " + "-" * 58)
                for o in all_orders:
                    tot = f"{o.total_price.currency} {o.total_price.amount:,.0f}"
                    status_col = f"{GREEN}{o.status}{RESET}" if o.status == "Paid" else f"{YELLOW}{o.status}{RESET}"
                    print(f"  {o.id:<15} {o.customer_id:<16} {status_col:<21} {tot:<15}")

        elif choice == "5":
            print_layer_badge("DOMAIN RULE TESTING: Pelanggaran Invariant", RED)
            print("  Menguji Invariant Domain: Nominal uang negatif...")
            try:
                Money(-100000, "IDR")
            except DomainException as ex:
                print(f"  {GREEN}✔ Berhasil ditangkap oleh ValueObject DomainException:{RESET} '{ex}'")

            print("\n  Menguji Pelanggaran Transisi Status: Melunasi order yang sudah Paid...")
            orders = controller.get_all()
            if orders:
                test_ord = orders[0]
                test_ord.status = "Paid"
                try:
                    test_ord.mark_as_paid()
                except DomainException as ex:
                    print(f"  {GREEN}✔ Berhasil ditangkap oleh AggregateRoot Rule:{RESET} '{ex}'")

        elif choice == "6":
            print(f"""
{CYAN}{BOLD}==================================================================
                 CLEAN ARCHITECTURE DEPENDENCY RULE
=================================================================={RESET}
              [ Presentation / Web API Layer ]
                              │
                              ▼ (references)
              [ Application Layer (CQRS/Use Cases) ]
                              │
                              ▼ (references)
              [ Domain Layer (Entities/Value Objects) ]
                              ▲
                              │ (implements contracts)
            [ Infrastructure (EF Core, Email, Bus) ]

  * {BOLD}Aturan Emas:{RESET} Inner layers (Domain) tidak boleh memiliki reference
    ke Outer layers (Infra, Presentation, atau Third-party libraries).
  * Infrastructure mengimplementasikan interface/kontrak repository
    yang dideklarasikan di Domain layer (Dependency Inversion Principle).
""")

        elif choice == "0":
            print(f"\n{GREEN}Selesai. Keluar dari simulator C# Clean Architecture.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid! Masukkan angka 0-6.{RESET}")

if __name__ == "__main__":
    interactive_loop()

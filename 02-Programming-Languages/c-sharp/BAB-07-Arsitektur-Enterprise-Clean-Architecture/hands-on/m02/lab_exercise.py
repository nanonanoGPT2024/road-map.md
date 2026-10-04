#!/usr/bin/env python3
"""
Lab Hands-on: C# Enterprise Architecture & Clean Architecture Deep Dive
Simulasi Implementasi CQRS, MediatR Pipeline Behaviors, Domain-Driven Design (DDD),
Unit of Work, dan Outbox Pattern pada ekosistem .NET Modern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import json
import time
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar
import uuid

# --- ANSI Terminal Colors ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_RED = "\033[91m"

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


# ==============================================================================
# 1. DOMAIN LAYER (Enterprise Core: Entities, Value Objects, Domain Events)
# ==============================================================================

class IDomainEvent(ABC):
    """Marker interface untuk Domain Event yang terjadi pada Aggregate."""
    def __init__(self):
        self.event_id: str = str(uuid.uuid4())
        self.occurred_on: datetime = datetime.utcnow()


@dataclass(frozen=True)
class Money:
    """Value Object: Immutable, equality berdasarkan state bukan identitas."""
    amount: float
    currency: str = "USD"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount tidak boleh negatif.")


@dataclass
class OrderPlacedDomainEvent(IDomainEvent):
    order_id: str
    customer_id: str
    total_amount: float
    currency: str

    def __post_init__(self):
        super().__init__()


class AggregateRoot(ABC):
    """Base class untuk Aggregate Root yang mengelola lifecycle Domain Events."""
    def __init__(self, aggregate_id: str):
        self.id: str = aggregate_id
        self._domain_events: List[IDomainEvent] = []

    def add_domain_event(self, event: IDomainEvent) -> None:
        self._domain_events.append(event)

    def pop_domain_events(self) -> List[IDomainEvent]:
        events = list(self._domain_events)
        self._domain_events.clear()
        return events


class Order(AggregateRoot):
    """Aggregate Root Domain: Menegakkan invariant bisnis."""
    def __init__(self, order_id: str, customer_id: str):
        super().__init__(order_id)
        self.customer_id: str = customer_id
        self.items: List[Dict[str, Any]] = []
        self.total_price: Money = Money(0.0)
        self.status: str = "Draft"

    def add_item(self, sku: str, quantity: int, unit_price: float) -> None:
        if quantity <= 0:
            raise ValueError("Quantity harus lebih dari nol.")
        self.items.append({"sku": sku, "quantity": quantity, "price": unit_price})
        new_total = self.total_price.amount + (quantity * unit_price)
        self.total_price = Money(round(new_total, 2), self.total_price.currency)

    def checkout(self) -> None:
        if not self.items:
            raise ValueError("Tidak dapat checkout pesanan kosong.")
        self.status = "Placed"
        # Raise Domain Event yang nanti diproses oleh Outbox / Event Dispatcher
        self.add_domain_event(
            OrderPlacedDomainEvent(
                order_id=self.id,
                customer_id=self.customer_id,
                total_amount=self.total_price.amount,
                currency=self.total_price.currency
            )
        )


# ==============================================================================
# 2. INFRASTRUCTURE & PERSISTENCE (DbContext, Repository, Outbox)
# ==============================================================================

@dataclass
class OutboxMessage:
    id: str
    event_type: str
    payload: str
    created_at: datetime
    processed: bool = False


class InMemoryDbContext:
    """Simulasi Entity Framework Core DbContext dengan Tracking & Outbox Table."""
    def __init__(self):
        self.orders_table: Dict[str, Order] = {}
        self.outbox_table: List[OutboxMessage] = []
        self._in_transaction: bool = False

    def begin_transaction(self) -> None:
        self._in_transaction = True

    def commit(self) -> None:
        self._in_transaction = False

    def rollback(self) -> None:
        self._in_transaction = False


class IOrderRepository(ABC):
    @abstractmethod
    def add(self, order: Order) -> None:
        pass


class IUnitOfWork(ABC):
    @abstractmethod
    def save_changes(self) -> int:
        pass


class EfOrderRepository(IOrderRepository):
    def __init__(self, db: InMemoryDbContext):
        self._db = db

    def add(self, order: Order) -> None:
        self._db.orders_table[order.id] = order


class EfUnitOfWork(IUnitOfWork):
    """
    Unit of Work: Menjaga konsistensi data dan menulis Domain Events
    ke tabel Outbox dalam satu transaksi atomik (Transactional Outbox Pattern).
    """
    def __init__(self, db: InMemoryDbContext):
        self._db = db

    def save_changes(self) -> int:
        records_written = 0
        for order in self._db.orders_table.values():
            events = order.pop_domain_events()
            for event in events:
                outbox_entry = OutboxMessage(
                    id=event.event_id,
                    event_type=type(event).__name__,
                    payload=json.dumps(event.__dict__, default=str),
                    created_at=event.occurred_on
                )
                self._db.outbox_table.append(outbox_entry)
                records_written += 1
        return records_written


# ==============================================================================
# 3. APPLICATION LAYER (CQRS, MediatR Pattern, & Pipeline Behaviors)
# ==============================================================================

class IRequest(Generic[TResponse], ABC):
    """Simulasi MediatR IRequest<TResponse>."""
    pass


class IRequestHandler(Generic[TRequest, TResponse], ABC):
    """Simulasi MediatR IRequestHandler<TRequest, TResponse>."""
    @abstractmethod
    def handle(self, request: TRequest) -> TResponse:
        pass


class IPipelineBehavior(ABC):
    """Middleware pipeline untuk Cross-Cutting Concerns (Logging, Validation, UoW)."""
    @abstractmethod
    def handle(self, request: Any, next_action: Callable[[], Any]) -> Any:
        pass


@dataclass
class CreateOrderCommand(IRequest[str]):
    customer_id: str
    items: List[Dict[str, Any]]


class CreateOrderCommandHandler(IRequestHandler[CreateOrderCommand, str]):
    """Application Command Handler: Mengorkestrasi Domain dan Repository."""
    def __init__(self, repo: IOrderRepository):
        self._repo = repo

    def handle(self, request: CreateOrderCommand) -> str:
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order = Order(order_id, request.customer_id)
        for item in request.items:
            order.add_item(item["sku"], item["quantity"], item["unit_price"])
        order.checkout()
        self._repo.add(order)
        return order.id


# Pipeline Behaviors (Cross-Cutting Concerns)
class LoggingBehavior(IPipelineBehavior):
    def handle(self, request: Any, next_action: Callable[[], Any]) -> Any:
        req_name = type(request).__name__
        print(f"  {CLR_BLUE}--> [Pipeline: Logging]{CLR_RESET} Handling request {CLR_BOLD}{req_name}{CLR_RESET}")
        start_time = time.perf_counter()
        response = next_action()
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"  {CLR_BLUE}<-- [Pipeline: Logging]{CLR_RESET} {req_name} processed in {elapsed:.2f}ms")
        return response


class ValidationBehavior(IPipelineBehavior):
    """Simulasi FluentValidation di dalam MediatR pipeline."""
    def handle(self, request: Any, next_action: Callable[[], Any]) -> Any:
        print(f"  {CLR_YELLOW}[Pipeline: Validation]{CLR_RESET} Validating incoming command...")
        if isinstance(request, CreateOrderCommand):
            if not request.customer_id:
                raise ValueError("Validation Failed: CustomerId wajib diisi.")
            if not request.items:
                raise ValueError("Validation Failed: Items minimal memiliki 1 produk.")
        return next_action()


class TransactionBehavior(IPipelineBehavior):
    """Unit of Work behavior: Menangani database transaction boundary."""
    def __init__(self, db: InMemoryDbContext, uow: IUnitOfWork):
        self._db = db
        self._uow = uow

    def handle(self, request: Any, next_action: Callable[[], Any]) -> Any:
        print(f"  {CLR_MAGENTA}[Pipeline: Transaction]{CLR_RESET} Memulai DB Transaction & UoW Boundary...")
        self._db.begin_transaction()
        try:
            result = next_action()
            outbox_count = self._uow.save_changes()
            self._db.commit()
            print(f"  {CLR_MAGENTA}[Pipeline: Transaction]{CLR_RESET} Committed! Disimpan {outbox_count} domain event ke Outbox.")
            return result
        except Exception as ex:
            self._db.rollback()
            print(f"  {CLR_RED}[Pipeline: Transaction] Rollback terjadi karena kegagalan: {ex}{CLR_RESET}")
            raise


# ==============================================================================
# 4. MEDIATOR IMPLEMENTATION (Mini-MediatR Engine)
# ==============================================================================

class Mediator:
    """Implementasi mediator yang merangkai pipeline middleware."""
    def __init__(self):
        self._handlers: Dict[Type, Any] = {}
        self._behaviors: List[IPipelineBehavior] = []

    def register_handler(self, request_type: Type, handler_instance: Any) -> None:
        self._handlers[request_type] = handler_instance

    def add_behavior(self, behavior: IPipelineBehavior) -> None:
        self._behaviors.append(behavior)

    def send(self, request: Any) -> Any:
        req_type = type(request)
        if req_type not in self._handlers:
            raise NotImplementedError(f"No handler registered for {req_type.__name__}")

        handler = self._handlers[req_type]

        def target_execution():
            return handler.handle(request)

        # Bangun pipeline chain secara reaktif (LIFO chaining)
        chain = target_execution
        for behavior in reversed(self._behaviors):
            current_behavior = behavior
            next_step = chain
            chain = (lambda b, n: lambda: b.handle(request, n))(current_behavior, next_step)

        return chain()


# ==============================================================================
# 5. BACKGROUND WORKER (Outbox Processor Simulation)
# ==============================================================================

class OutboxProcessorBackgroundService:
    """
    Simulasi .NET IHostedService / BackgroundService:
    Membaca pesan dari outbox table secara polling dan mempublikasikannya ke Message Broker.
    """
    def __init__(self, db: InMemoryDbContext):
        self._db = db

    def process_pending_messages(self) -> None:
        print(f"\n{CLR_CYAN}[Worker: OutboxProcessor]{CLR_RESET} Memindai event pending di outbox...")
        pending = [m for m in self._db.outbox_table if not m.processed]
        if not pending:
            print(f"  {CLR_CYAN}[Worker]{CLR_RESET} Tidak ada event pending.")
            return

        for msg in pending:
            print(f"  {CLR_GREEN}>> Publishing to Event Bus (RabbitMQ/Kafka):{CLR_RESET}")
            print(f"     Type    : {CLR_BOLD}{msg.event_type}{CLR_RESET}")
            print(f"     EventId : {msg.id}")
            print(f"     Payload : {msg.payload}")
            # Mark as processed
            msg.processed = True
        print(f"{CLR_CYAN}[Worker: OutboxProcessor]{CLR_RESET} Selesai memproses {len(pending)} event.")


# ==============================================================================
# 6. LAB RUNNER / DEMONSTRASI UTAMA
# ==============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} LAB: C# ENTERPRISE & CLEAN ARCHITECTURE DEEP DIVE SIMULATOR {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}\n")

    # Dependency Injection Setup
    db_context = InMemoryDbContext()
    unit_of_work = EfUnitOfWork(db_context)
    order_repo = EfOrderRepository(db_context)

    mediator = Mediator()
    mediator.add_behavior(LoggingBehavior())
    mediator.add_behavior(ValidationBehavior())
    mediator.add_behavior(TransactionBehavior(db_context, unit_of_work))

    create_order_handler = CreateOrderCommandHandler(order_repo)
    mediator.register_handler(CreateOrderCommand, create_order_handler)

    print(f"{CLR_BOLD}--- Scenario 1: Mengirim Valid CreateOrderCommand melalui MediatR Pipeline ---{CLR_RESET}")
    command_1 = CreateOrderCommand(
        customer_id="CUST-NET-789",
        items=[
            {"sku": "DOTNET-BOOK-01", "quantity": 1, "unit_price": 45.50},
            {"sku": "AZURE-DEV-PASS", "quantity": 2, "unit_price": 12.00}
        ]
    )

    try:
        created_id = mediator.send(command_1)
        print(f"\n{CLR_GREEN}Pesanan Berhasil Diproses! Order ID: {CLR_BOLD}{created_id}{CLR_RESET}")
    except Exception as ex:
        print(f"{CLR_RED}Gagal memproses: {ex}{CLR_RESET}")

    # Cek State Database
    order = db_context.orders_table[created_id]
    print(f"DB State -> Order: {order.id}, Status: {order.status}, Total: {order.total_price.amount} {order.total_price.currency}")

    # Eksekusi Background Outbox Publisher
    background_worker = OutboxProcessorBackgroundService(db_context)
    background_worker.process_pending_messages()

    print(f"\n{CLR_BOLD}--- Scenario 2: Validasi Gagal (Cross-Cutting Concern Pipeline) ---{CLR_RESET}")
    invalid_command = CreateOrderCommand(
        customer_id="",  # CustomerId kosong memicu validasi
        items=[]
    )
    try:
        mediator.send(invalid_command)
    except ValueError as val_ex:
        print(f"{CLR_RED}Ditangkap di boundary presentasi: {val_ex}{CLR_RESET}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN} Simulasi Arsitektur Enterprise Selesai dengan Sukses! {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
BAB-09: Modern Backend & Clean Architecture (Kotlin Paradigm Simulator)
Interactive Hands-On Lab Exercise (Python 3 Runnable Simulation)

This lab simulates Kotlin-idiomatic Clean Architecture patterns:
  1. Domain Entities & Value Objects (immutability, validation)
  2. Sealed Result Types (Kotlin Result/Either pattern)
  3. Domain Ports / Repository Interfaces
  4. Use Cases (Application Layer Interactors)
  5. Infrastructure Adapters (In-Memory Repository & Presenter)
  6. Framework/Presentation simulation (Ktor-style Routing & HTTP Handlers)
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

# ==============================================================================
# ANSI Color Palette for Rich Terminal Interface
# ==============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'

def print_banner():
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 78}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   KOTLIN CLEAN ARCHITECTURE & BACKEND SIMULATOR (BAB-09 M01 LAB){Colors.ENDC}")
    print(f"{Colors.CYAN}{'=' * 78}{Colors.ENDC}")
    print(f"{Colors.DIM}Simulating: Entities -> UseCases -> Repositories -> Ktor Endpoints{Colors.ENDC}\n")

# ==============================================================================
# 1. CORE FUNCTIONAL PRIMITIVES (Kotlin Sealed Class / Result Simulation)
# ==============================================================================
T = TypeVar('T')
E = TypeVar('E')

class Result(Generic[T, E]):
    """Simulates Kotlin's sealed class Result<T> / Arrow-kt Either<E, A>"""
    def __init__(self, value: Optional[T] = None, error: Optional[E] = None, is_success: bool = True):
        self._value = value
        self._error = error
        self._is_success = is_success

    @classmethod
    def success(cls, value: T) -> 'Result[T, E]':
        return cls(value=value, is_success=True)

    @classmethod
    def failure(cls, error: E) -> 'Result[T, E]':
        return cls(error=error, is_success=False)

    @property
    def is_success(self) -> bool:
        return self._is_success

    @property
    def value(self) -> T:
        if not self._is_success:
            raise ValueError(f"Cannot get value from failure result: {self._error}")
        return self._value  # type: ignore

    @property
    def error(self) -> E:
        if self._is_success:
            raise ValueError("Cannot get error from success result")
        return self._error  # type: ignore

    def fold(self, on_success: Callable[[T], Any], on_failure: Callable[[E], Any]) -> Any:
        if self._is_success:
            return on_success(self._value)  # type: ignore
        return on_failure(self._error)  # type: ignore

# ==============================================================================
# 2. DOMAIN LAYER (Entities, Value Objects, Domain Exceptions)
# ==============================================================================
class OrderStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"

@dataclass(frozen=True)
class Money:
    """Value Object: Immutable with self-validation rules"""
    amount: float
    currency: str = "USD"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be a 3-letter ISO code")

    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

@dataclass(frozen=True)
class OrderItem:
    sku: str
    name: str
    unit_price: Money
    quantity: int

    def subtotal(self) -> Money:
        return Money(amount=self.unit_price.amount * self.quantity, currency=self.unit_price.currency)

@dataclass
class Order:
    """Domain Entity: Encapsulates state and business invariants"""
    id: str
    customer_id: str
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def calculate_total(self) -> Money:
        if not self.items:
            return Money(amount=0.0)
        curr = self.items[0].unit_price.currency
        total = sum(item.subtotal().amount for item in self.items)
        return Money(amount=total, currency=curr)

    def confirm(self) -> Result[bool, str]:
        if self.status != OrderStatus.PENDING:
            return Result.failure(f"Cannot confirm order in state '{self.status.value}'")
        if not self.items:
            return Result.failure("Cannot confirm an order with zero items")
        self.status = OrderStatus.CONFIRMED
        return Result.success(True)

    def cancel(self) -> Result[bool, str]:
        if self.status == OrderStatus.SHIPPED:
            return Result.failure("Cannot cancel an order that is already shipped")
        self.status = OrderStatus.CANCELLED
        return Result.success(True)

# Domain Port (Interface)
class OrderRepositoryPort:
    def save(self, order: Order) -> Result[Order, str]:
        raise NotImplementedError

    def find_by_id(self, order_id: str) -> Result[Optional[Order], str]:
        raise NotImplementedError

    def list_all(self) -> Result[List[Order], str]:
        raise NotImplementedError

# ==============================================================================
# 3. APPLICATION LAYER (Use Cases / CQRS Interactors)
# ==============================================================================
@dataclass
class CreateOrderCommand:
    customer_id: str
    items_raw: List[Dict[str, Any]]

class CreateOrderUseCase:
    """Interactors coordinate domain models and repository ports"""
    def __init__(self, repo: OrderRepositoryPort):
        self.repo = repo

    def execute(self, cmd: CreateOrderCommand) -> Result[Order, str]:
        if not cmd.customer_id.strip():
            return Result.failure("Validation Error: customer_id cannot be blank")
        if not cmd.items_raw:
            return Result.failure("Validation Error: order must have at least 1 item")

        parsed_items: List[OrderItem] = []
        try:
            for it in cmd.items_raw:
                money = Money(amount=float(it['unit_price']), currency=it.get('currency', 'USD'))
                qty = int(it['quantity'])
                if qty <= 0:
                    return Result.failure("Validation Error: Item quantity must be > 0")
                parsed_items.append(OrderItem(
                    sku=it['sku'],
                    name=it['name'],
                    unit_price=money,
                    quantity=qty
                ))
        except Exception as ex:
            return Result.failure(f"Payload parsing error: {str(ex)}")

        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        order = Order(id=order_id, customer_id=cmd.customer_id, items=parsed_items)

        save_res = self.repo.save(order)
        return save_res

class ConfirmOrderUseCase:
    def __init__(self, repo: OrderRepositoryPort):
        self.repo = repo

    def execute(self, order_id: str) -> Result[Order, str]:
        find_res = self.repo.find_by_id(order_id)
        if not find_res.is_success:
            return Result.failure(find_res.error)
        order = find_res.value
        if not order:
            return Result.failure(f"Order '{order_id}' not found")

        confirm_res = order.confirm()
        if not confirm_res.is_success:
            return Result.failure(confirm_res.error)

        return self.repo.save(order)

# ==============================================================================
# 4. INFRASTRUCTURE ADAPTER LAYER (In-Memory Repository Implementation)
# ==============================================================================
class InMemoryOrderRepository(OrderRepositoryPort):
    def __init__(self):
        self._storage: Dict[str, Order] = {}

    def save(self, order: Order) -> Result[Order, str]:
        self._storage[order.id] = order
        return Result.success(order)

    def find_by_id(self, order_id: str) -> Result[Optional[Order], str]:
        return Result.success(self._storage.get(order_id))

    def list_all(self) -> Result[List[Order], str]:
        return Result.success(list(self._storage.values()))

# ==============================================================================
# 5. PRESENTATION LAYER (Simulating Ktor / Spring HTTP Web Routing)
# ==============================================================================
class OrderController:
    """Simulates Ktor Routing DSL and ContentNegotiation JSON Serializer"""
    def __init__(self, create_uc: CreateOrderUseCase, confirm_uc: ConfirmOrderUseCase, repo: OrderRepositoryPort):
        self.create_uc = create_uc
        self.confirm_uc = confirm_uc
        self.repo = repo

    def handle_post_order(self, customer_id: str, raw_items: List[Dict[str, Any]]) -> None:
        print(f"\n{Colors.BLUE}--> [HTTP POST /api/v1/orders] Incoming request...{Colors.ENDC}")
        time.sleep(0.3)
        cmd = CreateOrderCommand(customer_id=customer_id, items_raw=raw_items)
        result = self.create_uc.execute(cmd)

        if result.is_success:
            ord_obj = result.value
            tot = ord_obj.calculate_total()
            print(f"{Colors.GREEN}[201 Created]{Colors.ENDC} Order successfully committed to storage!")
            print(f"  {Colors.BOLD}ID:{Colors.ENDC} {ord_obj.id} | {Colors.BOLD}Customer:{Colors.ENDC} {ord_obj.customer_id}")
            print(f"  {Colors.BOLD}Total:{Colors.ENDC} {tot.currency} {tot.amount:.2f} | {Colors.BOLD}Status:{Colors.ENDC} {ord_obj.status.value}")
            for item in ord_obj.items:
                print(f"    * {item.name} ({item.sku}) x{item.quantity} @ {item.unit_price.amount} {item.unit_price.currency}")
        else:
            print(f"{Colors.FAIL}[400 Bad Request]{Colors.ENDC} Business constraint rejected: {result.error}")

    def handle_post_confirm(self, order_id: str) -> None:
        print(f"\n{Colors.BLUE}--> [HTTP POST /api/v1/orders/{order_id}/confirm]{Colors.ENDC}")
        time.sleep(0.3)
        result = self.confirm_uc.execute(order_id)
        if result.is_success:
            print(f"{Colors.GREEN}[200 OK]{Colors.ENDC} Order {order_id} state changed to {result.value.status.value}")
        else:
            print(f"{Colors.FAIL}[422 Unprocessable Entity]{Colors.ENDC} {result.error}")

    def handle_get_all(self) -> None:
        print(f"\n{Colors.BLUE}--> [HTTP GET /api/v1/orders]{Colors.ENDC}")
        res = self.repo.list_all()
        orders = res.value
        if not orders:
            print(f"{Colors.DIM}No orders found in database.{Colors.ENDC}")
            return
        print(f"{Colors.GREEN}[200 OK]{Colors.ENDC} Total Orders Found: {len(orders)}")
        for o in orders:
            tot = o.calculate_total()
            color_st = Colors.WARNING if o.status == OrderStatus.PENDING else Colors.GREEN
            print(f"  - [{color_st}{o.status.value}{Colors.ENDC}] ID: {o.id} | Cust: {o.customer_id} | Total: {tot.amount:.2f} {tot.currency} ({len(o.items)} items)")

# ==============================================================================
# 6. INTERACTIVE CLI RUNNER & BENCHMARK SUITE
# ==============================================================================
def seed_demo_data(controller: OrderController):
    print(f"{Colors.DIM}Seeding initial clean architecture domain records...{Colors.ENDC}")
    controller.handle_post_order("CUST-101", [
        {"sku": "KOT-01", "name": "Kotlin Coroutines Deep Dive", "unit_price": 45.0, "quantity": 1},
        {"sku": "KOT-02", "name": "Clean Architecture Guide", "unit_price": 55.0, "quantity": 2}
    ])
    controller.handle_post_order("CUST-202", [
        {"sku": "SRV-99", "name": "Microservice Voucher", "unit_price": 120.0, "quantity": 1}
    ])

def interactive_loop():
    repo = InMemoryOrderRepository()
    create_uc = CreateOrderUseCase(repo)
    confirm_uc = ConfirmOrderUseCase(repo)
    controller = OrderController(create_uc, confirm_uc, repo)

    print_banner()
    seed_demo_data(controller)

    while True:
        print(f"\n{Colors.CYAN}{Colors.BOLD}--- Interactive Console Menu ---{Colors.ENDC}")
        print("1. List All Orders (GET /api/v1/orders)")
        print("2. Create New Order (POST /api/v1/orders)")
        print("3. Confirm Order (POST /api/v1/orders/{id}/confirm)")
        print("4. Trigger Domain Validation Failure (Negative Price / Empty Items)")
        print("5. Run Automated Architecture Compliance Test")
        print("6. Exit")

        try:
            choice = input(f"\n{Colors.BOLD}Select an option [1-6]: {Colors.ENDC}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == '1':
            controller.handle_get_all()
        elif choice == '2':
            cust = input("Enter Customer ID: ").strip() or "CUST-DEFAULT"
            name = input("Enter Item Name: ").strip() or "Standard Service Package"
            price_str = input("Enter Unit Price (default 50.0): ").strip() or "50.0"
            qty_str = input("Enter Quantity (default 1): ").strip() or "1"
            try:
                controller.handle_post_order(cust, [{
                    "sku": f"SKU-{uuid.uuid4().hex[:4].upper()}",
                    "name": name,
                    "unit_price": float(price_str),
                    "quantity": int(qty_str)
                }])
            except ValueError as ex:
                print(f"{Colors.FAIL}Input Error: {ex}{Colors.ENDC}")
        elif choice == '3':
            ord_id = input("Enter Order ID to Confirm: ").strip()
            if ord_id:
                controller.handle_post_confirm(ord_id)
            else:
                print(f"{Colors.FAIL}Order ID cannot be empty.{Colors.ENDC}")
        elif choice == '4':
            print(f"{Colors.WARNING}Simulating malicious/invalid payload...{Colors.ENDC}")
            controller.handle_post_order("CUST-MALICIOUS", [{
                "sku": "BAD-01",
                "name": "Invalid Item",
                "unit_price": -99.0,
                "quantity": 0
            }])
        elif choice == '5':
            run_verification_test(repo, create_uc, confirm_uc)
        elif choice == '6':
            print(f"{Colors.GREEN}Terminating simulator. Happy coding Clean Architecture in Kotlin!{Colors.ENDC}")
            break
        else:
            print(f"{Colors.FAIL}Invalid choice. Please select 1-6.{Colors.ENDC}")

def run_verification_test(repo: InMemoryOrderRepository, create_uc: CreateOrderUseCase, confirm_uc: ConfirmOrderUseCase):
    print(f"\n{Colors.HEADER}=== Running Clean Architecture Automated Test Suite ==={Colors.ENDC}")
    # Test 1: Value Object Invariant
    try:
        Money(amount=-10.0, currency="USD")
        print(f"[{Colors.FAIL}FAIL{Colors.ENDC}] Negative money was allowed")
    except ValueError:
        print(f"[{Colors.GREEN}PASS{Colors.ENDC}] Value Object Invariant: Negative money rejected")

    # Test 2: UseCase Validation
    cmd_invalid = CreateOrderCommand(customer_id="", items_raw=[])
    res_inv = create_uc.execute(cmd_invalid)
    assert not res_inv.is_success
    print(f"[{Colors.GREEN}PASS{Colors.ENDC}] UseCase Port Validation: Blank customer rejected")

    # Test 3: Happy Path Order Lifecycle
    cmd_ok = CreateOrderCommand(customer_id="TEST-CUST", items_raw=[
        {"sku": "T1", "name": "Test Item", "unit_price": 25.0, "quantity": 2}
    ])
    res_ok = create_uc.execute(cmd_ok)
    assert res_ok.is_success
    created = res_ok.value
    assert created.status == OrderStatus.PENDING
    print(f"[{Colors.GREEN}PASS{Colors.ENDC}] Repository Port Persistence: Order created ({created.id})")

    confirm_res = confirm_uc.execute(created.id)
    assert confirm_res.is_success
    assert confirm_res.value.status == OrderStatus.CONFIRMED
    print(f"[{Colors.GREEN}PASS{Colors.ENDC}] State Transition: PENDING -> CONFIRMED verified")

    # Re-confirming should fail
    reconfirm_res = confirm_uc.execute(created.id)
    assert not reconfirm_res.is_success
    print(f"[{Colors.GREEN}PASS{Colors.ENDC}] Business Rule: Idempotency / Double confirmation prevented")
    print(f"{Colors.CYAN}{Colors.BOLD}All architecture assertions passed successfully!{Colors.ENDC}\n")

if __name__ == '__main__':
    # If run in non-interactive terminal (e.g. CI or automated runner), run self-test then exit
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        r = InMemoryOrderRepository()
        run_verification_test(r, CreateOrderUseCase(r), ConfirmOrderUseCase(r))
    else:
        interactive_loop()

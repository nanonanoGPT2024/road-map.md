#!/usr/bin/env python3
"""
Lab Hands-on: Hexagonal & Clean Architecture Simulator
Context: PHP Enterprise Architecture (Domain-Driven Design / Ports & Adapters)
Simulates core Clean Architecture layers:
  1. Domain (Entities, Value Objects, Domain Exceptions)
  2. Application (Use Cases, Inbound/Outbound Ports, DTOs)
  3. Infrastructure (Outbound Adapters: Storage, Payment, Notification)
  4. Presentation / Delivery (Inbound Adapters: CLI Controller / API Simulator)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import time
import uuid

# --- ANSI Formatting Helper ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

def print_header(title: str):
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} [LAYER] {title.upper()}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")

def print_step(actor: str, action: str):
    print(f"{TermColor.YELLOW}[{actor:20s}]{TermColor.RESET} -> {action}")

# ============================================================================
# 1. DOMAIN LAYER (Zero external dependencies, Pure Business Logic)
# ============================================================================

class DomainException(Exception):
    """Exception thrown when a business invariant is violated."""
    pass

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"

@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "USD"

    def __post_init__(self):
        if self.amount < 0:
            raise DomainException("Monetary value cannot be negative.")

@dataclass
class Order:
    """Core Domain Entity: Maintains invariants and state transitions."""
    order_id: str
    customer_id: str
    total: Money
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)

    def mark_as_paid(self) -> None:
        if self.status != OrderStatus.PENDING:
            raise DomainException(f"Cannot pay an order with status '{self.status}'.")
        self.status = OrderStatus.PAID

    def mark_as_failed(self) -> None:
        self.status = OrderStatus.FAILED

# ============================================================================
# 2. APPLICATION LAYER (Use Cases & Port Interfaces)
# ============================================================================

# --- DTOs (Data Transfer Objects) ---
@dataclass(frozen=True)
class CheckoutInputDTO:
    customer_id: str
    amount: float
    currency: str

@dataclass(frozen=True)
class CheckoutOutputDTO:
    order_id: str
    status: str
    amount: float
    currency: str
    timestamp: str

# --- Secondary Ports (Outbound Interfaces) ---
class OrderRepositoryPort(ABC):
    """Port for persistence operations."""
    @abstractmethod
    def save(self, order: Order) -> None:
        pass

    @abstractmethod
    def find_by_id(self, order_id: str) -> Order:
        pass

class PaymentGatewayPort(ABC):
    """Port for third-party payment processing."""
    @abstractmethod
    def charge(self, amount: Money, token: str) -> bool:
        pass

class NotificationPort(ABC):
    """Port for event notifications (e.g., Mailer, SMS, Webhook)."""
    @abstractmethod
    def notify_order_processed(self, order: Order) -> None:
        pass

# --- Primary Port / Use Case ---
class CheckoutUseCase:
    """
    Application Service (Orchestrator).
    Coordinates Domain Entities and driven ports without coupling to specific implementations.
    """
    def __init__(
        self,
        repository: OrderRepositoryPort,
        payment_gateway: PaymentGatewayPort,
        notification: NotificationPort
    ):
        self._repository = repository
        self._payment_gateway = payment_gateway
        self._notification = notification

    def execute(self, request: CheckoutInputDTO) -> CheckoutOutputDTO:
        # 1. Instantiate Domain Entity
        order_id = str(uuid.uuid4())[:8]
        order = Order(
            order_id=order_id,
            customer_id=request.customer_id,
            total=Money(amount=request.amount, currency=request.currency)
        )

        # 2. Persist initial pending state
        self._repository.save(order)

        # 3. Process payment through Outbound Port
        is_success = self._payment_gateway.charge(order.total, token="tok_sandbox_token")

        # 4. Enforce Domain state changes
        if is_success:
            order.mark_as_paid()
        else:
            order.mark_as_failed()

        # 5. Persist final state & dispatch notifications
        self._repository.save(order)
        self._notification.notify_order_processed(order)

        # 6. Return Application Output DTO
        return CheckoutOutputDTO(
            order_id=order.order_id,
            status=order.status.value,
            amount=order.total.amount,
            currency=order.total.currency,
            timestamp=order.created_at.isoformat()
        )

# ============================================================================
# 3. INFRASTRUCTURE LAYER (Adapters implementing Ports)
# ============================================================================

class InMemoryOrderRepository(OrderRepositoryPort):
    """Secondary Adapter: In-Memory / Cache / Database implementation."""
    def __init__(self):
        self._storage: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._storage[order.order_id] = order
        print_step("InMemoryRepository", f"Persisted Order #{order.order_id} [Status: {order.status.value}]")

    def find_by_id(self, order_id: str) -> Order:
        if order_id not in self._storage:
            raise KeyError(f"Order #{order_id} not found.")
        return self._storage[order_id]

class StripePaymentAdapter(PaymentGatewayPort):
    """Secondary Adapter: External Payment Gateway (Mocking PHP Stripe SDK)."""
    def charge(self, amount: Money, token: str) -> bool:
        print_step("StripePaymentAdapter", f"Calling Stripe API for {amount.currency} {amount.amount:.2f}...")
        # Simulate network latency
        time.sleep(0.05)
        # Business rule simulation: Payments over 1000 fail in test mode
        if amount.amount > 1000.0:
            print_step("StripePaymentAdapter", f"{TermColor.RED}Charge failed: Insufficient test funds.{TermColor.RESET}")
            return False
        print_step("StripePaymentAdapter", f"{TermColor.GREEN}Charge authorized successfully.{TermColor.RESET}")
        return True

class SmtpMailerAdapter(NotificationPort):
    """Secondary Adapter: Mailer Dispatcher (Mocking PHP SwiftMailer/Symfony Mailer)."""
    def notify_order_processed(self, order: Order) -> None:
        print_step(
            "SmtpMailerAdapter",
            f"Email sent to customer '{order.customer_id}' | Status: {order.status.value}"
        )

# ============================================================================
# 4. PRESENTATION / DELIVERY LAYER (Inbound Adapters & Composition Root)
# ============================================================================

class CliController:
    """Primary / Driving Adapter: Simulates a CLI command / PHP Artisan command."""
    def __init__(self, checkout_use_case: CheckoutUseCase):
        self._checkout_use_case = checkout_use_case

    def handle_request(self, payload_json: str):
        try:
            raw_data = json.loads(payload_json)
            dto = CheckoutInputDTO(
                customer_id=raw_data["customer_id"],
                amount=float(raw_data["amount"]),
                currency=raw_data.get("currency", "USD")
            )
            print_step("CliController", f"Request received for user '{dto.customer_id}'")
            response = self._checkout_use_case.execute(dto)
            print(f"\n{TermColor.GREEN}{TermColor.BOLD}>>> HTTP 200 OK / Output Response <<<{TermColor.RESET}")
            print(json.dumps(response.__dict__, indent=2))
        except DomainException as de:
            print(f"\n{TermColor.RED}{TermColor.BOLD}>>> DOMAIN INVARIANT ERROR (422) <<<{TermColor.RESET}")
            print(f"Error: {str(de)}")
        except Exception as e:
            print(f"\n{TermColor.RED}{TermColor.BOLD}>>> SYSTEM ERROR (500) <<<{TermColor.RESET}")
            print(f"Error: {str(e)}")

# ============================================================================
# RUNNABLE LAB EXECUTION
# ============================================================================

def main():
    print_header("Composition Root: Wiring Dependencies (IoC)")
    # WIRING (Inversion of Control container role)
    repository_adapter = InMemoryOrderRepository()
    payment_adapter = StripePaymentAdapter()
    mailer_adapter = SmtpMailerAdapter()

    # Injecting dependencies to Use Case
    use_case = CheckoutUseCase(
        repository=repository_adapter,
        payment_gateway=payment_adapter,
        notification=mailer_adapter
    )

    controller = CliController(checkout_use_case=use_case)

    # TEST CASE 1: Valid Checkout Scenario
    print_header("Scenario 1: Happy Path - Normal Order Execution")
    req_success = json.dumps({"customer_id": "cust_usr_99", "amount": 149.99, "currency": "USD"})
    controller.handle_request(req_success)

    # TEST CASE 2: Payment Failure (Infrastructure Gateway simulation)
    print_header("Scenario 2: Gateway Decline - Amount Exceeds Limits")
    req_failed = json.dumps({"customer_id": "cust_usr_100", "amount": 1500.00, "currency": "USD"})
    controller.handle_request(req_failed)

    # TEST CASE 3: Invariant Violation (Domain Validation triggered)
    print_header("Scenario 3: Domain Invariant Violation - Negative Value")
    req_invalid = json.dumps({"customer_id": "cust_usr_101", "amount": -25.50, "currency": "USD"})
    controller.handle_request(req_invalid)

    print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}Architectural Verification:{TermColor.RESET}")
    print(f"1. {TermColor.CYAN}Domain Layer{TermColor.RESET} remains pure, tested, and decoupled from framework libs.")
    print(f"2. {TermColor.CYAN}Use Cases{TermColor.RESET} only interact with abstract ports (Interfaces).")
    print(f"3. {TermColor.CYAN}Adapters{TermColor.RESET} can be swapped (e.g., Stripe -> PayPal, InMemory -> MySQL) without touching business logic.\n")

if __name__ == "__main__":
    main()
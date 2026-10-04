#!/usr/bin/env python3
"""
Lab Exercise: ASP.NET Core BAB-06 - Validation, Error Handling & Fault Tolerance Simulator
Simulasi teknis independen arsitektur ASP.NET Core:
  1. Model Validation (FluentValidation style + RFC 7807 ProblemDetails)
  2. Global Exception Handling Middleware (IExceptionHandler pipeline)
  3. Resilience & Fault Tolerance (Polly-like Retry, Exponential Backoff, Circuit Breaker, Fallback)
"""

import sys
import time
import random
import uuid
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Callable

# ==============================================================================
# ANSI Color Palette for Terminal Visualization
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GRAY = "\033[100m"

def banner(text: str) -> None:
    print(f"\n{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} >>> {text} <<<{Color.RESET}")
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}\n")

# ==============================================================================
# 1. Validation & RFC 7807 ProblemDetails
# ==============================================================================
@dataclass
class CreateOrderRequest:
    customer_id: str
    product_sku: str
    quantity: int
    unit_price: float
    idempotency_key: str

@dataclass
class ProblemDetails:
    type: str
    title: str
    status: int
    detail: str
    instance: str
    trace_id: str = field(default_factory=lambda: f"00-{uuid.uuid4().hex[:16]}-01")
    errors: Dict[str, List[str]] = field(default_factory=dict)

    def to_json(self) -> str:
        data = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "instance": self.instance,
            "traceId": self.trace_id
        }
        if self.errors:
            data["errors"] = self.errors
        return json.dumps(data, indent=2)

class OrderValidator:
    """Simulasi FluentValidation: AbstractValidator<CreateOrderRequest>"""
    def validate(self, req: CreateOrderRequest) -> Dict[str, List[str]]:
        errors: Dict[str, List[str]] = {}

        if not req.customer_id or not req.customer_id.strip():
            errors.setdefault("CustomerId", []).append("'CustomerId' must not be empty.")
        elif not req.customer_id.startswith("CUST-"):
            errors.setdefault("CustomerId", []).append("'CustomerId' must begin with 'CUST-'.")

        if not req.product_sku or len(req.product_sku) < 3:
            errors.setdefault("ProductSku", []).append("'ProductSku' length must be at least 3 characters.")

        if req.quantity <= 0:
            errors.setdefault("Quantity", []).append("'Quantity' must be strictly greater than 0.")
        elif req.quantity > 500:
            errors.setdefault("Quantity", []).append("'Quantity' cannot exceed maximum batch limit of 500.")

        if req.unit_price <= 0.0:
            errors.setdefault("UnitPrice", []).append("'UnitPrice' must be positive.")

        if not req.idempotency_key or len(req.idempotency_key) != 36:
            errors.setdefault("IdempotencyKey", []).append("'IdempotencyKey' must be a valid 36-char UUID.")

        return errors

# ==============================================================================
# 2. Custom Domain Exceptions & Global Middleware
# ==============================================================================
class DomainException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code

class InventoryDepletedException(DomainException):
    def __init__(self, sku: str):
        super().__init__(f"Stock for item '{sku}' is completely depleted.", status_code=409)

class DownstreamTimeoutException(Exception):
    def __init__(self, service: str):
        super().__init__(f"Remote call to '{service}' timed out after 3000ms.")

class GlobalExceptionHandlerMiddleware:
    """Simulasi UseExceptionHandler() / IExceptionHandler pipeline ASP.NET Core"""
    @staticmethod
    def handle(func: Callable[[], Any], instance_path: str) -> Any:
        try:
            return func()
        except DomainException as dex:
            problem = ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807#domain-error",
                title="Business Rule Violation",
                status=dex.status_code,
                detail=str(dex),
                instance=instance_path
            )
            print(f"{Color.RED}[Middleware] Intercepted DomainException (HTTP {dex.status_code}):{Color.RESET}")
            print(f"{Color.YELLOW}{problem.to_json()}{Color.RESET}\n")
            return None
        except Exception as ex:
            problem = ProblemDetails(
                type="https://tools.ietf.org/html/rfc7807#internal-server-error",
                title="An unhandled error occurred while processing your request.",
                status=500,
                detail=f"Unhandled internal failure: {str(ex)}",
                instance=instance_path
            )
            print(f"{Color.BG_RED}{Color.WHITE}[Middleware] Intercepted Unhandled Exception (HTTP 500):{Color.RESET}")
            print(f"{Color.RED}{problem.to_json()}{Color.RESET}\n")
            return None

# ==============================================================================
# 3. Fault Tolerance & Resilience Pipeline (Polly Simulation)
# ==============================================================================
class CircuitState(Enum):
    CLOSED = "CLOSED (Normal Traffic Allowed)"
    OPEN = "OPEN (Fast-Fail Active)"
    HALF_OPEN = "HALF_OPEN (Testing Canary Request)"

class CircuitBreakerOpenException(Exception):
    pass

class ResiliencePipeline:
    """Simulasi Polly v8 ResiliencePipeline: Retry with Jitter + Circuit Breaker + Fallback"""
    def __init__(self, max_retries: int = 3, failure_threshold: int = 3, break_duration: float = 3.0):
        self.max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.break_duration = break_duration
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def _update_state(self) -> None:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.break_duration:
                self.state = CircuitState.HALF_OPEN
                print(f"{Color.MAGENTA}[Polly CircuitBreaker] State Transition: OPEN -> HALF_OPEN (Canary trial enabled){Color.RESET}")

    def execute(self, action: Callable[[], Any], fallback: Optional[Callable[[], Any]] = None) -> Any:
        self._update_state()

        if self.state == CircuitState.OPEN:
            print(f"{Color.RED}[Polly CircuitBreaker] Circuit is OPEN! Request blocked immediately (Fast-Fail).{Color.RESET}")
            if fallback:
                print(f"{Color.CYAN}[Polly Fallback] Executing graceful fallback strategy...{Color.RESET}")
                return fallback()
            raise CircuitBreakerOpenException("Circuit Breaker is OPEN. Operation aborted.")

        attempt = 0
        while attempt <= self.max_retries:
            try:
                attempt += 1
                result = action()
                # If we succeeded in HALF_OPEN, reset back to CLOSED
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    print(f"{Color.GREEN}[Polly CircuitBreaker] Canary succeeded! State Transition: HALF_OPEN -> CLOSED{Color.RESET}")
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = 0
                return result

            except DownstreamTimeoutException as ex:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    print(f"{Color.BG_RED}{Color.WHITE}[Polly CircuitBreaker] Threshold reached ({self.failure_count}/{self.failure_threshold})! State Transition -> OPEN{Color.RESET}")

                if attempt > self.max_retries:
                    print(f"{Color.RED}[Polly Retry] Exhausted {self.max_retries} retries. Raising failure.{Color.RESET}")
                    if fallback:
                        print(f"{Color.CYAN}[Polly Fallback] Falling back to default backup cache/provider.{Color.RESET}")
                        return fallback()
                    raise ex

                # Exponential backoff with full jitter: delay = min(base * 2^(attempt-1), max) + jitter
                base_delay = 0.3 * (2 ** (attempt - 1))
                jitter = random.uniform(0.05, 0.15)
                total_delay = base_delay + jitter
                print(f"{Color.YELLOW}[Polly Retry] Attempt {attempt} failed: {ex}. Retrying in {total_delay:.2f}s (Backoff+Jitter)...{Color.RESET}")
                time.sleep(total_delay)

# ==============================================================================
# 4. Interactive Lab Scenarios
# ==============================================================================
resilience_engine = ResiliencePipeline(max_retries=2, failure_threshold=3, break_duration=3.5)
validator = OrderValidator()

def run_validation_demo(valid: bool = False):
    banner("Scenario 1: ASP.NET Core FluentValidation & ProblemDetails (RFC 7807)")
    if valid:
        req = CreateOrderRequest(
            customer_id="CUST-88291",
            product_sku="SKU-MICROSERVICES-NET9",
            quantity=12,
            unit_price=49.99,
            idempotency_key=str(uuid.uuid4())
        )
        print(f"{Color.CYAN}Submitting valid payload:{Color.RESET} {req}\n")
    else:
        req = CreateOrderRequest(
            customer_id="BAD_ID",
            product_sku="X",
            quantity=-5,
            unit_price=-10.0,
            idempotency_key="invalid-key"
        )
        print(f"{Color.CYAN}Submitting invalid payload:{Color.RESET} {req}\n")

    errors = validator.validate(req)
    if errors:
        problem = ProblemDetails(
            type="https://tools.ietf.org/html/rfc7231#section-6.5.1",
            title="One or more validation errors occurred.",
            status=400,
            detail="See the errors field for details.",
            instance="/api/v1/orders",
            errors=errors
        )
        print(f"{Color.RED}[ASP.NET Core ModelBinding Filter] Validation Failed (HTTP 400 Bad Request):{Color.RESET}")
        print(f"{Color.YELLOW}{problem.to_json()}{Color.RESET}")
    else:
        print(f"{Color.GREEN}[Validation Success] Model is valid. Proceeding to Controller Action!{Color.RESET}")

def run_exception_middleware_demo(scenario_type: str = "domain"):
    banner("Scenario 2: Global Exception Handling Middleware Pipeline")
    instance = "/api/v1/orders/ORD-99120/checkout"

    def faulty_action():
        if scenario_type == "domain":
            raise InventoryDepletedException("SKU-MICROSERVICES-NET9")
        elif scenario_type == "null_ref":
            # Simulate unexpected bug (NullReferenceException equivalent)
            dummy: Optional[dict] = None
            return dummy["non_existent_key"]  # type: ignore
        return "OK"

    print(f"Executing request through ASP.NET Core Middleware Pipeline (Scenario: {scenario_type})...")
    GlobalExceptionHandlerMiddleware.handle(faulty_action, instance)

def run_resilience_demo():
    banner("Scenario 3: Polly Fault Tolerance (Retry + Jitter -> Circuit Breaker -> Fallback)")

    downstream_health = {"failures_remaining": 6}

    def remote_payment_gateway():
        if downstream_health["failures_remaining"] > 0:
            downstream_health["failures_remaining"] -= 1
            raise DownstreamTimeoutException("PaymentGateway-StripeSim")
        return {"payment_status": "APPROVED", "transaction_id": "TXN-" + uuid.uuid4().hex[:8]}

    def payment_fallback():
        return {"payment_status": "QUEUED_OFFLINE", "note": "Accepted into dead-letter replay queue for eventual consistency"}

    print(f"{Color.BOLD}Simulating bursts of requests against flaky downstream service...{Color.RESET}\n")

    for i in range(1, 6):
        print(f"{Color.WHITE}{Color.BOLD}>>> Request #{i} Dispatch <<<{Color.RESET}")
        res = GlobalExceptionHandlerMiddleware.handle(
            lambda: resilience_engine.execute(remote_payment_gateway, fallback=payment_fallback),
            f"/api/v1/payments/batch/{i}"
        )
        if res:
            print(f"{Color.GREEN}Result: {res}{Color.RESET}\n")
        time.sleep(0.5)

    print(f"{Color.CYAN}Cooling down for 4.0s to allow Circuit Breaker transition to HALF_OPEN...{Color.RESET}")
    time.sleep(4.0)

    print(f"{Color.WHITE}{Color.BOLD}>>> Canary Request #6 Dispatch (Downstream recovered) <<<{Color.RESET}")
    res = GlobalExceptionHandlerMiddleware.handle(
        lambda: resilience_engine.execute(remote_payment_gateway, fallback=payment_fallback),
        "/api/v1/payments/batch/6"
    )
    if res:
        print(f"{Color.GREEN}Result: {res}{Color.RESET}\n")

def interactive_menu():
    while True:
        banner("ASP.NET Core BAB-06: Interactive Terminal Lab")
        print(f"{Color.BOLD}Pilihan Simulasi:{Color.RESET}")
        print(f" {Color.CYAN}1.{Color.RESET} Validasi Model Gagal (RFC 7807 ProblemDetails 400)")
        print(f" {Color.CYAN}2.{Color.RESET} Validasi Model Berhasil")
        print(f" {Color.CYAN}3.{Color.RESET} Domain Exception Handled by Middleware (HTTP 409 Conflict)")
        print(f" {Color.CYAN}4.{Color.RESET} Unhandled Exception Handled by Middleware (HTTP 500 Internal)")
        print(f" {Color.CYAN}5.{Color.RESET} Simulasi Polly Resilience (Retry, Jitter, Circuit Breaker, Fallback)")
        print(f" {Color.CYAN}6.{Color.RESET} Jalankan Seluruh Skenario Otomatis (Full Verification)")
        print(f" {Color.RED}0.{Color.RESET} Keluar (Exit)\n")

        try:
            choice = input(f"{Color.YELLOW}Masukkan nomor opsi [0-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            run_validation_demo(valid=False)
        elif choice == "2":
            run_validation_demo(valid=True)
        elif choice == "3":
            run_exception_middleware_demo(scenario_type="domain")
        elif choice == "4":
            run_exception_middleware_demo(scenario_type="null_ref")
        elif choice == "5":
            run_resilience_demo()
        elif choice == "6":
            run_validation_demo(valid=False)
            run_validation_demo(valid=True)
            run_exception_middleware_demo(scenario_type="domain")
            run_exception_middleware_demo(scenario_type="null_ref")
            run_resilience_demo()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan simulasi ASP.NET Core BAB-06.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-6.{Color.RESET}")

if __name__ == "__main__":
    # If run in non-interactive / CI / piped environment, execute full suite
    if not sys.stdin.isatty():
        banner("Running Non-Interactive Autonomous ASP.NET Core Verification Suite")
        run_validation_demo(valid=False)
        run_validation_demo(valid=True)
        run_exception_middleware_demo(scenario_type="domain")
        run_exception_middleware_demo(scenario_type="null_ref")
        run_resilience_demo()
    else:
        interactive_menu()

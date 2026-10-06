#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur Enterprise Microservices & Distributed Systems
Topik: Service Registry (Eureka Pattern), API Gateway, Circuit Breaker, dan Distributed Tracing (Correlation ID).
"""

import sys
import time
import uuid
import random
from typing import Dict, Any, Optional, List

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"


class ServiceInstance:
    """Representasi satu instance microservice yang terdaftar di Discovery Server."""
    def __init__(self, service_id: str, host: str, port: int):
        self.service_id = service_id
        self.host = host
        self.port = port
        self.healthy = True
        self.failure_rate = 0.0

    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"


class ServiceRegistry:
    """Simulasi Eureka / Consul Service Registry."""
    def __init__(self):
        self._registry: Dict[str, List[ServiceInstance]] = {}

    def register(self, service_name: str, instance: ServiceInstance) -> None:
        if service_name not in self._registry:
            self._registry[service_name] = []
        self._registry[service_name].append(instance)
        print(f"{GRAY}[Registry]{RESET} Registered {CYAN}{service_name}{RESET} -> {instance.endpoint()}")

    def discover(self, service_name: str) -> Optional[ServiceInstance]:
        instances = [i for i in self._registry.get(service_name, []) if i.healthy]
        if not instances:
            return None
        # Simple Round-Robin / Random Load Balancer
        return random.choice(instances)


class CircuitBreakerOpenException(Exception):
    """Exception yang dilempar saat Circuit Breaker berstatus OPEN."""
    pass


class CircuitBreaker:
    """Simulasi Resilience4j Circuit Breaker (CLOSED, OPEN, HALF-OPEN)."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, failure_threshold: int = 3, reset_timeout_sec: float = 3.0):
        self.name = name
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout_sec = reset_timeout_sec
        self.last_failure_time = 0.0

    def execute(self, func, *args, **kwargs) -> Any:
        now = time.time()
        if self.state == self.OPEN:
            if now - self.last_failure_time > self.reset_timeout_sec:
                self.state = self.HALF_OPEN
                print(f"{YELLOW}[CircuitBreaker:{self.name}]{RESET} State transitioned to {BOLD}{self.HALF_OPEN}{RESET}")
            else:
                raise CircuitBreakerOpenException(f"Circuit Breaker [{self.name}] is OPEN. Fast-failing request.")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as ex:
            self._on_failure()
            raise ex

    def _on_success(self) -> None:
        if self.state == self.HALF_OPEN:
            print(f"{GREEN}[CircuitBreaker:{self.name}]{RESET} Canary request succeeded! Transitioning to {BOLD}{self.CLOSED}{RESET}")
            self.state = self.CLOSED
            self.failure_count = 0
        elif self.state == self.CLOSED and self.failure_count > 0:
            self.failure_count = 0

    def _on_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        print(f"{RED}[CircuitBreaker:{self.name}]{RESET} Failure #{self.failure_count} recorded.")
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            print(f"{RED}{BOLD}[CircuitBreaker:{self.name}] THRESHOLD REACHED -> State is now OPEN!{RESET}")


class OrderService:
    """Business microservice: Order Management."""
    def create_order(self, trace_id: str, order_id: str, amount: float) -> Dict[str, Any]:
        time.sleep(0.05)
        return {
            "status": "CREATED",
            "order_id": order_id,
            "amount": amount,
            "trace_id": trace_id
        }


class PaymentService:
    """Downstream microservice: Payment Processing."""
    def __init__(self, failure_probability: float = 0.0):
        self.failure_probability = failure_probability

    def process_payment(self, trace_id: str, order_id: str, amount: float) -> Dict[str, Any]:
        time.sleep(0.08)
        if random.random() < self.failure_probability:
            raise ConnectionError(f"Downstream payment gateway timeout for order {order_id}")
        return {
            "status": "PAID",
            "order_id": order_id,
            "transaction_id": f"txn-{uuid.uuid4().hex[:8]}",
            "amount": amount,
            "trace_id": trace_id
        }


class ApiGateway:
    """Simulasi Spring Cloud Gateway dengan Distributed Tracing & Resilience."""
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.order_service = OrderService()
        self.payment_service = PaymentService(failure_probability=0.0)
        self.payment_cb = CircuitBreaker("PaymentServiceCB", failure_threshold=3, reset_timeout_sec=2.5)

    def set_payment_failure_rate(self, rate: float) -> None:
        self.payment_service.failure_probability = rate

    def handle_checkout(self, order_id: str, amount: float) -> Dict[str, Any]:
        # Generate W3C / OpenTelemetry Trace ID
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        print(f"\n{BOLD}{BLUE}--> [Gateway] Incoming Request:{RESET} POST /api/v1/checkout (TraceID: {MAGENTA}{trace_id}{RESET})")

        # 1. Step 1: Order Service Call
        order_res = self.order_service.create_order(trace_id, order_id, amount)
        print(f"  {GREEN}✔{RESET} OrderService: Order {order_id} created successfully.")

        # 2. Step 2: Payment Service Call via Circuit Breaker
        try:
            payment_res = self.payment_cb.execute(
                self.payment_service.process_payment, trace_id, order_id, amount
            )
            print(f"  {GREEN}✔{RESET} PaymentService: Transaksi sukses ({payment_res['transaction_id']}).")
            return {
                "statusCode": 200,
                "traceId": trace_id,
                "order": order_res,
                "payment": payment_res,
                "circuitBreakerState": self.payment_cb.state
            }
        except (CircuitBreakerOpenException, ConnectionError) as err:
            # Fallback strategy (Graceful Degradation)
            print(f"  {YELLOW}⚠{RESET} PaymentService Failed: {err}")
            print(f"  {CYAN}⚡ Fallback triggered:{RESET} Order queued as PENDING_PAYMENT.")
            return {
                "statusCode": 202,
                "traceId": trace_id,
                "order": order_res,
                "payment": {"status": "PENDING_OFFLINE_PROCESSING"},
                "circuitBreakerState": self.payment_cb.state,
                "fallbackApplied": True
            }


def display_header() -> None:
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{BOLD}{GREEN}  LAB EXERCISE: Enterprise Microservices & Distributed Architecture     {RESET}")
    print(f"{BOLD}{GRAY}  Simulasi Resilience4j, Discovery Registry, & Distributed Tracing      {RESET}")
    print(f"{BOLD}{CYAN}========================================================================={RESET}")


def run_interactive_simulation() -> None:
    display_header()
    registry = ServiceRegistry()
    registry.register("order-service", ServiceInstance("order-service-1", "10.0.1.15", 8081))
    registry.register("payment-service", ServiceInstance("payment-service-1", "10.0.1.20", 8082))
    registry.register("payment-service", ServiceInstance("payment-service-2", "10.0.1.21", 8082))

    gateway = ApiGateway(registry)

    print(f"\n{BOLD}Skenario 1: Lalu Lintas Normal (Semua Layanan Sehat){RESET}")
    for i in range(1, 4):
        gateway.handle_checkout(f"ORD-100{i}", 150_000.0 * i)
        time.sleep(0.1)

    print(f"\n{BOLD}{RED}Skenario 2: Terjadi Gangguan Jaringan pada Payment Service (Failure Rate 100%){RESET}")
    gateway.set_payment_failure_rate(1.0)
    for i in range(4, 8):
        res = gateway.handle_checkout(f"ORD-100{i}", 200_000.0)
        print(f"  HTTP Response: {res['statusCode']} | CB State: {res['circuitBreakerState']}")
        time.sleep(0.1)

    print(f"\n{BOLD}{YELLOW}Skenario 3: Fast-Fail Circuit Breaker (Layanan diblokir langsung tanpa timeout){RESET}")
    res = gateway.handle_checkout("ORD-1008", 500_000.0)
    print(f"  HTTP Response: {res['statusCode']} | CB State: {res['circuitBreakerState']}")

    print(f"\n{BOLD}{CYAN}Skenario 4: Self-Healing / Pemulihan Layanan (Half-Open Probe){RESET}")
    print(f"{GRAY}Menunggu 3 detik agar reset timeout tercapai...{RESET}")
    time.sleep(3.0)
    gateway.set_payment_failure_rate(0.0)
    res = gateway.handle_checkout("ORD-1009", 120_000.0)
    print(f"  HTTP Response: {res['statusCode']} | CB State: {res['circuitBreakerState']}")

    print(f"\n{BOLD}{GREEN}✔ Seluruh simulasi Microservices & Distributed Patterns selesai dengan sukses!{RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()

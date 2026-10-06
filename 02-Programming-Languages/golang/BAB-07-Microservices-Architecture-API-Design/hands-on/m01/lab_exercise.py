#!/usr/bin/env python3
"""
Lab Exercise M01: Microservices Architecture & API Design Patterns
Simulasi Teknis Fondasi Arsitektur Microservices, API Gateway, Circuit Breaker,
Service Discovery, dan Distributed Tracing (Go-Idiomatic Patterns in Python 3).
"""

import sys
import time
import random
import uuid
from typing import Dict, List, Optional, Tuple

# ANSI Terminal Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"


class ServiceRegistry:
    """Simulasi Service Discovery (seperti HashiCorp Consul / Etcd di ekosistem Go)."""
    def __init__(self):
        self.instances: Dict[str, List[str]] = {}

    def register(self, service_name: str, endpoint: str):
        if service_name not in self.instances:
            self.instances[service_name] = []
        if endpoint not in self.instances[service_name]:
            self.instances[service_name].append(endpoint)
            print(f"{GREEN}[Discovery]{RESET} Registered {BOLD}{service_name}{RESET} -> {endpoint}")

    def discover(self, service_name: str) -> Optional[str]:
        endpoints = self.instances.get(service_name, [])
        if not endpoints:
            return None
        # Client-side load balancing: Random selection
        return random.choice(endpoints)


class CircuitBreaker:
    """
    Simulasi Circuit Breaker Pattern (seperti sony/gobreaker di Go):
    State: CLOSED -> OPEN -> HALF-OPEN
    """
    def __init__(self, failure_threshold: int = 3, recovery_time: float = 2.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = time.time()

    def before_request(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change > self.recovery_time:
                self.state = "HALF-OPEN"
                self.last_state_change = now
                print(f"{YELLOW}[CircuitBreaker]{RESET} Timeout elapsed. State transition -> {BOLD}HALF-OPEN{RESET}")
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        if self.state != "CLOSED":
            print(f"{GREEN}[CircuitBreaker]{RESET} Success observed! State transition -> {BOLD}CLOSED{RESET}")
            self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        print(f"{RED}[CircuitBreaker]{RESET} Failure recorded ({self.failure_count}/{self.failure_threshold})")
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_state_change = time.time()
            print(f"{RED}{BOLD}[CircuitBreaker] THRESHOLD EXCEEDED! State transition -> OPEN (Tripped){RESET}")


class MicroserviceNode:
    """Mock Microservice backend yang memproses RPC dengan simulasi latency & error."""
    def __init__(self, name: str, endpoint: str, failure_rate: float = 0.0):
        self.name = name
        self.endpoint = endpoint
        self.failure_rate = failure_rate

    def handle_request(self, trace_id: str, span_id: str, action: str) -> Tuple[int, str]:
        child_span_id = uuid.uuid4().hex[:8]
        print(f"  {CYAN}--> [{self.name}@{self.endpoint}]{RESET} Executing action '{action}'")
        print(f"      {MAGENTA}TraceContext{RESET}: trace_id={trace_id} span_id={span_id} -> child_span={child_span_id}")
        
        # Simulate execution processing
        time.sleep(0.08)
        
        if random.random() < self.failure_rate:
            return 500, f"Internal error in {self.name}"
        return 200, f"Success from {self.name} ({action})"


class APIGateway:
    """Simulasi API Gateway (Reverse Proxy, Correlation ID Injection, & Resiliency)."""
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(self, service_name: str) -> CircuitBreaker:
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(failure_threshold=3, recovery_time=2.0)
        return self.circuit_breakers[service_name]

    def route_request(self, service_name: str, action: str, mock_nodes: Dict[str, MicroserviceNode]):
        trace_id = uuid.uuid4().hex[:16]
        gateway_span_id = uuid.uuid4().hex[:8]
        
        print(f"\n{BOLD}{BLUE}[API Gateway]{RESET} Incoming request for service: {BOLD}{service_name}{RESET} | Action: {action}")
        print(f"  {MAGENTA}Generated X-Trace-ID:{RESET} {trace_id} | {MAGENTA}Gateway-Span:{RESET} {gateway_span_id}")

        breaker = self.get_breaker(service_name)
        if not breaker.before_request():
            print(f"  {RED}{BOLD}[FAST-FAIL 503]{RESET} Request rejected by Circuit Breaker (State: {breaker.state})")
            return

        endpoint = self.registry.discover(service_name)
        if not endpoint:
            print(f"  {RED}[404 Not Found]{RESET} No healthy instances found in Service Registry!")
            return

        node = mock_nodes.get(endpoint)
        if not node:
            print(f"  {RED}[502 Bad Gateway]{RESET} Unreachable node {endpoint}")
            return

        status, response = node.handle_request(trace_id, gateway_span_id, action)
        if status == 200:
            breaker.record_success()
            print(f"  {GREEN}[HTTP 200 OK]{RESET} Gateway received: {response}")
        else:
            breaker.record_failure()
            print(f"  {RED}[HTTP {status} ERROR]{RESET} Gateway received: {response}")


def print_banner():
    banner = f"""
{CYAN}========================================================================={RESET}
{BOLD}{GREEN}  LAB EXERCISE M01: MICROSERVICES ARCHITECTURE & API DESIGN PATTERNS{RESET}
{YELLOW}  Golang Backend Systems: Discovery, Resiliency, Tracing & Protocols{RESET}
{CYAN}========================================================================={RESET}
"""
    print(banner)


def run_interactive_simulation():
    print_banner()

    # Step 1: Initialize Infrastructure
    print(f"{BOLD}[Step 1] Menginisialisasi Service Registry & Instances...{RESET}")
    registry = ServiceRegistry()
    registry.register("order-service", "10.0.1.10:8080")
    registry.register("order-service", "10.0.1.11:8080")
    registry.register("payment-service", "10.0.2.20:9090")
    registry.register("inventory-service", "10.0.3.30:9090")

    nodes = {
        "10.0.1.10:8080": MicroserviceNode("Order-Node-1", "10.0.1.10:8080", failure_rate=0.0),
        "10.0.1.11:8080": MicroserviceNode("Order-Node-2", "10.0.1.11:8080", failure_rate=0.0),
        "10.0.2.20:9090": MicroserviceNode("Payment-Node-1", "10.0.2.20:9090", failure_rate=0.75),
        "10.0.3.30:9090": MicroserviceNode("Inventory-Node-1", "10.0.3.30:9090", failure_rate=0.0),
    }

    gateway = APIGateway(registry)

    while True:
        print(f"\n{BOLD}{WHITE}--- PILIHAN SIMULASI MICROSERVICES ---{RESET}")
        print(f"{GREEN}1.{RESET} Dispatch Healthy Request (order-service: CreateOrder)")
        print(f"{GREEN}2.{RESET} Test Circuit Breaker Trip & Fast-Fail (payment-service: ChargePayment)")
        print(f"{GREEN}3.{RESET} Bandingkan Payload Overhead (gRPC Protobuf vs REST JSON)")
        print(f"{GREEN}4.{RESET} Tampilkan Service Topology & Status Circuit Breaker")
        print(f"{RED}0.{RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}Pilih nomor skenario [0-4]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan oleh user.{RESET}")
            break

        if choice == "1":
            gateway.route_request("order-service", "POST /v1/orders", nodes)
        elif choice == "2":
            print(f"\n{YELLOW}Mengirim rentetan request ke payment-service (Tingkat error 75%)...{RESET}")
            for i in range(1, 6):
                print(f"\n-- Request #{i} --")
                gateway.route_request("payment-service", "POST /v1/payments/charge", nodes)
                time.sleep(0.3)
            print(f"\n{YELLOW}Menunggu recovery timeout (2 detik) untuk menguji mode HALF-OPEN...{RESET}")
            time.sleep(2.1)
            print(f"\n-- Request Pasca-Recovery --")
            gateway.route_request("payment-service", "POST /v1/payments/charge", nodes)
        elif choice == "3":
            print(f"\n{CYAN}{BOLD}[Benchmark Protokol: gRPC vs REST/JSON]{RESET}")
            sample_order = {
                "order_id": "ord_9988221100",
                "customer_id": "cust_123456",
                "items": [{"sku": f"SKU-{i}", "qty": 2, "price": 150000} for i in range(5)],
                "total_amount": 1500000,
                "status": "PENDING_CONFIRMATION"
            }
            json_payload = str(sample_order).encode("utf-8")
            # Simulasi Protobuf binary wire serialization (~40% compact)
            protobuf_wire_simulated = b"\x08\x96\x01\x12\x0eord_9988221100" + b"\x1a" * 80
            
            print(f"  * REST JSON Payload Size     : {BOLD}{len(json_payload)} bytes{RESET}")
            print(f"  * gRPC Protobuf Payload Size : {BOLD}{len(protobuf_wire_simulated)} bytes{RESET}")
            savings = (1 - (len(protobuf_wire_simulated) / len(json_payload))) * 100
            print(f"  * {GREEN}Efisiensi Bandwidth gRPC  : ~{savings:.1f}% penghematan wire format!{RESET}")
            print(f"  * Keunggulan Go: HTTP/2 Multiplexing, Strict Typings (.pb.go), Streaming gRPC.")
        elif choice == "4":
            print(f"\n{CYAN}{BOLD}[Service Registry & Circuit Breaker Dashboard]{RESET}")
            for svc, endpoints in registry.instances.items():
                breaker = gateway.circuit_breakers.get(svc)
                state_str = f"{GREEN}CLOSED{RESET}" if not breaker or breaker.state == "CLOSED" else f"{RED}{breaker.state}{RESET}"
                print(f"  • Service: {BOLD}{svc:<18}{RESET} | Nodes: {len(endpoints):<2} | Breaker: {state_str}")
                for ep in endpoints:
                    print(f"     └─ Endpoint: {ep}")
        elif choice == "0":
            print(f"{GREEN}Simulasi selesai. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-4.{RESET}")


if __name__ == "__main__":
    run_interactive_simulation()

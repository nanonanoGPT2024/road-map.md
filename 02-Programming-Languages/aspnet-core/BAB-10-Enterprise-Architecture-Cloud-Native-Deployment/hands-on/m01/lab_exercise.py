#!/usr/bin/env python3
"""
Lab Exercise M01: Enterprise Architecture & Cloud-Native Deployment Simulator
Topik: ASP.NET Core Clean Architecture, CQRS/MediatR Pipeline, Health Checks & Resiliency
"""

import sys
import time
import uuid
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_DIM = "\033[2m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
 .NET ENTERPRISE CLOUD-NATIVE ARCHITECTURE LAB SIMULATOR
 BAB 10: Clean Architecture | CQRS/MediatR | Cloud-Native Health & Resiliency
================================================================================{CLR_RESET}
"""
    print(banner)


# -----------------------------------------------------------------------------
# 1. DOMAIN & CQRS APPLICATION ABSTRACTIONS
# -----------------------------------------------------------------------------

@dataclass
class CreateOrderCommand:
    order_id: str
    customer_id: str
    amount: float
    items: List[str]


@dataclass
class DomainEvent:
    event_id: str
    event_name: str
    timestamp: float
    payload: Dict[str, Any]


class PipelineBehavior:
    """Simulasi MediatR IPipelineBehavior<TRequest, TResponse>"""
    def __init__(self, name: str):
        self.name = name

    def execute(self, command: Any, next_step: Callable[[], Any]) -> Any:
        raise NotImplementedError


class LoggingBehavior(PipelineBehavior):
    def __init__(self):
        super().__init__("LoggingBehavior")

    def execute(self, command: Any, next_step: Callable[[], Any]) -> Any:
        print(f"  {CLR_DIM}[MediatR Pipeline] Entering {self.name} -> Handling {command.__class__.__name__}{CLR_RESET}")
        start = time.perf_counter()
        result = next_step()
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  {CLR_DIM}[MediatR Pipeline] Exiting {self.name} -> Completed in {elapsed:.2f}ms{CLR_RESET}")
        return result


class ValidationBehavior(PipelineBehavior):
    def __init__(self):
        super().__init__("ValidationBehavior (FluentValidation)")

    def execute(self, command: Any, next_step: Callable[[], Any]) -> Any:
        print(f"  {CLR_DIM}[MediatR Pipeline] Entering {self.name} -> Validating invariants...{CLR_RESET}")
        if isinstance(command, CreateOrderCommand):
            if command.amount <= 0:
                raise ValueError("Validation failed: Order amount must be positive!")
            if not command.items:
                raise ValueError("Validation failed: Order items cannot be empty!")
        print(f"  {CLR_GREEN}✓ Validation passed successfully{CLR_RESET}")
        return next_step()


class TransactionalOutboxBehavior(PipelineBehavior):
    def __init__(self, outbox_storage: List[Dict[str, Any]]):
        super().__init__("TransactionalOutboxBehavior")
        self.outbox = outbox_storage

    def execute(self, command: Any, next_step: Callable[[], Any]) -> Any:
        print(f"  {CLR_DIM}[MediatR Pipeline] Entering {self.name} -> Transaction scope started{CLR_RESET}")
        result = next_step()
        # Stage outbox message atomically with business transaction
        outbox_msg = {
            "Id": str(uuid.uuid4()),
            "Type": f"{command.__class__.__name__}.Executed",
            "Data": str(command),
            "CreatedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ProcessedUtc": None,
            "Status": "Enqueued"
        }
        self.outbox.append(outbox_msg)
        print(f"  {CLR_MAGENTA}⚡ [Outbox Pattern] Staged transactional event {outbox_msg['Id'][:8]} to local DB{CLR_RESET}")
        return result


# -----------------------------------------------------------------------------
# 2. RESILIENCE: POLLY CIRCUIT BREAKER SIMULATOR
# -----------------------------------------------------------------------------

class CircuitState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Simulasi Polly Circuit Breaker Policy"""
    def __init__(self, failure_threshold: int = 3, reset_timeout_sec: float = 3.0):
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def execute(self, action: Callable[[], Any]) -> Any:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                print(f"  {CLR_YELLOW}[CircuitBreaker] Timeout elapsed. State transition -> HALF_OPEN (Trial call){CLR_RESET}")
            else:
                remaining = self.reset_timeout - (now - self.last_failure_time)
                raise RuntimeError(f"CircuitBreaker is OPEN! Call rejected instantly. Retry in {remaining:.1f}s")

        try:
            result = action()
            if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                print(f"  {CLR_GREEN}[CircuitBreaker] Trial succeeded! State transition -> CLOSED (Healthy){CLR_RESET}")
            return result
        except Exception as ex:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.threshold or self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                print(f"  {CLR_RED}[CircuitBreaker] Threshold reached ({self.failure_count} failures)! State -> OPEN (Trip breaker){CLR_RESET}")
            raise ex


# -----------------------------------------------------------------------------
# 3. KUBERNETES & CLOUD-NATIVE HEALTH CHECKS
# -----------------------------------------------------------------------------

class HealthCheckService:
    """Simulasi ASP.NET Core IHealthCheckService & Kubernetes Probes"""
    def __init__(self):
        self.db_connected = True
        self.redis_connected = True
        self.disk_space_ok = True
        self.warmup_completed = True

    def liveness_probe(self) -> Dict[str, Any]:
        """K8s /healthz/live: is the process running and not deadlocked?"""
        return {
            "status": "Healthy",
            "probe": "Liveness",
            "http_status": 200,
            "message": "Process is alive and responding"
        }

    def readiness_probe(self) -> Dict[str, Any]:
        """K8s /healthz/ready: is the pod ready to accept traffic?"""
        checks = {
            "Database": "Healthy" if self.db_connected else "Unhealthy",
            "RedisCache": "Healthy" if self.redis_connected else "Degraded",
            "DiskSpace": "Healthy" if self.disk_space_ok else "Unhealthy"
        }
        is_healthy = self.db_connected and self.disk_space_ok
        status = "Healthy" if is_healthy else ("Degraded" if self.redis_connected else "Unhealthy")
        http_code = 200 if is_healthy else 503
        return {
            "status": status,
            "probe": "Readiness",
            "http_status": http_code,
            "entries": checks
        }

    def startup_probe(self) -> Dict[str, Any]:
        """K8s /healthz/startup: has initialization finished?"""
        return {
            "status": "Healthy" if self.warmup_completed else "Starting",
            "probe": "Startup",
            "http_status": 200 if self.warmup_completed else 503
        }


# -----------------------------------------------------------------------------
# 4. INTERACTIVE SIMULATOR RUNNER
# -----------------------------------------------------------------------------

class EnterpriseLabRunner:
    def __init__(self):
        self.outbox_table: List[Dict[str, Any]] = []
        self.health_service = HealthCheckService()
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout_sec=4.0)
        self.setup_pipeline()

    def setup_pipeline(self):
        self.pipeline: List[PipelineBehavior] = [
            LoggingBehavior(),
            ValidationBehavior(),
            TransactionalOutboxBehavior(self.outbox_table)
        ]

    def dispatch_command(self, cmd: CreateOrderCommand):
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        print(f"\n{CLR_BLUE}[OpenTelemetry W3C TraceContext] TraceId: {trace_id} | SpanId: {span_id}{CLR_RESET}")

        def handler():
            print(f"  {CLR_CYAN}[CommandHandler] Executing OrderCommandHandler -> Order {cmd.order_id} saved!{CLR_RESET}")
            return {"status": "Created", "order_id": cmd.order_id, "amount": cmd.amount}

        # Build pipeline chain
        def build_chain(behaviors: List[PipelineBehavior], final_handler: Callable[[], Any]):
            if not behaviors:
                return final_handler
            current = behaviors[0]
            rest = behaviors[1:]
            return lambda: current.execute(cmd, build_chain(rest, final_handler))

        executor = build_chain(self.pipeline, handler)
        return executor()

    def simulate_downstream_dependency(self, fail_rate: float):
        if random.random() < fail_rate:
            raise ConnectionError("Remote payment gateway returned HTTP 504 Gateway Timeout")
        return "HTTP 200 OK: Payment Captured"

    def run_menu(self):
        while True:
            print("\n" + "=" * 60)
            print(f"{CLR_BOLD}ENTERPRISE ARCHITECTURE LAB MENU:{CLR_RESET}")
            print(f" {CLR_CYAN}1.{CLR_RESET} Simulasi CQRS Command & MediatR Pipeline (Clean Architecture)")
            print(f" {CLR_CYAN}2.{CLR_RESET} Test Kubernetes Probes (/healthz/live & /healthz/ready)")
            print(f" {CLR_CYAN}3.{CLR_RESET} Simulasi Resiliency: Circuit Breaker & Transient Faults (Polly)")
            print(f" {CLR_CYAN}4.{CLR_RESET} Review Transactional Outbox Staged Messages")
            print(f" {CLR_CYAN}5.{CLR_RESET} Toggle Infrastructure Status (Simulate DB Outage)")
            print(f" {CLR_CYAN}6.{CLR_RESET} Exit")
            print("=" * 60)

            choice = input(f"{CLR_YELLOW}Pilih opsi [1-6]: {CLR_RESET}").strip()

            if choice == "1":
                self.handle_cqrs_simulation()
            elif choice == "2":
                self.handle_health_check_simulation()
            elif choice == "3":
                self.handle_circuit_breaker_simulation()
            elif choice == "4":
                self.handle_outbox_review()
            elif choice == "5":
                self.handle_toggle_infra()
            elif choice == "6":
                print(f"\n{CLR_GREEN}Keluar dari simulator. Selamat belajar Enterprise Cloud-Native!{CLR_RESET}\n")
                sys.exit(0)
            else:
                print(f"{CLR_RED}Pilihan tidak valid! Masukkan angka 1 sampai 6.{CLR_RESET}")

    def handle_cqrs_simulation(self):
        print(f"\n{CLR_BOLD}--- SIMULASI CQRS COMMAND DISPATCH (MEDIATR) ---{CLR_RESET}")
        try:
            raw_amt = input("Masukkan nominal transaksi (default 150000): ").strip()
            amount = float(raw_amt) if raw_amt else 150000.0
        except ValueError:
            amount = 150000.0

        items_input = input("Masukkan nama item (pisahkan koma, default 'Book,Pen'): ").strip()
        items = [i.strip() for i in items_input.split(",")] if items_input else ["Book", "Pen"]

        cmd = CreateOrderCommand(
            order_id=f"ORD-{random.randint(1000, 9999)}",
            customer_id=f"CUST-{random.randint(10, 99)}",
            amount=amount,
            items=items
        )

        try:
            result = self.dispatch_command(cmd)
            print(f"\n{CLR_GREEN}{CLR_BOLD}HASIL: {result}{CLR_RESET}")
        except Exception as ex:
            print(f"\n{CLR_RED}{CLR_BOLD}PIPELINE EXCEPTION: {ex}{CLR_RESET}")

    def handle_health_check_simulation(self):
        print(f"\n{CLR_BOLD}--- KUBERNETES CONTAINER HEALTH PROBES ---{CLR_RESET}")
        liveness = self.health_service.liveness_probe()
        readiness = self.health_service.readiness_probe()

        live_color = CLR_GREEN if liveness['http_status'] == 200 else CLR_RED
        ready_color = CLR_GREEN if readiness['http_status'] == 200 else CLR_RED

        print(f"\n[GET /healthz/live] -> HTTP {live_color}{liveness['http_status']} {liveness['status']}{CLR_RESET}")
        print(f"  Detail: {liveness['message']}")

        print(f"\n[GET /healthz/ready] -> HTTP {ready_color}{readiness['http_status']} {readiness['status']}{CLR_RESET}")
        for check, res in readiness.get("entries", {}).items():
            c = CLR_GREEN if res == "Healthy" else (CLR_YELLOW if res == "Degraded" else CLR_RED)
            print(f"  - {check:<15}: {c}{res}{CLR_RESET}")

        if readiness['http_status'] == 503:
            print(f"\n{CLR_YELLOW}⚠️  K8s Service Router: Traffic dialihkan! Pod dikeluarkan dari EndpointSlice.{CLR_RESET}")
        else:
            print(f"\n{CLR_GREEN}✓ Pod terdaftar di Ingress / Service Mesh, siap menerima RPC & HTTP traffic.{CLR_RESET}")

    def handle_circuit_breaker_simulation(self):
        print(f"\n{CLR_BOLD}--- RESILIENCE: POLLY CIRCUIT BREAKER TEST ---{CLR_RESET}")
        print(f"State saat ini: {CLR_BOLD}{self.circuit_breaker.state}{CLR_RESET} | Failures: {self.circuit_breaker.failure_count}/{self.circuit_breaker.threshold}")
        print("Mengirim 5 panggilan beruntun ke payment gateway yang tidak stabil (70% kegagalan)...")

        for i in range(1, 6):
            time.sleep(0.4)
            print(f"\n[Call #{i}] Menghubungi payment gateway...", end=" ")
            try:
                res = self.circuit_breaker.execute(lambda: self.simulate_downstream_dependency(fail_rate=0.7))
                print(f"{CLR_GREEN}{res}{CLR_RESET}")
            except Exception as e:
                print(f"{CLR_RED}GAGAL -> {e}{CLR_RESET}")

    def handle_outbox_review(self):
        print(f"\n{CLR_BOLD}--- TRANSACTIONAL OUTBOX TABLE REVIEW ---{CLR_RESET}")
        if not self.outbox_table:
            print(f"{CLR_DIM}Belum ada pesan tersimpan di tabel Outbox.{CLR_RESET}")
            return

        print(f"Total outbox records: {len(self.outbox_table)}")
        print(f"{'Event ID':<10} | {'Status':<10} | {'Created At':<20} | {'Payload Type'}")
        print("-" * 65)
        for msg in self.outbox_table:
            st_color = CLR_YELLOW if msg["Status"] == "Enqueued" else CLR_GREEN
            print(f"{msg['Id'][:8]:<10} | {st_color}{msg['Status']:<10}{CLR_RESET} | {msg['CreatedAtUtc']:<20} | {msg['Type']}")

        flush = input(f"\nJalankan Outbox Background Publisher (simulate IHostedService)? (y/N): ").strip().lower()
        if flush == 'y':
            print(f"  {CLR_CYAN}[OutboxProcessor] Polling unpublished events...{CLR_RESET}")
            for msg in self.outbox_table:
                if msg["Status"] == "Enqueued":
                    time.sleep(0.2)
                    msg["Status"] = "Published"
                    msg["ProcessedUtc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    print(f"  {CLR_GREEN}✓ Event {msg['Id'][:8]} dipublish ke Kafka/RabbitMQ broker broker{CLR_RESET}")

    def handle_toggle_infra(self):
        print(f"\n{CLR_BOLD}--- SIMULASI KEGAGALAN INFRASTRUKTUR ---{CLR_RESET}")
        self.health_service.db_connected = not self.health_service.db_connected
        status_str = f"{CLR_GREEN}CONNECTED{CLR_RESET}" if self.health_service.db_connected else f"{CLR_RED}DISCONNECTED{CLR_RESET}"
        print(f"Status Database SQL Server diubah menjadi: {status_str}")


def main():
    print_banner()
    runner = EnterpriseLabRunner()
    try:
        runner.run_menu()
    except KeyboardInterrupt:
        print(f"\n\n{CLR_YELLOW}Eksekusi dibatalkan oleh pengguna.{CLR_RESET}\n")


if __name__ == "__main__":
    main()

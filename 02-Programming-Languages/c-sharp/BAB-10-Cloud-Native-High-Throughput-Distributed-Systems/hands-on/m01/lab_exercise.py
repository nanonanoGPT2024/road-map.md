#!/usr/bin/env python3
"""
Lab Exercise: Cloud-Native High-Throughput Distributed Systems (C# Architecture Simulation)
Bab 10: Cloud-Native High-Throughput Distributed Systems
Simulasi interaktif konsep:
  1. Microsoft Orleans Virtual Actor (Grain Lifecycle & State Turn-based Concurrency)
  2. Polly v8 Resilience Pipeline (Circuit Breaker, Rate Limiter & Hedging)
  3. Transactional Outbox Pattern (Transactional Safety & At-least-once Delivery)
  4. W3C Distributed Tracing (TraceId, SpanId, Context Propagation)
"""

import sys
import time
import random
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


def print_banner():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{BG_BLUE}  .NET CLOUD-NATIVE & HIGH-THROUGHPUT DISTRIBUTED SYSTEMS SIMULATOR   {RESET}")
    print(f"{CYAN}  Architectural Patterns: Orleans Actors | Polly v8 | Outbox | OpenTelemetry{RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")


# -----------------------------------------------------------------------------
# 1. OpenTelemetry W3C Distributed Tracing
# -----------------------------------------------------------------------------
@dataclass
class ActivityContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)

    def to_w3c_traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-01"


class DistributedTracer:
    @staticmethod
    def start_activity(name: str, parent: Optional[ActivityContext] = None) -> ActivityContext:
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        ctx = ActivityContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id if parent else None,
            baggage=dict(parent.baggage) if parent else {}
        )
        print(f"  {DIM}[OTel Activity]{RESET} {BOLD}{name}{RESET} -> TraceId: {CYAN}{ctx.trace_id[:8]}...{RESET} | SpanId: {YELLOW}{ctx.span_id}{RESET} | W3C: {DIM}{ctx.to_w3c_traceparent()}{RESET}")
        return ctx


# -----------------------------------------------------------------------------
# 2. Microsoft Orleans Virtual Actor (Grain) Simulation
# -----------------------------------------------------------------------------
class GrainState(Enum):
    UNLOADED = "Unloaded (Cold Storage)"
    ACTIVATED = "Activated (In-Memory Silo)"
    DEACTIVATING = "Deactivating"


class OrderGrain:
    """Simulates Microsoft Orleans IGrainWithGuidKey with Single-Threaded Execution Guarantee"""
    def __init__(self, grain_id: str):
        self.grain_id = grain_id
        self.state = GrainState.UNLOADED
        self.balance = 1000.0
        self.processed_transactions = 0

    def activate(self):
        if self.state != GrainState.ACTIVATED:
            print(f"    {MAGENTA}[Orleans Silo]{RESET} Hydrating Grain {BOLD}OrderGrain({self.grain_id}){RESET} from Persistent Storage...")
            time.sleep(0.3)
            self.state = GrainState.ACTIVATED
            print(f"    {GREEN}✓ Grain {self.grain_id} successfully activated on Silo Node #1.{RESET}")

    def execute_transaction(self, amount: float, ctx: ActivityContext) -> bool:
        self.activate()
        span = DistributedTracer.start_activity(f"OrderGrain.ExecuteTransaction({self.grain_id})", ctx)
        if self.balance >= amount:
            self.balance -= amount
            self.processed_transactions += 1
            print(f"    {GREEN}[Grain Turn Success]{RESET} Debited: {YELLOW}${amount:.2f}{RESET} | New Balance: {GREEN}${self.balance:.2f}{RESET} | Total Tx: {self.processed_transactions}")
            return True
        else:
            print(f"    {RED}[Grain Turn Rejected]{RESET} Insufficient balance: requested ${amount:.2f}, available ${self.balance:.2f}")
            return False


# -----------------------------------------------------------------------------
# 3. Polly v8 Resilience Pipeline (Circuit Breaker + Rate Limiter)
# -----------------------------------------------------------------------------
class CircuitState(Enum):
    CLOSED = "CLOSED (Normal Operation)"
    OPEN = "OPEN (Failing Fast)"
    HALF_OPEN = "HALF_OPEN (Testing Canary)"


class PollyResiliencePipeline:
    def __init__(self, failure_threshold: int = 3, break_duration_sec: float = 2.0):
        self.failure_threshold = failure_threshold
        self.break_duration_sec = break_duration_sec
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def execute(self, action_name: str, target_func):
        current_time = time.time()

        # Check circuit state transitions
        if self.state == CircuitState.OPEN:
            if current_time - self.last_state_change >= self.break_duration_sec:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = current_time
                print(f"    {YELLOW}[Polly CircuitBreaker]{RESET} Timeout expired. State transitioned to: {BOLD}{YELLOW}HALF-OPEN{RESET}")
            else:
                remaining = self.break_duration_sec - (current_time - self.last_state_change)
                print(f"    {RED}[Polly CircuitBreaker OPEN]{RESET} Short-circuiting call to '{action_name}'. Fail-fast active ({remaining:.1f}s remaining).")
                return False

        try:
            success = target_func()
            if success:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    print(f"    {GREEN}[Polly CircuitBreaker]{RESET} Canary succeeded! Circuit transitioned to: {BOLD}{GREEN}CLOSED{RESET}")
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = max(0, self.failure_count - 1)
                return True
            else:
                self._handle_failure(action_name)
                return False
        except Exception as ex:
            print(f"    {RED}[Polly Exception Caught]{RESET} {ex}")
            self._handle_failure(action_name)
            return False

    def _handle_failure(self, action_name: str):
        self.failure_count += 1
        print(f"    {RED}[Polly Pipeline Metric]{RESET} Failure recorded ({self.failure_count}/{self.failure_threshold}) for '{action_name}'")
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            print(f"    {BOLD}{RED}[Polly Alert] Circuit breaker tripped! State: OPEN for {self.break_duration_sec}s{RESET}")


# -----------------------------------------------------------------------------
# 4. Transactional Outbox Pattern Simulation
# -----------------------------------------------------------------------------
@dataclass
class OutboxMessage:
    id: str
    event_type: str
    payload: str
    created_at: float
    published: bool = False


class OutboxProcessor:
    def __init__(self):
        self.db_table: List[OutboxMessage] = []
        self.message_broker_queue: List[OutboxMessage] = []

    def commit_transaction_with_outbox(self, event_type: str, payload: str, ctx: ActivityContext):
        DistributedTracer.start_activity("DbTransaction.Commit(AppDbContext)", ctx)
        msg = OutboxMessage(
            id=uuid.uuid4().hex[:8],
            event_type=event_type,
            payload=payload,
            created_at=time.time()
        )
        self.db_table.append(msg)
        print(f"    {GREEN}[Transactional Outbox]{RESET} Atomically stored event {BOLD}{event_type}{RESET} (ID: {msg.id}) in database Outbox table.")

    def run_publisher_worker(self, ctx: ActivityContext):
        span = DistributedTracer.start_activity("OutboxBackgroundWorker.PublishPendingMessages", ctx)
        pending = [m for m in self.db_table if not m.published]
        if not pending:
            print(f"    {DIM}[Outbox Worker] No pending messages in outbox table.{RESET}")
            return

        print(f"    {CYAN}[Outbox Worker]{RESET} Dispatching {len(pending)} pending messages to Event Bus (RabbitMQ/Kafka)...")
        for m in pending:
            time.sleep(0.2)
            m.published = True
            self.message_broker_queue.append(m)
            print(f"    {GREEN}  ↳ Dispatched:{RESET} Event={m.event_type} | ID={m.id} | Payload='{m.payload}' -> {GREEN}ACKNOWLEDGED{RESET}")


# -----------------------------------------------------------------------------
# Interactive CLI Simulator Runner
# -----------------------------------------------------------------------------
def run_interactive_lab():
    print_banner()

    # Pre-initialized services
    order_grain = OrderGrain(grain_id="ORD-90210")
    polly_pipeline = PollyResiliencePipeline(failure_threshold=3, break_duration_sec=3.0)
    outbox = OutboxProcessor()

    while True:
        print(f"\n{BOLD}{BLUE}================ PANDUAN LAB INTERAKTIF C# DISTRIBUTED ================{RESET}")
        print(f"{CYAN}1.{RESET} Simulasi Orleans Virtual Actor (State Concurrency & Activation)")
        print(f"{CYAN}2.{RESET} Simulasi Polly v8 Circuit Breaker (Resilience Pipeline & Fail-Fast)")
        print(f"{CYAN}3.{RESET} Simulasi Transactional Outbox Pattern (Dual-Write Protection)")
        print(f"{CYAN}4.{RESET} Simulasi E2E Distributed Flow (Actor + Outbox + Tracing + Polly)")
        print(f"{CYAN}5.{RESET} Tampilkan Status Arsitektur Silo & Circuit Breaker")
        print(f"{RED}0.{RESET} Keluar (Exit)")
        print(f"{BOLD}{BLUE}========================================================================{RESET}")

        try:
            choice = input(f"{BOLD}Pilih modul simulasi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "0":
            print(f"{GREEN}Lab selesai. Selamat belajar Distributed Systems C#!{RESET}\n")
            break

        elif choice == "1":
            print(f"\n{BOLD}{MAGENTA}--- [1] ORLEANS VIRTUAL ACTOR GRAIN EXECUTION ---{RESET}")
            ctx = DistributedTracer.start_activity("Client.CallOrderGrain")
            try:
                amt_str = input(f"Masukkan jumlah debit balance (default $150): ").strip()
                amount = float(amt_str) if amt_str else 150.0
            except ValueError:
                amount = 150.0
            order_grain.execute_transaction(amount, ctx)

        elif choice == "2":
            print(f"\n{BOLD}{YELLOW}--- [2] POLLY RESILIENCE PIPELINE TEST ---{RESET}")
            mode = input(f"Simulasi pemanggilan remote API: (s) Sukses atau (f) Gagal/Timeout? [s/f]: ").strip().lower()

            def simulated_external_call():
                if mode == "f":
                    print(f"    {RED}✗ Downstream Microservice timed out (504 Gateway Timeout){RESET}")
                    return False
                print(f"    {GREEN}✓ Downstream Microservice responded HTTP 200 OK (18ms){RESET}")
                return True

            polly_pipeline.execute("PaymentGateway.ChargeCardAsync", simulated_external_call)

        elif choice == "3":
            print(f"\n{BOLD}{CYAN}--- [3] TRANSACTIONAL OUTBOX PATTERN DISPATCHER ---{RESET}")
            ctx = DistributedTracer.start_activity("CheckoutService.ProcessOrder")
            event_type = "OrderPlacedDomainEvent"
            payload = f'{{"orderId": "{order_grain.grain_id}", "timestamp": {int(time.time())}}}'
            outbox.commit_transaction_with_outbox(event_type, payload, ctx)

            trigger_worker = input(f"Jalankan background worker OutboxPublisher? [Y/n]: ").strip().lower()
            if trigger_worker in ("", "y", "yes"):
                outbox.run_publisher_worker(ctx)

        elif choice == "4":
            print(f"\n{BOLD}{GREEN}--- [4] END-TO-END DISTRIBUTED HIGH-THROUGHPUT TRANSACTION ---{RESET}")
            root_ctx = DistributedTracer.start_activity("ApiGateway.SubmitOrder")
            root_ctx.baggage["userId"] = "user_4099"
            root_ctx.baggage["tenant"] = "production-cluster"

            print(f"  {BOLD}Step 1:{RESET} Memanggil Polly Protected Payment Pipeline...")
            payment_ok = polly_pipeline.execute(
                "PaymentGateway.Authorize",
                lambda: random.random() > 0.35  # 65% chance of success
            )

            if payment_ok:
                print(f"\n  {BOLD}Step 2:{RESET} Menjalankan Orleans OrderGrain turn-based debit...")
                order_grain.execute_transaction(250.0, root_ctx)

                print(f"\n  {BOLD}Step 3:{RESET} Menyimpan ke Outbox Table secara atomik...")
                outbox.commit_transaction_with_outbox(
                    "OrderCompletedEvent",
                    f'{{"grainId": "{order_grain.grain_id}", "status": "APPROVED"}}',
                    root_ctx
                )

                print(f"\n  {BOLD}Step 4:{RESET} Background Worker mem-publish ke Message Broker...")
                outbox.run_publisher_worker(root_ctx)
                print(f"\n{BOLD}{GREEN}✓ E2E Distributed Flow Selesai dengan Konsistensi Penuh!{RESET}")
            else:
                print(f"\n{BOLD}{RED}✗ E2E Flow digagalkan oleh Polly Resilience Circuit / Downstream Dependency.{RESET}")

        elif choice == "5":
            print(f"\n{BOLD}{BLUE}--- SYSTEM TELEMETRY & ARCHITECTURE DASHBOARD ---{RESET}")
            print(f"  • Orleans Silo Node       : {GREEN}ONLINE (Cluster: eu-west-silo-prod-01){RESET}")
            print(f"  • OrderGrain({order_grain.grain_id}) State : {MAGENTA}{order_grain.state.value}{RESET}")
            print(f"  • Grain Balance           : {GREEN}${order_grain.balance:.2f}{RESET} (Tx Count: {order_grain.processed_transactions})")
            print(f"  • Polly Circuit State     : {YELLOW if polly_pipeline.state == CircuitState.OPEN else GREEN}{polly_pipeline.state.value}{RESET}")
            print(f"  • Consecutive Failures    : {polly_pipeline.failure_count} / {polly_pipeline.failure_threshold}")
            print(f"  • Outbox DB Messages      : {len(outbox.db_table)} total, {sum(1 for m in outbox.db_table if not m.published)} pending")
            print(f"  • Broker Published Queue  : {len(outbox.message_broker_queue)} events dispatched")

        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    run_interactive_lab()

#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Protokol Keandalan Sistem Terdistribusi & SRE Patterns
Topik: Circuit Breaker, Exponential Backoff + Full Jitter, Token Bucket Rate Limiter,
       serta Fault Injection / Chaos Testing pada RPC Network Layer.
"""

import sys
import time
import math
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# --- ANSI Terminal Styling ---
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
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class RequestMetric:
    attempt: int
    duration_ms: float
    status: str
    circuit_state: CircuitState
    error: Optional[str] = None


class TokenBucketRateLimiter:
    """Implementasi Token Bucket untuk membatasi traffic ingress."""
    def __init__(self, capacity: int, fill_rate_per_sec: float):
        self.capacity = capacity
        self.fill_rate = fill_rate_per_sec
        self.tokens = float(capacity)
        self.last_update = time.time()

    def allow_request(self, tokens_needed: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

        if self.tokens >= tokens_needed:
            self.tokens -= tokens_needed
            return True
        return False


class CircuitBreaker:
    """
    State machine Circuit Breaker standar industri (Netflix Hystrix / Envoy style):
    - CLOSED: Lalu lintas normal.
    - OPEN: Gagalkan cepat (Fail-fast) saat error rate melampaui ambang batas.
    - HALF_OPEN: Uji coba probe parsial setelah cooldown_sec.
    """
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 4.0, half_open_success_needed: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.half_open_success_needed = half_open_success_needed

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.consecutive_success = 0
        self.last_state_change = time.time()

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if (now - self.last_state_change) >= self.recovery_time_sec:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        return True

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.consecutive_success += 1
            if self.consecutive_success >= self.half_open_success_needed:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        self.failure_count += 1
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def _transition_to(self, target_state: CircuitState):
        prev = self.state
        self.state = target_state
        self.last_state_change = time.time()
        if target_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.consecutive_success = 0
        elif target_state == CircuitState.HALF_OPEN:
            self.consecutive_success = 0


class UpstreamServiceNode:
    """Simulasi service backend downstream dengan profil latensi dan error."""
    def __init__(self, name: str, base_latency_ms: float = 25.0):
        self.name = name
        self.base_latency_ms = base_latency_ms
        self.packet_loss_rate = 0.05
        self.is_degraded = False

    def handle_rpc(self) -> Tuple[bool, float, str]:
        # Simulasi network latency distribution (log-normal)
        jitter = random.uniform(0.7, 1.4)
        latency = self.base_latency_ms * jitter

        if self.is_degraded:
            latency += random.uniform(150.0, 400.0)
            if random.random() < 0.70:
                time.sleep(latency / 1000.0)
                return False, latency, "HTTP_503_SERVICE_UNAVAILABLE"

        if random.random() < self.packet_loss_rate:
            latency += 50.0
            time.sleep(latency / 1000.0)
            return False, latency, "NETWORK_TIMEOUT_CONNECTION_RESET"

        time.sleep(latency / 1000.0)
        return True, latency, "200_OK"


class ResilientRPCClient:
    """Client yang menerapkan Retry dengan Exponential Backoff + Full Jitter & Circuit Breaker."""
    def __init__(self, upstream: UpstreamServiceNode, circuit_breaker: CircuitBreaker, rate_limiter: TokenBucketRateLimiter):
        self.upstream = upstream
        self.cb = circuit_breaker
        self.limiter = rate_limiter
        self.history: List[RequestMetric] = []

    def call_with_resilience(self, max_retries: int = 3, base_backoff_ms: float = 40.0, cap_ms: float = 500.0) -> RequestMetric:
        # Step 1: Ingress Rate Limiter Check
        if not self.limiter.allow_request():
            metric = RequestMetric(
                attempt=0,
                duration_ms=0.5,
                status="429_RATE_LIMITED",
                circuit_state=self.cb.state,
                error="CLIENT_RATE_LIMIT_EXCEEDED"
            )
            self.history.append(metric)
            return metric

        # Step 2: Circuit Breaker Gate
        if not self.cb.can_execute():
            metric = RequestMetric(
                attempt=0,
                duration_ms=0.2,
                status="CIRCUIT_REJECTED",
                circuit_state=self.cb.state,
                error="CIRCUIT_OPEN_FAST_FAIL"
            )
            self.history.append(metric)
            return metric

        total_duration = 0.0
        last_error = ""

        # Step 3: Resilient Retries Loop
        for attempt in range(1, max_retries + 1):
            success, latency, message = self.upstream.handle_rpc()
            total_duration += latency

            if success:
                self.cb.record_success()
                metric = RequestMetric(
                    attempt=attempt,
                    duration_ms=total_duration,
                    status=message,
                    circuit_state=self.cb.state
                )
                self.history.append(metric)
                return metric
            else:
                last_error = message
                self.cb.record_failure()

                if attempt < max_retries:
                    # Exponential Backoff with Full Jitter: Sleep = random(0, min(cap, base * 2^attempt))
                    temp = min(cap_ms, base_backoff_ms * (2 ** (attempt - 1)))
                    sleep_ms = random.uniform(0, temp)
                    time.sleep(sleep_ms / 1000.0)
                    total_duration += sleep_ms

        metric = RequestMetric(
            attempt=max_retries,
            duration_ms=total_duration,
            status="FAILED_EXHAUSTED",
            circuit_state=self.cb.state,
            error=last_error
        )
        self.history.append(metric)
        return metric


def render_banner():
    print(f"{CYAN}{BOLD}=" * 80 + f"{RESET}")
    print(f"{WHITE}{BOLD}   LAB M02: SIMULASI PROTOKOL KEANDALAN SRE & DISTRIBUTED RESILIENCY{RESET}")
    print(f"{CYAN}   Circuit Breaker | Exp-Backoff + Full Jitter | Token Bucket | Fault Injection{RESET}")
    print(f"{CYAN}{BOLD}=" * 80 + f"{RESET}\n")


def display_dashboard(client: ResilientRPCClient, upstream: UpstreamServiceNode):
    total = len(client.history)
    if total == 0:
        return

    successes = sum(1 for m in client.history if "200_OK" in m.status)
    open_rejections = sum(1 for m in client.history if m.status == "CIRCUIT_REJECTED")
    rate_limited = sum(1 for m in client.history if m.status == "429_RATE_LIMITED")
    failures = total - successes - open_rejections - rate_limited

    durations = sorted([m.duration_ms for m in client.history])
    p50 = durations[int(len(durations) * 0.50)]
    p95 = durations[min(int(len(durations) * 0.95), len(durations) - 1)]
    p99 = durations[min(int(len(durations) * 0.99), len(durations) - 1)]

    availability = (successes / total) * 100.0

    state_color = GREEN if client.cb.state == CircuitState.CLOSED else (RED if client.cb.state == CircuitState.OPEN else YELLOW)
    backend_status = f"{RED}[DEGRADED / HIGH ERROR]{RESET}" if upstream.is_degraded else f"{GREEN}[HEALTHY]{RESET}"

    print(f"\n{BOLD}{WHITE}--- [ TELEMETRY & SRE DASHBOARD ] ---{RESET}")
    print(f"Backend Target  : {BOLD}{upstream.name}{RESET} {backend_status}")
    print(f"Circuit Breaker : {state_color}{BOLD}{client.cb.state.value}{RESET} (Failures: {client.cb.failure_count}/{client.cb.failure_threshold})")
    print(f"Rate Limiter    : {CYAN}{client.limiter.tokens:.1f}/{client.limiter.capacity} tokens available{RESET}")
    print(f"Total Requests  : {WHITE}{total}{RESET} | Success: {GREEN}{successes}{RESET} | Throttled: {YELLOW}{rate_limited}{RESET} | Fast-Fail: {MAGENTA}{open_rejections}{RESET} | Errors: {RED}{failures}{RESET}")
    print(f"SLO Availability: {BOLD}{GREEN if availability >= 99.0 else (YELLOW if availability >= 90.0 else RED)}{availability:.2f}%{RESET}")
    print(f"Latency Profiles: p50={CYAN}{p50:.1f}ms{RESET} | p95={YELLOW}{p95:.1f}ms{RESET} | p99={RED}{p99:.1f}ms{RESET}")
    print(f"{DIM}{'-' * 80}{RESET}")


def run_batch_simulation(client: ResilientRPCClient, upstream: UpstreamServiceNode, request_count: int, sleep_interval: float = 0.08):
    print(f"{BOLD}{BLUE}>> Memulai simulasi batch {request_count} request...{RESET}")
    for i in range(1, request_count + 1):
        metric = client.call_with_resilience()
        state_badge = f"{GREEN}[CLOSED]{RESET}" if metric.circuit_state == CircuitState.CLOSED else (
            f"{RED}[OPEN]{RESET}" if metric.circuit_state == CircuitState.OPEN else f"{YELLOW}[HALF_OPEN]{RESET}"
        )

        if "200_OK" in metric.status:
            status_badge = f"{GREEN}{BOLD}PASS 200 OK{RESET}"
        elif "CIRCUIT_REJECTED" in metric.status:
            status_badge = f"{MAGENTA}{BOLD}CB FAIL-FAST (NO RPC){RESET}"
        elif "429" in metric.status:
            status_badge = f"{YELLOW}{BOLD}429 RATE LIMIT{RESET}"
        else:
            status_badge = f"{RED}{BOLD}ERR: {metric.error or metric.status}{RESET}"

        attempts_info = f"att={metric.attempt}" if metric.attempt > 0 else "att=0"
        print(f"Req #{i:03d} | {state_badge} | {attempts_info:<6} | Latency: {metric.duration_ms:6.1f}ms | {status_badge}")
        time.sleep(sleep_interval)


def interactive_menu():
    render_banner()
    upstream = UpstreamServiceNode("payment-gateway.internal", base_latency_ms=20.0)
    cb = CircuitBreaker(failure_threshold=3, recovery_time_sec=3.0, half_open_success_needed=2)
    limiter = TokenBucketRateLimiter(capacity=15, fill_rate_per_sec=10.0)
    client = ResilientRPCClient(upstream, cb, limiter)

    while True:
        display_dashboard(client, upstream)
        print(f"\n{BOLD}{CYAN}[MENU AKSI LAB INTERAKTIF]:{RESET}")
        print(f" {GREEN}1{RESET}) Kirim Traffic Normal (10 Requests)")
        print(f" {YELLOW}2{RESET}) Kirim Traffic Burst (25 Requests - Uji Rate Limiter)")
        print(f" {RED}3{RESET}) Suntikkan Chaos / Kegagalan Jaringan (Toggle Backend Degraded)")
        print(f" {BLUE}4{RESET}) Tunggu Recovery Cooldown Circuit Breaker (3.5 Detik)")
        print(f" {WHITE}5{RESET}) Reset Statistik Metrics")
        print(f" {DIM}0{RESET}) Keluar dari Program")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Menutup lab SRE.{RESET}")
            sys.exit(0)

        if choice == "1":
            run_batch_simulation(client, upstream, request_count=10, sleep_interval=0.05)
        elif choice == "2":
            run_batch_simulation(client, upstream, request_count=25, sleep_interval=0.01)
        elif choice == "3":
            upstream.is_degraded = not upstream.is_degraded
            status_text = f"{BG_RED}{WHITE} AKTIF (DEGRADED 70% ERROR) {RESET}" if upstream.is_degraded else f"{BG_GREEN}{WHITE} NON-AKTIF (HEALTHY) {RESET}"
            print(f"\n{BOLD}>> Mode Chaos Failure:{RESET} {status_text}")
        elif choice == "4":
            print(f"\n{YELLOW}>> Menunggu timer pemulihan Circuit Breaker ({cb.recovery_time_sec}s)...{RESET}")
            for sec in range(int(cb.recovery_time_sec) + 1, 0, -1):
                print(f"   Hitung mundur probe HALF-OPEN: {sec}s...", end="\r", flush=True)
                time.sleep(1.0)
            print(f"   {GREEN}Timer selesai. Circuit Breaker siap probe (HALF-OPEN).{RESET}        ")
        elif choice == "5":
            client.history.clear()
            print(f"\n{GREEN}>> Metrik berhasil direset!{RESET}")
        elif choice == "0":
            print(f"\n{GREEN}{BOLD}Simulasi selesai. Terima kasih.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    interactive_menu()

#!/usr/bin/env python3
"""
Lab Exercise: Enterprise PHP SRE, Observability & Cloud-Native Deployment Simulator
BAB-10: Enterprise-SRE-Observability-Cloud-Native-Deployment

This interactive simulation demonstrates core SRE principles for high-throughput PHP workloads:
1. PHP-FPM Pool Capacity Planning & Dynamic Process Tuning.
2. Distributed Tracing with W3C TraceContext (OpenTelemetry simulation).
3. Kubernetes Cloud-Native Probes (Liveness, Readiness, Startup) & Graceful Drain.
4. SRE Service Level Objectives (SLO), Error Budgets, and Multi-Window Burn Rate Alerting.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Terminal ANSI Color Codes
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
BG_RED = "\033[41m"


def banner(title: str) -> None:
    width = 75
    print(f"\n{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}{WHITE}{title.center(width)}{RESET}")
    print(f"{CYAN}{'=' * width}{RESET}\n")


def log_event(stage: str, message: str, level: str = "INFO") -> None:
    colors = {
        "INFO": GREEN,
        "WARN": YELLOW,
        "CRIT": RED,
        "TRACE": MAGENTA,
        "DEBUG": BLUE,
    }
    col = colors.get(level, WHITE)
    timestamp = time.strftime("%H:%M:%S")
    print(f"{DIM}[{timestamp}]{RESET} {col}[{level:<5}]{RESET} {BOLD}[{stage:<14}]{RESET} {message}")


# -----------------------------------------------------------------------------
# Module 1: PHP-FPM Pool Sizing & SRE Worker Exhaustion Simulation
# -----------------------------------------------------------------------------

@dataclass
class FpmPoolConfig:
    pool_name: str = "www-production"
    pm_type: str = "dynamic"  # static, dynamic, ondemand
    total_ram_mb: int = 4096
    os_reserved_mb: int = 1024
    avg_proc_memory_mb: int = 64
    max_children: int = 0
    start_servers: int = 0
    min_spare_servers: int = 0
    max_spare_servers: int = 0
    max_requests: int = 1000

    def compute_defaults(self) -> None:
        usable_ram = max(256, self.total_ram_mb - self.os_reserved_mb)
        self.max_children = max(4, usable_ram // self.avg_proc_memory_mb)
        if self.pm_type == "static":
            self.start_servers = self.max_children
            self.min_spare_servers = 0
            self.max_spare_servers = 0
        else:
            # SRE Recommended heuristics for dynamic
            self.min_spare_servers = max(2, self.max_children // 4)
            self.max_spare_servers = max(self.min_spare_servers + 2, (self.max_children * 3) // 4)
            self.start_servers = (self.min_spare_servers + self.max_spare_servers) // 2


@dataclass
class FpmWorker:
    worker_id: int
    busy: bool = False
    requests_served: int = 0
    memory_mb: float = 48.0
    current_request_duration_ms: float = 0.0


class FpmPoolEngine:
    def __init__(self, config: FpmPoolConfig) -> None:
        self.cfg = config
        self.workers: List[FpmWorker] = [
            FpmWorker(worker_id=i, memory_mb=random.uniform(40.0, 55.0))
            for i in range(self.cfg.start_servers)
        ]
        self.accepted_connections: int = 0
        self.listen_queue_len: int = 0
        self.dropped_connections: int = 0

    def simulate_traffic_wave(self, concurrent_requests: int, simulated_latency_avg_ms: float) -> Dict[str, float]:
        log_event("PHP-FPM", f"Incoming traffic burst: {BOLD}{concurrent_requests}{RESET} concurrent requests", "INFO")
        
        # Scale workers up to max_children if dynamic
        active_count = len(self.workers)
        needed = min(self.cfg.max_children, max(active_count, concurrent_requests))
        if needed > active_count:
            spawns = needed - active_count
            for i in range(spawns):
                self.workers.append(FpmWorker(worker_id=active_count + i, memory_mb=random.uniform(42.0, 52.0)))
            log_event("PHP-FPM", f"Spawned {spawns} new worker processes (Current pool size: {len(self.workers)})", "DEBUG")

        # Distribute workload
        busy_workers = 0
        queued = 0
        dropped = 0

        for req in range(concurrent_requests):
            idle = [w for w in self.workers if not w.busy]
            if idle:
                w = idle[0]
                w.busy = True
                w.requests_served += 1
                w.memory_mb += random.uniform(0.1, 0.4)
                w.current_request_duration_ms = max(5.0, random.gauss(simulated_latency_avg_ms, 15.0))
                busy_workers += 1
                self.accepted_connections += 1
            else:
                # Queue or drop (listen queue limit simulation)
                if queued < 128:  # listen.backlog default simulation
                    queued += 1
                else:
                    dropped += 1
                    self.dropped_connections += 1

        self.listen_queue_len = queued
        total_mem = sum(w.memory_mb for w in self.workers)

        # Output metrics
        status_col = GREEN if dropped == 0 else RED
        print(f"  {status_col}●{RESET} Pool status: Active Workers={busy_workers}/{len(self.workers)} "
              f"| Max Limit={self.cfg.max_children} | Listen Queue={queued} | Dropped={dropped} | Pool RAM={total_mem:.1f}MB")

        if dropped > 0:
            log_event("ALERT", f"PHP-FPM queue backlog saturated! Dropped {dropped} HTTP 502 requests.", "CRIT")

        # Recycle workers reaching max_requests to prevent memory leaks
        recycled = 0
        for w in self.workers:
            if w.requests_served >= self.cfg.max_requests:
                w.requests_served = 0
                w.memory_mb = random.uniform(40.0, 50.0)
                recycled += 1
            w.busy = False  # reset after wave

        if recycled > 0:
            log_event("PHP-FPM", f"Recycled {recycled} worker(s) reaching pm.max_requests={self.cfg.max_requests}", "INFO")

        return {
            "busy_workers": float(busy_workers),
            "pool_size": float(len(self.workers)),
            "queued": float(queued),
            "dropped": float(dropped),
            "total_mem_mb": total_mem,
        }


# -----------------------------------------------------------------------------
# Module 2: OpenTelemetry Tracing & W3C TraceContext Engine
# -----------------------------------------------------------------------------

@dataclass
class OtelSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time_ns: int
    duration_ms: float
    attributes: Dict[str, str] = field(default_factory=dict)
    events: List[Tuple[str, float]] = field(default_factory=list)
    status: str = "OK"  # OK, ERROR


class OtelTraceEngine:
    @staticmethod
    def generate_trace_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def generate_span_id() -> str:
        return uuid.uuid4().hex[:16]

    @classmethod
    def create_w3c_traceparent(cls, trace_id: str, span_id: str, sampled: bool = True) -> str:
        flag = "01" if sampled else "00"
        return f"00-{trace_id}-{span_id}-{flag}"

    @classmethod
    def trace_http_request(cls, route: str, method: str = "GET", inject_error: bool = False) -> List[OtelSpan]:
        trace_id = cls.generate_trace_id()
        root_span_id = cls.generate_span_id()
        now_ns = int(time.time() * 1e9)

        spans: List[OtelSpan] = []

        # Root Span: HTTP Request entering Nginx / FastCGI / Laravel Kernel
        root = OtelSpan(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            name=f"{method} {route}",
            start_time_ns=now_ns,
            duration_ms=0.0,
            attributes={
                "http.method": method,
                "http.route": route,
                "server.runtime": "php-fpm-8.3",
                "service.name": "ecommerce-order-service",
            },
        )

        # Child Span 1: Middleware Auth Check
        auth_span_id = cls.generate_span_id()
        auth_dur = random.uniform(2.5, 6.0)
        spans.append(OtelSpan(
            trace_id=trace_id,
            span_id=auth_span_id,
            parent_span_id=root_span_id,
            name="Middleware::Authenticate",
            start_time_ns=now_ns + 1_000_000,
            duration_ms=auth_dur,
            attributes={"auth.mechanism": "JWT-Bearer", "user.role": "customer"},
        ))

        # Child Span 2: Database Query
        db_span_id = cls.generate_span_id()
        db_dur = random.uniform(8.0, 35.0)
        db_span = OtelSpan(
            trace_id=trace_id,
            span_id=db_span_id,
            parent_span_id=root_span_id,
            name="PDO::query SELECT orders",
            start_time_ns=now_ns + int(auth_dur * 1e6) + 2_000_000,
            duration_ms=db_dur,
            attributes={
                "db.system": "postgresql",
                "db.name": "orders_db",
                "db.statement": "SELECT * FROM orders WHERE customer_id = $1 LIMIT 20",
            },
        )
        if inject_error:
            db_span.status = "ERROR"
            db_span.events.append(("exception", db_dur))
            db_span.attributes["error.message"] = "SQLSTATE[HY000]: Connection pool timeout (5000ms)"
        spans.append(db_span)

        # Child Span 3: Cache Fetch (Redis)
        redis_span_id = cls.generate_span_id()
        redis_dur = random.uniform(0.8, 2.5)
        spans.append(OtelSpan(
            trace_id=trace_id,
            span_id=redis_span_id,
            parent_span_id=root_span_id,
            name="Redis::get order_cache",
            start_time_ns=now_ns + int((auth_dur + db_dur) * 1e6) + 3_000_000,
            duration_ms=redis_dur,
            attributes={"db.system": "redis", "net.peer.name": "redis-cluster.internal"},
        ))

        # Finalize root duration
        root.duration_ms = auth_dur + db_dur + redis_dur + random.uniform(3.0, 8.0)
        if inject_error:
            root.status = "ERROR"
            root.attributes["http.status_code"] = "500"
        else:
            root.attributes["http.status_code"] = "200"

        spans.insert(0, root)
        return spans


# -----------------------------------------------------------------------------
# Module 3: Cloud-Native K8s Probes & Graceful Shutdown Lifecycle
# -----------------------------------------------------------------------------

class KubernetesPodProbe:
    def __init__(self) -> None:
        self.is_started: bool = False
        self.database_connected: bool = True
        self.redis_connected: bool = True
        self.sigterm_received: bool = False
        self.active_fpm_connections: int = 0

    def startup_probe(self) -> Tuple[int, str]:
        """Runs initial warm-up (opcache compilation, config cache)."""
        if self.is_started:
            return 200, "OK: Application initialized"
        return 503, "FAIL: Warming OPcache and framework manifests"

    def liveness_probe(self) -> Tuple[int, str]:
        """Checks if the php-fpm master process responds and memory is healthy."""
        # Liveness checks internal process vitality
        return 200, "OK: php-fpm master active"

    def readiness_probe(self) -> Tuple[int, str]:
        """Checks downstream dependencies and if pod is draining traffic."""
        if self.sigterm_received:
            return 503, "FAIL: Node shutting down (draining active connections)"
        if not self.database_connected:
            return 503, "FAIL: Database health check failed"
        if not self.redis_connected:
            return 503, "FAIL: Redis cache unreachable"
        return 200, f"OK: Ready to serve traffic (Active connections: {self.active_fpm_connections})"

    def handle_sigterm(self) -> None:
        """K8s preStop hook & SIGTERM graceful draining."""
        log_event("K8s LIFECYCLE", "SIGTERM received from Kubelet. Initiating graceful drain...", "WARN")
        self.sigterm_received = True
        log_event("K8s LIFECYCLE", "Readiness probe flipped to 503 (Removing pod from Endpoints/Kube-Proxy)", "INFO")
        
        while self.active_fpm_connections > 0:
            time.sleep(0.05)
            self.active_fpm_connections -= 1
            print(f"  {YELLOW}⏳ Draining in-flight PHP-FPM requests... remaining: {self.active_fpm_connections}{RESET}")
        
        log_event("K8s LIFECYCLE", "All worker processes drained cleanly. Process exiting with code 0.", "INFO")


# -----------------------------------------------------------------------------
# Module 4: SRE SLO, Error Budget & Multi-Window Burn Rate Alerting
# -----------------------------------------------------------------------------

@dataclass
class SloMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    fast_requests: int = 0  # < 200ms
    slo_availability_target: float = 0.999  # 99.9% (Three Nines)
    rolling_window_days: int = 30

    @property
    def error_budget_percent(self) -> float:
        return (1.0 - self.slo_availability_target) * 100.0

    @property
    def current_availability(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    def calculate_burn_rate(self, failure_rate: float) -> float:
        """
        Burn rate = Current Error Rate / Allowed Error Rate (Budget)
        A burn rate of 1.0 consumes 100% of error budget in 30 days.
        A burn rate of 14.4 consumes 2% of budget in 1 hour (Google SRE standard alert).
        """
        allowed_error_rate = 1.0 - self.slo_availability_target
        if allowed_error_rate <= 0:
            return 0.0
        return failure_rate / allowed_error_rate


# -----------------------------------------------------------------------------
# Interactive Console User Interface
# -----------------------------------------------------------------------------

def demo_fpm_tuning() -> None:
    banner("1. PHP-FPM Sizing & Process Tuning Calculator")
    print(f"{WHITE}Formula:{RESET}")
    print(f"  pm.max_children = (Total Available Server RAM - OS Reserved RAM) / Avg Memory Per Worker")
    print(f"  pm.start_servers = (min_spare + max_spare) / 2\n")

    try:
        ram = int(input(f"{BOLD}Enter Server Total RAM in MB (e.g. 4096, 8192) [default 4096]: {RESET}") or "4096")
        reserved = int(input(f"{BOLD}Enter OS & DB Reserved RAM in MB [default 1024]: {RESET}") or "1024")
        proc_mem = int(input(f"{BOLD}Enter Avg PHP Worker Memory (MB) [default 64]: {RESET}") or "64")
    except ValueError:
        print(f"{YELLOW}Invalid input, using defaults.{RESET}")
        ram, reserved, proc_mem = 4096, 1024, 64

    cfg = FpmPoolConfig(total_ram_mb=ram, os_reserved_mb=reserved, avg_proc_memory_mb=proc_mem)
    cfg.compute_defaults()

    print(f"\n{GREEN}{BOLD}=== SRE Recommended php-fpm pool.conf for [{cfg.pool_name}] ==={RESET}")
    print(f"pm = {CYAN}{cfg.pm_type}{RESET}")
    print(f"pm.max_children = {GREEN}{cfg.max_children}{RESET} (Max capacity before OOM crash)")
    print(f"pm.start_servers = {GREEN}{cfg.start_servers}{RESET}")
    print(f"pm.min_spare_servers = {GREEN}{cfg.min_spare_servers}{RESET}")
    print(f"pm.max_spare_servers = {GREEN}{cfg.max_spare_servers}{RESET}")
    print(f"pm.max_requests = {GREEN}{cfg.max_requests}{RESET} (Recycles worker to prevent PHP memory leaks)")
    print(f"pm.process_idle_timeout = {GREEN}10s{RESET}")

    engine = FpmPoolEngine(cfg)
    print(f"\n{BOLD}Simulating Traffic Spikes...{RESET}")
    engine.simulate_traffic_wave(concurrent_requests=cfg.max_children // 2, simulated_latency_avg_ms=20.0)
    engine.simulate_traffic_wave(concurrent_requests=cfg.max_children + 25, simulated_latency_avg_ms=45.0)


def demo_distributed_tracing() -> None:
    banner("2. OpenTelemetry & W3C TraceContext Visualizer")
    print(f"{WHITE}Simulating incoming HTTP Request with OpenTelemetry PHP SDK instrumentation...{RESET}\n")

    spans_success = OtelTraceEngine.trace_http_request("/api/v1/checkout", "POST", inject_error=False)
    root = spans_success[0]
    traceparent = OtelTraceEngine.create_w3c_traceparent(root.trace_id, root.span_id, True)

    print(f"{BOLD}HTTP Headers Injected:{RESET}")
    print(f"  {CYAN}traceparent:{RESET} {WHITE}{traceparent}{RESET}")
    print(f"  {CYAN}tracestate:{RESET}  {WHITE}congo=t61rcWkgMzE,rojo=00f067aa0ba902b7{RESET}\n")

    print(f"{BOLD}Waterfall Trace Tree ({root.name}) [Duration: {root.duration_ms:.2f}ms]:{RESET}")
    for span in spans_success:
        depth_prefix = "  " if span.parent_span_id is None else "    └── "
        stat_color = GREEN if span.status == "OK" else RED
        print(f"{depth_prefix}{stat_color}[{span.status}]{RESET} {BOLD}{span.name:<32}{RESET} "
              f"[{span.duration_ms:6.2f}ms] span_id={span.span_id}")
        for k, v in span.attributes.items():
            print(f"        {DIM}{k} = {v}{RESET}")

    print(f"\n{BOLD}Now simulating a downstream failure with Exception Tracking:{RESET}")
    spans_err = OtelTraceEngine.trace_http_request("/api/v1/orders/history", "GET", inject_error=True)
    for span in spans_err:
        depth_prefix = "  " if span.parent_span_id is None else "    └── "
        stat_color = GREEN if span.status == "OK" else RED
        print(f"{depth_prefix}{stat_color}[{span.status}]{RESET} {BOLD}{span.name:<32}{RESET} [{span.duration_ms:6.2f}ms]")
        if span.status == "ERROR":
            for err_k, err_v in span.attributes.items():
                if "error" in err_k or "status" in err_k:
                    print(f"        {RED}{BOLD}{err_k} = {err_v}{RESET}")


def demo_kubernetes_probes() -> None:
    banner("3. Cloud-Native Kubernetes Probes & PreStop Lifecycle")
    pod = KubernetesPodProbe()

    print(f"{BOLD}Phase 1: Startup Probe Verification{RESET}")
    code, msg = pod.startup_probe()
    print(f"  GET /healthz/startup -> HTTP {RED}{code}{RESET} ({msg})")
    time.sleep(0.3)
    pod.is_started = True
    code, msg = pod.startup_probe()
    print(f"  GET /healthz/startup -> HTTP {GREEN}{code}{RESET} ({msg})\n")

    print(f"{BOLD}Phase 2: Steady State Traffic Serving{RESET}")
    pod.active_fpm_connections = 12
    l_code, l_msg = pod.liveness_probe()
    r_code, r_msg = pod.readiness_probe()
    print(f"  Liveness Probe   -> HTTP {GREEN}{l_code}{RESET} ({l_msg})")
    print(f"  Readiness Probe  -> HTTP {GREEN}{r_code}{RESET} ({r_msg})\n")

    print(f"{BOLD}Phase 3: PreStop Hook & Graceful Shutdown Simulation{RESET}")
    pod.handle_sigterm()

    r_code, r_msg = pod.readiness_probe()
    print(f"\n  Final Readiness State: HTTP {RED}{r_code}{RESET} ({r_msg})")


def demo_slo_burn_rate() -> None:
    banner("4. SRE SLO, Error Budget & Multi-Window Burn Rate")
    slo = SloMetrics(slo_availability_target=0.999)

    print(f"{WHITE}Target SLO: {BOLD}{slo.slo_availability_target * 100:.2f}%{RESET} Availability over 30 days")
    print(f"Total Error Budget: {GREEN}{slo.error_budget_percent:.3f}%{RESET} of requests allowed to fail\n")

    scenarios = [
        ("Normal Operations (Low jitter)", 10000, 9998),
        ("Minor Dependency Degradation", 10000, 9970),
        ("Critical Outage (DB deadlocks)", 10000, 9200),
    ]

    for name, total, succ in scenarios:
        failures = total - succ
        rate = failures / total
        burn = slo.calculate_burn_rate(rate)

        burn_col = GREEN
        severity = "NORMAL"
        if burn >= 14.4:
            burn_col = RED
            severity = "PAGERDUTY ALARM (Page On-Call SRE immediately!)"
        elif burn >= 6.0:
            burn_col = YELLOW
            severity = "TICKET ALERT (Slack channel notification)"

        print(f"{BOLD}Scenario:{RESET} {name}")
        print(f"  Requests: {total:,} | Failures: {failures} ({rate*100:.2f}%)")
        print(f"  Burn Rate: {burn_col}{burn:.2f}x{RESET} -> {burn_col}{BOLD}{severity}{RESET}\n")


def run_automated_tests() -> int:
    """Non-interactive test verification for CI/CD and automated grading."""
    banner("Running Automated Verification Test Suite")
    
    # Test 1: FPM Pool calculation
    cfg = FpmPoolConfig(total_ram_mb=4096, os_reserved_mb=1024, avg_proc_memory_mb=64)
    cfg.compute_defaults()
    assert cfg.max_children == 48, f"Expected 48 max_children, got {cfg.max_children}"
    assert cfg.min_spare_servers == 12, f"Expected 12 min_spare, got {cfg.min_spare_servers}"
    assert cfg.max_spare_servers == 36, f"Expected 36 max_spare, got {cfg.max_spare_servers}"
    log_event("TEST-FPM", "FPM sizing calculation verified successfully", "INFO")

    # Test 2: Engine Traffic
    engine = FpmPoolEngine(cfg)
    metrics = engine.simulate_traffic_wave(concurrent_requests=10, simulated_latency_avg_ms=10.0)
    assert metrics["busy_workers"] == 10, f"Expected 10 busy workers, got {metrics['busy_workers']}"
    assert metrics["dropped"] == 0, "Expected 0 drops"
    log_event("TEST-TRAFFIC", "FPM engine traffic burst verified successfully", "INFO")

    # Test 3: Tracing W3C headers
    spans = OtelTraceEngine.trace_http_request("/api/test", "GET")
    assert len(spans) == 4, f"Expected 4 spans, got {len(spans)}"
    traceparent = OtelTraceEngine.create_w3c_traceparent(spans[0].trace_id, spans[0].span_id, True)
    assert traceparent.startswith("00-"), "Invalid W3C format"
    log_event("TEST-OTEL", "OpenTelemetry W3C trace generation verified", "INFO")

    # Test 4: K8s Probes
    pod = KubernetesPodProbe()
    assert pod.startup_probe()[0] == 503
    pod.is_started = True
    assert pod.startup_probe()[0] == 200
    assert pod.readiness_probe()[0] == 200
    log_event("TEST-K8S", "Kubernetes probes state transitions verified", "INFO")

    # Test 5: SLO calculation
    slo = SloMetrics(slo_availability_target=0.999)
    burn = slo.calculate_burn_rate(0.0144)  # 1.44% failure rate
    assert abs(burn - 14.4) < 1e-4, f"Expected burn rate 14.4, got {burn}"
    log_event("TEST-SLO", "Multi-window burn rate calculation verified", "INFO")

    print(f"\n{GREEN}{BOLD}✓ ALL SRE OBSERVABILITY INTEGRITY TESTS PASSED 100%!{RESET}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="PHP Enterprise SRE & Observability Simulator")
    parser.add_argument("--test", action="store_true", help="Run automated unit/integration tests")
    parser.add_argument("--auto", action="store_true", help="Run full walkthrough non-interactively")
    args = parser.parse_args()

    if args.test:
        sys.exit(run_automated_tests())

    if args.auto:
        demo_fpm_tuning()
        demo_distributed_tracing()
        demo_kubernetes_probes()
        demo_slo_burn_rate()
        run_automated_tests()
        return

    # Interactive Menu
    while True:
        banner("Enterprise PHP SRE & Cloud-Native Observability Lab")
        print(f" {BOLD}1.{RESET} PHP-FPM Pool Capacity Planning & Dynamic Sizing")
        print(f" {BOLD}2.{RESET} OpenTelemetry W3C Distributed Tracing Simulation")
        print(f" {BOLD}3.{RESET} Kubernetes Probes (Liveness/Readiness/Startup) & Drain")
        print(f" {BOLD}4.{RESET} SRE SLO, Error Budget & Multi-Window Burn Rate Alerts")
        print(f" {BOLD}5.{RESET} Run Automated Integrity Verification Test Suite")
        print(f" {BOLD}6.{RESET} Exit\n")

        choice = input(f"{BOLD}Select Module [1-6]: {RESET}").strip()
        if choice == "1":
            demo_fpm_tuning()
        elif choice == "2":
            demo_distributed_tracing()
        elif choice == "3":
            demo_kubernetes_probes()
        elif choice == "4":
            demo_slo_burn_rate()
        elif choice == "5":
            run_automated_tests()
        elif choice in ("6", "q", "exit"):
            print(f"\n{GREEN}Exiting SRE Observability Lab. Happy Reliability Engineering!{RESET}")
            break
        else:
            print(f"{YELLOW}Invalid option, please choose between 1 and 6.{RESET}")

        input(f"\n{DIM}Press Enter to continue...{RESET}")


if __name__ == "__main__":
    main()

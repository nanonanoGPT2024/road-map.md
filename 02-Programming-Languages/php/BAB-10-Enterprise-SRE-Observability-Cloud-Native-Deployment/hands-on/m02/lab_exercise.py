#!/usr/bin/env python3
"""
Lab Exercise: Enterprise SRE, Observability & Cloud-Native Deployment for PHP-FPM
Topic: 02-Programming-Languages / PHP / Chapter 10 - Module 02 Deep Dive

Simulates an enterprise PHP-FPM runtime cluster deployed in Kubernetes:
1. Dynamic Worker Pool Management (pm = dynamic, max_children, recycling on max_requests).
2. Distributed Tracing & W3C TraceContext injection (FastCGI -> Opcode -> PDO DB -> Redis).
3. Slowlog Detection & PHP Fatal Crash Handling.
4. SRE Instrumentation: Prometheus-compatible Metrics Exporter & Kubernetes Health Probes.
"""

import time
import random
import threading
import queue
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"


@dataclass
class Span:
    """Represents an OpenTelemetry-compatible APM Span."""
    name: str
    duration_ms: float
    status: str = "OK"
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class Trace:
    """Represents an end-to-end distributed trace containing FastCGI lifecycle spans."""
    trace_id: str
    uri: str
    spans: List[Span] = field(default_factory=list)
    is_slow: bool = False
    error: Optional[str] = None

    @property
    def total_latency_ms(self) -> float:
        return sum(s.duration_ms for s in self.spans)


class PHPWorker(threading.Thread):
    """
    Simulates a single PHP-FPM FastCGI child worker.
    Respects max_requests recycling and memory management.
    """
    def __init__(self, worker_id: int, task_queue: queue.Queue, result_queue: queue.Queue,
                 max_requests: int = 10, slowlog_timeout_ms: float = 80.0):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.max_requests = max_requests
        self.slowlog_timeout_ms = slowlog_timeout_ms
        self.requests_handled = 0
        self.memory_usage_mb = 18.0  # Base PHP engine bootstrap footprint

    def run(self):
        while True:
            item = self.task_queue.get()
            if item is None:
                break

            trace = self._execute_request(item)
            self.requests_handled += 1
            # Simulate realistic PHP per-request memory fragmentation
            self.memory_usage_mb += random.uniform(0.5, 2.2)

            # Check if PHP-FPM needs to recycle this worker process
            recycled = False
            if self.requests_handled >= self.max_requests:
                recycled = True
                self.memory_usage_mb = 18.0
                self.requests_handled = 0

            self.result_queue.put((self.worker_id, trace, self.memory_usage_mb, recycled))
            self.task_queue.task_done()

    def _execute_request(self, task: dict) -> Trace:
        """Simulates PHP execution stack: Zend Engine compilation, PDO execution, Cache read."""
        trace = Trace(trace_id=task["trace_id"], uri=task["uri"])

        # 1. Zend Opcode & Script Compilation
        comp_time = random.uniform(2.0, 8.0)
        trace.spans.append(Span("zend_compile_file", comp_time, attributes={"file": task["uri"]}))

        # 2. Redis/Session State Fetch
        redis_time = random.uniform(3.0, 12.0)
        trace.spans.append(Span("ext-redis::get", redis_time, attributes={"key": f"sess_{task['trace_id'][:8]}"}))

        # 3. PDO Database Query (may simulate slow queries or lock contention)
        if task["endpoint_type"] == "heavy_sql":
            pdo_time = random.uniform(70.0, 110.0)
        else:
            pdo_time = random.uniform(8.0, 25.0)

        pdo_span = Span("PDO::query", pdo_time, attributes={"db.statement": "SELECT * FROM orders WHERE ..."})
        trace.spans.append(pdo_span)

        # 4. Memory Exhaustion / OOM Simulator
        if task["endpoint_type"] == "oom_trigger":
            trace.error = "Fatal Error: Allowed memory size of 134217728 bytes exhausted"
            trace.spans.append(Span("zend_alloc_failure", 1.0, status="ERROR"))
            return trace

        # Detect Slowlog threshold violation (request_slowlog_timeout)
        if trace.total_latency_ms > self.slowlog_timeout_ms:
            trace.is_slow = True

        return trace


class PHPFPMMonitor:
    """
    SRE Telemetry Aggregator: Metrics, Healthz/Readyz Probes, and Slowlog Logger.
    """
    def __init__(self):
        self.total_requests = 0
        self.slow_requests = 0
        self.crashes = 0
        self.recycles = 0
        self.latencies: List[float] = []

    def record_metrics(self, trace: Trace, recycled: bool):
        self.total_requests += 1
        self.latencies.append(trace.total_latency_ms)
        if trace.is_slow:
            self.slow_requests += 1
        if trace.error:
            self.crashes += 1
        if recycled:
            self.recycles += 1

    def calculate_percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int((p / 100.0) * len(sorted_latencies))
        idx = min(idx, len(sorted_latencies) - 1)
        return sorted_latencies[idx]

    def dump_prometheus_metrics(self, active_workers: int, idle_workers: int):
        """Generates Prometheus-compliant text format metrics."""
        p95 = self.calculate_percentile(95.0)
        p99 = self.calculate_percentile(99.0)
        print(f"\n{CLR_BOLD}{CLR_CYAN}--- PROMETHEUS METRIC EXPORTER (HTTP GET /metrics) ---{CLR_RESET}")
        print("# HELP php_fpm_active_processes The number of active processes.")
        print("# TYPE php_fpm_active_processes gauge")
        print(f"php_fpm_active_processes{{pool=\"www\"}} {active_workers}")
        print("# HELP php_fpm_idle_processes The number of idle processes.")
        print("# TYPE php_fpm_idle_processes gauge")
        print(f"php_fpm_idle_processes{{pool=\"www\"}} {idle_workers}")
        print("# HELP php_fpm_slow_requests_total The number of requests exceeded request_slowlog_timeout.")
        print("# TYPE php_fpm_slow_requests_total counter")
        print(f"php_fpm_slow_requests_total{{pool=\"www\"}} {self.slow_requests}")
        print("# HELP php_fpm_worker_recycles_total Process recycled after reaching pm.max_requests.")
        print("# TYPE php_fpm_worker_recycles_total counter")
        print(f"php_fpm_worker_recycles_total{{pool=\"www\"}} {self.recycles}")
        print(f"php_fpm_http_request_duration_ms{{quantile=\"0.95\"}} {p95:.2f}")
        print(f"php_fpm_http_request_duration_ms{{quantile=\"0.99\"}} {p99:.2f}")


def run_lab():
    print(f"{CLR_BOLD}{CLR_MAGENTA}==================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} LAB: Enterprise PHP-FPM SRE, Observability & Cloud-Native Runtime {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}==================================================================={CLR_RESET}\n")

    num_workers = 3
    task_queue = queue.Queue()
    result_queue = queue.Queue()
    monitor = PHPFPMMonitor()

    print(f"{CLR_BLUE}[SYSTEM] Initializing PHP-FPM Master Process (PID: 1042)...{CLR_RESET}")
    print(f"{CLR_BLUE}[CONFIG] Pool: www | pm: dynamic | pm.max_children: {num_workers} | pm.max_requests: 6{CLR_RESET}")
    print(f"{CLR_BLUE}[CONFIG] request_slowlog_timeout: 80ms | catch_workers_output = yes{CLR_RESET}\n")

    workers = []
    for i in range(num_workers):
        w = PHPWorker(worker_id=i + 1, task_queue=task_queue, result_queue=result_queue,
                      max_requests=6, slowlog_timeout_ms=80.0)
        workers.append(w)
        w.start()
        print(f"  {CLR_GREEN}✔ Child worker [{w.worker_id}] spawned successfully (PID: {2000 + i}){CLR_RESET}")

    # Simulated incoming HTTP/FastCGI batch traffic
    endpoints = [
        {"uri": "/api/v2/orders/create", "endpoint_type": "standard"},
        {"uri": "/api/v2/catalog/item", "endpoint_type": "standard"},
        {"uri": "/api/v2/reports/sales-history", "endpoint_type": "heavy_sql"},
        {"uri": "/api/v2/checkout/process", "endpoint_type": "standard"},
        {"uri": "/api/v2/analytics/memory-leak", "endpoint_type": "oom_trigger"},
        {"uri": "/healthz", "endpoint_type": "standard"},
        {"uri": "/api/v2/inventory/lock", "endpoint_type": "heavy_sql"},
        {"uri": "/api/v2/orders/batch", "endpoint_type": "standard"},
    ]

    print(f"\n{CLR_YELLOW}[TRAFFIC] Ingesting FastCGI ingress traffic into worker pool...{CLR_RESET}\n")
    for idx, ep in enumerate(endpoints):
        task = {
            "trace_id": f"4bf92f3577b34da6a3ce929d0e0e473{idx}",
            "uri": ep["uri"],
            "endpoint_type": ep["endpoint_type"]
        }
        task_queue.put(task)

    # Process responses & simulate APM real-time feed
    processed_count = 0
    traces_inspected: List[Trace] = []

    while processed_count < len(endpoints):
        worker_id, trace, mem_mb, recycled = result_queue.get()
        monitor.record_metrics(trace, recycled)
        traces_inspected.append(trace)

        status_badge = f"{CLR_GREEN}[HTTP 200 OK]{CLR_RESET}"
        if trace.error:
            status_badge = f"{CLR_RED}[HTTP 500 CRASH]{CLR_RESET}"
        elif trace.is_slow:
            status_badge = f"{CLR_YELLOW}[HTTP 200 SLOW]{CLR_RESET}"

        print(f"FastCGI [Worker #{worker_id}] {status_badge} {trace.uri:<30} "
              f"Latency: {trace.total_latency_ms:>6.2f}ms | RSS: {mem_mb:.1f}MB")

        if trace.is_slow:
            print(f"  {CLR_YELLOW}↳ [SLOWLOG ALERT] Execution exceeded 80ms! Draining callstack for SRE tracing...{CLR_RESET}")
        if trace.error:
            print(f"  {CLR_RED}↳ [PHP FATAL] {trace.error}{CLR_RESET}")
        if recycled:
            print(f"  {CLR_CYAN}↳ [PM RECYCLE] Worker #{worker_id} hit pm.max_requests. Graceful restart triggered.{CLR_RESET}")

        processed_count += 1
        time.sleep(0.04)

    # Distributed Tracing Waterfall Inspection for one slow trace
    slow_trace = next((t for t in traces_inspected if t.is_slow), None)
    if slow_trace:
        print(f"\n{CLR_BOLD}{CLR_CYAN}--- DISTRIBUTED TRACE WATERFALL: {slow_trace.trace_id} ---{CLR_RESET}")
        print(f"Route Target: {slow_trace.uri} | Total Duration: {slow_trace.total_latency_ms:.2f}ms")
        for span in slow_trace.spans:
            bar_len = int(span.duration_ms / 2.5)
            bar = "█" * max(1, bar_len)
            print(f"  {span.name:<22} |{CLR_MAGENTA}{bar:<40}{CLR_RESET}| {span.duration_ms:.2f}ms {span.attributes}")

    # Kubernetes Health & Readiness Probes
    print(f"\n{CLR_BOLD}{CLR_CYAN}--- KUBERNETES PROBE EVALUATION ---{CLR_RESET}")
    liveness_ok = monitor.crashes < (monitor.total_requests * 0.5)
    readiness_ok = monitor.calculate_percentile(95.0) < 150.0

    print(f"Liveness  (/-/healthz):  [{'PASS' if liveness_ok else 'FAIL'}] Pod is alive, crash rate below critical limits.")
    print(f"Readiness (/-/readyz):    [{'PASS' if readiness_ok else 'FAIL'}] Latency p95: {monitor.calculate_percentile(95.0):.2f}ms (threshold: 150ms).")

    # Output Prometheus Metrics
    monitor.dump_prometheus_metrics(active_workers=0, idle_workers=num_workers)

    # Graceful shutdown of simulator
    for _ in workers:
        task_queue.put(None)
    for w in workers:
        w.join()

    print(f"\n{CLR_BOLD}{CLR_GREEN}[SUCCESS] Lab execution complete. Enterprise SRE telemetry verified.{CLR_RESET}\n")


if __name__ == "__main__":
    run_lab()
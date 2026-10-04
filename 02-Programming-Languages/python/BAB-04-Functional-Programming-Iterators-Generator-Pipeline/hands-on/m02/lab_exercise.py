#!/usr/bin/env python3
"""
Lab: Functional Programming, Iterators & Generator Pipelines
Module: Advanced Streaming Data Analytics Engine

Mendemonstrasikan:
1. Custom Iterator Protocol (__iter__, __next__)
2. Stateful & Stateless Generator Functions
3. Lazy Generator Pipelines (Producer -> Parser -> Filter -> Windowed Aggregator)
4. Functional Primitives (map, filter, functools.reduce, closures)
5. Verifikasi Efisiensi Memori (Lazy Evaluation vs Eager Collection)
"""

import sys
import time
import random
from typing import Iterator, Iterable, Tuple, Dict, Any, Generator
from dataclasses import dataclass
from functools import reduce

# --- ANSI Terminal Color Formatting ---
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


@dataclass(frozen=True)
class AccessLog:
    """Immutable data model merepresentasikan event web request log."""
    ip: str
    endpoint: str
    status_code: int
    response_time_ms: float
    bytes_sent: int


# ============================================================================
# 1. Custom Iterator Implementation
# ============================================================================
class RateLimitingWindow:
    """
    Stateful custom iterator yang mengelompokkan item ke dalam sliding window
    berukuran N tanpa me-load seluruh stream ke dalam RAM sekaligus.
    """
    def __init__(self, iterable: Iterable[Any], window_size: int):
        self._source = iter(iterable)
        self._window_size = window_size
        self._buffer = []
        self._exhausted = False

    def __iter__(self) -> "RateLimitingWindow":
        return self

    def __next__(self) -> Tuple[Any, ...]:
        if self._exhausted:
            raise StopIteration

        # Isi buffer sampai batas window
        while len(self._buffer) < self._window_size:
            try:
                self._buffer.append(next(self._source))
            except StopIteration:
                self._exhausted = True
                break

        if not self._buffer:
            raise StopIteration

        snapshot = tuple(self._buffer)
        # Geser sliding window: drop elemen terlama
        self._buffer.pop(0)
        return snapshot


# ============================================================================
# 2. Generator Pipeline Components
# ============================================================================
def raw_log_producer(total_records: int) -> Generator[str, None, None]:
    """
    Producer: Menghasilkan log mentah berformat CLF secara streaming.
    Menggunakan generator untuk mencegah OOM pada dataset masif.
    """
    endpoints = ["/api/v1/checkout", "/api/v1/login", "/search", "/static/app.js", "/api/v1/telemetry"]
    statuses = [200, 200, 200, 201, 400, 401, 404, 500, 503]
    ips = [f"192.168.1.{i}" for i in range(1, 255)]

    for _ in range(total_records):
        ip = random.choice(ips)
        endpoint = random.choice(endpoints)
        status = random.choice(statuses)
        # Injeksi spike latensi sesekali untuk simulasi anomali
        latency = round(random.expovariate(1 / 50.0) + (500.0 if random.random() < 0.05 else 5.0), 2)
        bytes_sent = random.randint(200, 15000)
        yield f"{ip} - - [{time.strftime('%d/%b/%Y:%H:%M:%S')}] GET {endpoint} {status} {latency} {bytes_sent}"


def parse_log_pipeline(raw_stream: Iterable[str]) -> Generator[AccessLog, None, None]:
    """
    Transformer Pipeline: Melakukan parsing string menjadi objek AccessLog.
    """
    for entry in raw_stream:
        parts = entry.split()
        yield AccessLog(
            ip=parts[0],
            endpoint=parts[6],
            status_code=int(parts[7]),
            response_time_ms=float(parts[8]),
            bytes_sent=int(parts[9]),
        )


def anomaly_detector_pipeline(
    log_stream: Iterable[AccessLog], 
    latency_threshold_ms: float
) -> Generator[AccessLog, None, None]:
    """
    Filter Pipeline: Pure generator filter yang hanya melewatkan log yang
    memiliki indikasi anomali (Error 5xx atau High Latency).
    """
    for log in log_stream:
        is_server_error = 500 <= log.status_code <= 599
        is_slow_query = log.response_time_ms >= latency_threshold_ms
        if is_server_error or is_slow_query:
            yield log


# ============================================================================
# 3. Functional Accumulators & Aggregations
# ============================================================================
def aggregate_metrics(acc: Dict[str, Any], log: AccessLog) -> Dict[str, Any]:
    """
    Pure reducer function yang dirancang untuk functools.reduce.
    Akumulasi latensi total, transfer data, dan error count.
    """
    acc["count"] += 1
    acc["total_latency"] += log.response_time_ms
    acc["total_bytes"] += log.bytes_sent
    if log.status_code >= 500:
        acc["server_errors"] += 1
    acc["max_latency"] = max(acc["max_latency"], log.response_time_ms)
    return acc


def run_pipeline_demo(records_count: int = 250_000) -> None:
    print(f"{BOLD}{CYAN}=== 1. LAZY GENERATOR PIPELINE MEMORY BENCHMARK ==={RESET}")
    print(f"Dataset Size : {records_count:,} records")

    # --- Pengujian Memori: Eager Evaluation (List Comprehension) ---
    sample_size = 50_000  # Subsample untuk menghindari memory exhaustion sistem
    t0 = time.perf_counter()
    eager_list = [log for log in parse_log_pipeline(raw_log_producer(sample_size))]
    eager_time = time.perf_counter() - t0
    eager_size_mb = sys.getsizeof(eager_list) / (1024 * 1024)
    print(f"{YELLOW}[Eager Processing]{RESET} (N={sample_size:,})")
    print(f"  └─ RAM Usage (List object): {BOLD}{eager_size_mb:.4f} MB{RESET} | Elapsed: {eager_time:.3f}s")
    del eager_list

    # --- Pengujian Memori: Lazy Evaluation (Generator Pipeline) ---
    t0 = time.perf_counter()
    lazy_gen = parse_log_pipeline(raw_log_producer(records_count))
    lazy_size_bytes = sys.getsizeof(lazy_gen)
    lazy_time = time.perf_counter() - t0
    print(f"{GREEN}[Lazy Pipeline]{RESET}   (N={records_count:,})")
    print(f"  └─ RAM Usage (Generator):   {BOLD}{lazy_size_bytes} Bytes{RESET} | Instantiation: {lazy_time:.6f}s")
    print(f"  └─ Memory saving factor   : ~{BOLD}{((eager_size_mb * 1024 * 1024) / lazy_size_bytes):.1f}x{RESET}\n")

    # --- Eksekusi Real-time Streaming Pipeline ---
    print(f"{BOLD}{CYAN}=== 2. STREAMING ANOMALY DETECTION & PROCESSING ==={RESET}")
    latency_threshold = 250.0  # ms
    pipeline = anomaly_detector_pipeline(
        parse_log_pipeline(raw_log_producer(records_count)), 
        latency_threshold_ms=latency_threshold
    )

    initial_state = {
        "count": 0,
        "total_latency": 0.0,
        "total_bytes": 0,
        "server_errors": 0,
        "max_latency": 0.0,
    }

    t0 = time.perf_counter()
    # Mengalirkan stream melalui reducer secara on-the-fly
    summary = reduce(aggregate_metrics, pipeline, initial_state)
    elapsed = time.perf_counter() - t0

    throughput = records_count / elapsed
    avg_latency = summary["total_latency"] / summary["count"] if summary["count"] else 0.0

    print(f"Processed      : {BOLD}{records_count:,}{RESET} log records in {BOLD}{elapsed:.3f}s{RESET}")
    print(f"Throughput     : {GREEN}{throughput:,.1f} events/sec{RESET}")
    print(f"Anomalies Found: {RED}{summary['count']:,}{RESET} events ({(summary['count']/records_count)*100:.2f}%)")
    print(f"  ├─ 5xx Server Errors  : {summary['server_errors']:,}")
    print(f"  ├─ Max Latency Spikes : {summary['max_latency']:.2f} ms")
    print(f"  ├─ Avg Anomaly Latency: {avg_latency:.2f} ms")
    print(f"  └─ Data Transferred   : {summary['total_bytes'] / (1024*1024):.2f} MB\n")

    # --- Demonstrasi Custom Sliding Window Iterator ---
    print(f"{BOLD}{CYAN}=== 3. CUSTOM ITERATOR SLIDING WINDOW STREAM ==={RESET}")
    test_stream = parse_log_pipeline(raw_log_producer(10))
    windowed_stream = RateLimitingWindow(test_stream, window_size=3)

    print("Tracking 3-Request Window Latency Average:")
    for idx, window in enumerate(windowed_stream, 1):
        window_avg = sum(item.response_time_ms for item in window) / len(window)
        endpoints = " -> ".join([w.endpoint for w in window])
        print(f"  Window #{idx:02d} [{len(window)} items] Avg: {BOLD}{window_avg:6.2f}ms{RESET} | Flow: {MAGENTA}{endpoints}{RESET}")


if __name__ == "__main__":
    try:
        run_pipeline_demo()
    except KeyboardInterrupt:
        print(f"\n{RED}Pipeline execution interrupted by user.{RESET}")
        sys.exit(0)
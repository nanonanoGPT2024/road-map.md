"""
Production Module: Low-Latency High-Throughput Metric Collector & Rate Limiter
File: metrics_engine.py
"""

from __future__ import annotations
import time
import sys
import gc
from collections import deque
import heapq
from typing import NamedTuple, List, Optional, Tuple

class MetricEvent:
    """Representasi payload metrik ultra-ringan tanpa overhead dynamic dictionary."""
    __slots__ = ('timestamp', 'latency_ms', 'status_code')

    def __init__(self, timestamp: float, latency_ms: float, status_code: int) -> None:
        self.timestamp = timestamp
        self.latency_ms = latency_ms
        self.status_code = status_code

    def __lt__(self, other: MetricEvent) -> bool:
        # Dibutuhkan oleh heap ordering
        return self.latency_ms < other.latency_ms

class SlidingWindowBuffer:
    """
    Koleksi metrik bounded berbasis ring/deque buffer.
    Menjamin operasi Append dan Eviction selalu O(1) konstan tanpa alokasi memori berlebih.
    """
    __slots__ = ('max_window_sec', 'events', '_capacity')

    def __init__(self, max_window_sec: float, capacity: int = 100_000) -> None:
        self.max_window_sec = max_window_sec
        self._capacity = capacity
        # Bounded deque mencegah memory unbounded growth
        self.events: deque[MetricEvent] = deque(maxlen=capacity)

    def record_event(self, latency_ms: float, status_code: int) -> None:
        now = time.monotonic()
        # Amortized O(1) push; jika melebihi batas, elemen tertua dibuang otomatis dari kiri di level C
        self.events.append(MetricEvent(now, latency_ms, status_code))

    def purge_expired(self, current_time: float) -> int:
        """Membersihkan elemen yang keluar dari window waktu dengan O(k) di mana k = elemen kedaluwarsa."""
        evicted = 0
        threshold = current_time - self.max_window_sec
        # Akses elemen paling kiri secara konstan
        while self.events and self.events[0].timestamp < threshold:
            self.events.popleft()
            evicted += 1
        return evicted

class LatencyTracker:
    """
    Melacak Top-K transaksi terlambat menggunakan bounded min-heap.
    Kapasitas memory dijamin O(K).
    """
    __slots__ = ('k', 'heap')

    def __init__(self, k: int = 10) -> None:
        self.k = k
        self.heap: List[Tuple[float, float]] = []  # Menyimpan tuple: (latency_ms, timestamp)

    def push_latency(self, latency_ms: float, timestamp: float) -> None:
        if len(self.heap) < self.k:
            heapq.heappush(self.heap, (latency_ms, timestamp))
        else:
            # Jika latensi lebih besar dari elemen terkecil di Top-K saat ini, gantikan
            if latency_ms > self.heap[0][0]:
                heapq.heapreplace(self.heap, (latency_ms, timestamp))

    def get_top_k(self) -> List[Tuple[float, float]]:
        """Mengembalikan metrik top-k terurut dari terkecil ke terbesar."""
        return sorted(self.heap, reverse=True)

class PerformanceTelemetryEngine:
    """Fasad Orkestrasi Pemrosesan Metrik."""
    def __init__(self, window_sec: float = 60.0) -> None:
        self.buffer = SlidingWindowBuffer(max_window_sec=window_sec)
        self.top_slow_requests = LatencyTracker(k=5)

    def ingest(self, latency_ms: float, status_code: int) -> None:
        now = time.monotonic()
        self.buffer.record_event(latency_ms, status_code)
        self.top_slow_requests.push_latency(latency_ms, now)

    def run_maintenance_cycle(self) -> dict:
        now = time.monotonic()
        purged = self.buffer.purge_expired(now)
        return {
            "purged_records": purged,
            "active_window_size": len(self.buffer.events),
            "top_slow_events": self.top_slow_requests.get_top_k()
        }

if __name__ == "__main__":
    import random

    print("=== SIMULASI STREAMING 200.000 METRIK DENGAN LOW MEMORY FOOTPRINT ===")
    engine = PerformanceTelemetryEngine(window_sec=2.0)

    # Catat jejak awal GC
    gc.collect()
    start_time = time.perf_counter()

    for idx in range(200_000):
        # Bangkitkan payload acak
        latency = random.uniform(5.0, 450.0)
        status = 200 if latency < 400.0 else 504
        engine.ingest(latency_ms=latency, status_code=status)

        # Simulasi maintenance window berkala tiap 50.000 operasi
        if idx % 50_000 == 0 and idx > 0:
            time.sleep(0.1)  # Simulasi pergeseran waktu
            telemetry = engine.run_maintenance_cycle()
            print(f"Batch {idx} | Aktif: {telemetry['active_window_size']} items | Dihapus: {telemetry['purged_records']}")

    elapsed = time.perf_counter() - start_time
    print(f"\nSelesai memproses 200.000 event dalam {elapsed:.4f} detik.")
    print(f"Throughput: {200_000 / elapsed:.2f} events/detik")
    print(f"Top 5 Latency Terburuk (ms): {engine.top_slow_requests.get_top_k()}")

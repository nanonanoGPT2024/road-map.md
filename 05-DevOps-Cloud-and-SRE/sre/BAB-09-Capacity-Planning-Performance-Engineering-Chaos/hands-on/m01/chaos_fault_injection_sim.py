#!/usr/bin/env python3
"""
Production Resilience & Chaos Engineering Simulator
Standar Kurikulum: GEMINI.md SRE

Simulator ini mereplikasi kondisi sistem pemrosesan transaksi terdistribusi:
- Mensimulasikan traffic request generator (Arrival Rate / Poisson Distribution)
- Menerapkan kalkulasi Little's Law secara dinamis
- Mensimulasikan Worker Thread Pool dengan bounded buffer queue
- Menginjeksi anomali Chaos:
    * Latency Injection (tc-netem simulation)
    * Packet Loss / Drops (socket failure simulation)
    * CPU Starvation / Contention (Amdahl's Law serial thread stall)
"""

import time
import math
import random
import threading
import logging
from dataclasses import dataclass, field
from queue import Queue, Full, Empty
from typing import List, Dict

# Inisialisasi Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ChaosSimulator")

@dataclass
class SystemMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    dropped_by_queue: int = 0
    latencies: List[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_success(self, latency: float):
        with self.lock:
            self.total_requests += 1
            self.successful_requests += 1
            self.latencies.append(latency)

    def record_failure(self):
        with self.lock:
            self.total_requests += 1
            self.failed_requests += 1

    def record_queue_drop(self):
        with self.lock:
            self.total_requests += 1
            self.dropped_by_queue += 1

    def get_snapshot(self) -> Dict[str, float]:
        with self.lock:
            if not self.latencies:
                return {
                    "throughput_success": 0,
                    "error_rate_pct": 0,
                    "p50_ms": 0,
                    "p95_ms": 0,
                    "p99_ms": 0,
                    "queue_drops": self.dropped_by_queue
                }
            sorted_lat = sorted(self.latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[int(0.50 * n)] * 1000
            p95 = sorted_lat[int(0.95 * n)] * 1000
            p99 = sorted_lat[int(0.99 * n)] * 1000
            err_pct = ((self.failed_requests + self.dropped_by_queue) / max(1, self.total_requests)) * 100
            return {
                "total_received": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "queue_drops": self.dropped_by_queue,
                "error_rate_pct": err_pct,
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99
            }

@dataclass
class ChaosConfig:
    latency_injection_sec: float = 0.0
    packet_loss_rate: float = 0.0 # 0.0 - 1.0 (0% - 100%)
    cpu_starvation_factor: float = 1.0 # 1.0 = Normal, 5.0 = 5x slower serialization
    active: bool = False

class MicroserviceWorker(threading.Thread):
    def __init__(self, worker_id: int, request_queue: Queue, metrics: SystemMetrics, chaos_config: ChaosConfig):
        super().__init__(name=f"Worker-{worker_id}", daemon=True)
        self.worker_id = worker_id
        self.queue = request_queue
        self.metrics = metrics
        self.chaos = chaos_config
        self.base_processing_time = 0.035 # 35ms baseline processing

    def run(self):
        while True:
            try:
                arrival_time = self.queue.get(timeout=1.0)
            except Empty:
                continue

            start_proc = time.perf_counter()

            # Chaos Primitive 1: Packet Loss Simulation
            if self.chaos.active and random.random() < self.chaos.packet_loss_rate:
                self.queue.task_done()
                self.metrics.record_failure()
                continue

            # Base Work Execution (Amdahl Serial vs Parallel Simulation)
            # Parallel component:
            parallel_work = self.base_processing_time * 0.7
            time.sleep(parallel_work)

            # Serial component (vulnerable to CPU contention / lock delay):
            serial_work = (self.base_processing_time * 0.3) * (
                self.chaos.cpu_starvation_factor if self.chaos.active else 1.0
            )
            time.sleep(serial_work)

            # Chaos Primitive 2: Network Latency Injection
            if self.chaos.active and self.chaos.latency_injection_sec > 0:
                # Add latency + jitter
                jitter = random.uniform(-0.010, 0.010)
                actual_delay = max(0.0, self.chaos.latency_injection_sec + jitter)
                time.sleep(actual_delay)

            end_proc = time.perf_counter()
            total_latency = end_proc - arrival_time
            self.metrics.record_success(total_latency)
            self.queue.task_done()

class WorkloadGenerator(threading.Thread):
    def __init__(self, target_rps: int, request_queue: Queue, metrics: SystemMetrics, duration_sec: int):
        super().__init__(name="Traffic-Gen", daemon=True)
        self.target_rps = target_rps
        self.queue = request_queue
        self.metrics = metrics
        self.duration_sec = duration_sec

    def run(self):
        interval = 1.0 / self.target_rps
        end_time = time.time() + self.duration_sec
        logger.info(f"Target RPS Generator aktif: {self.target_rps} RPS konstan (No Coordinated Omission)")

        while time.time() < end_time:
            tick_start = time.perf_counter()
            try:
                # Menambahkan timestamp arrival untuk kalkulasi real queuing delay
                self.queue.put_nowait(time.perf_counter())
            except Full:
                # Mengukur Coordinated Omission: Buffer penuh, sistem mengalami starvation
                self.metrics.record_queue_drop()

            elapsed = time.perf_counter() - tick_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

def execute_simulation():
    print("=" * 75)
    print("      SRE LAB: CAPACITY PLANNING & CHAOS EXPERIMENT SIMULATOR")
    print("=" * 75)

    # 1. Parameter Dimensi Kapasitas
    TARGET_RPS = 1200
    WORKER_POOL_SIZE = 30
    QUEUE_CAPACITY = 200
    EXPERIMENT_DURATION = 25 # detik

    # Little's Law Theoretical Calculation
    baseline_latency = 0.035 # 35ms
    theoretical_concurrency = TARGET_RPS * baseline_latency
    print(f"\n[1] Kalkulasi Kapasitas Little's Law:")
    print(f"    - Target Arrival Rate (lambda) : {TARGET_RPS} RPS")
    print(f"    - Base Latency Service (W)     : {baseline_latency * 1000:.1f} ms")
    print(f"    - Kebutuhan Konkurensi Rata-rata (L) : {theoretical_concurrency:.2f} parallel execution")
    print(f"    - Worker Threads Dialokasikan  : {WORKER_POOL_SIZE}")
    print(f"    - Bounded Queue Buffer Size    : {QUEUE_CAPACITY}\n")

    request_queue = Queue(maxsize=QUEUE_CAPACITY)
    metrics = SystemMetrics()
    chaos_config = ChaosConfig()

    # Inisialisasi Worker Threads
    workers = []
    for i in range(WORKER_POOL_SIZE):
        w = MicroserviceWorker(i, request_queue, metrics, chaos_config)
        w.start()
        workers.append(w)

    # Inisialisasi Traffic Generator
    generator = WorkloadGenerator(TARGET_RPS, request_queue, metrics, EXPERIMENT_DURATION)
    generator.start()

    # Timeline Kontrol Eksperimen
    start_sim = time.time()
    chaos_injected = False
    chaos_recovered = False

    print("Status Simulasi:")
    print("Detik | Status       | In-Queue | P50 (ms) | P95 (ms) | P99 (ms) | Err Rate (%) | Queue Drops")
    print("-" * 85)

    while time.time() - start_sim < EXPERIMENT_DURATION:
        time_elapsed = int(time.time() - start_sim)

        # Fase 1: Baseline Steady State (0-7s)
        # Fase 2: Inject Chaos (8-16s)
        if 8 <= time_elapsed <= 16 and not chaos_injected:
            logger.warning(">>> [GAME DAY ACTION] Menginjeksi Chaos Faults:")
            logger.warning("    * Network Delay: +120ms")
            logger.warning("    * Packet Loss  : 3%")
            logger.warning("    * CPU Contention Factor: 3.5x")
            chaos_config.latency_injection_sec = 0.120
            chaos_config.packet_loss_rate = 0.03
            chaos_config.cpu_starvation_factor = 3.5
            chaos_config.active = True
            chaos_injected = True

        # Fase 3: Self-Healing / Rollback Trigger (17-25s)
        if time_elapsed > 16 and not chaos_recovered:
            logger.info(">>> [ROLLBACK / RECOVERY] Menghentikan Injeksi Chaos. Memulihkan Steady State...")
            chaos_config.active = False
            chaos_recovered = True

        # Observability Metrics Snapshot
        snap = metrics.get_snapshot()
        q_size = request_queue.qsize()
        status_label = "STEADY"
        if chaos_config.active:
            status_label = "CHAOS ACTIVE"
        elif chaos_recovered:
            status_label = "RECOVERING"

        print(f"{time_elapsed:5d} | {status_label:12s} | {q_size:8d} | {snap['p50_ms']:8.1f} | {snap['p95_ms']:8.1f} | {snap['p99_ms']:8.1f} | {snap['error_rate_pct']:11.2f}% | {snap['queue_drops']:11d}")
        time.sleep(1.0)

    generator.join()
    print("-" * 85)
    print("\nEksperimen Selesai. Hasil Audit Post-Mortem:")
    final_snap = metrics.get_snapshot()
    print(f"Total Request Diterima  : {final_snap['total_received']}")
    print(f"Total Berhasil Diproses : {final_snap['successful']}")
    print(f"Total Gagal (Chaos Drop): {final_snap['failed']}")
    print(f"Total Antrean Tertolak  : {final_snap['queue_drops']} (Buffer Exhaustion)")
    print(f"Final Error Rate        : {final_snap['error_rate_pct']:.2f}%")
    print(f"P95 Latency Overall     : {final_snap['p95_ms']:.2f} ms")
    print(f"P99 Latency Overall     : {final_snap['p99_ms']:.2f} ms")

    if final_snap['queue_drops'] > 0:
        print("\n[KESIMPULAN SRE]")
        print("Sistem mengalami saturasi kapasitas berat selama chaos berlangsung.")
        print("Kenaikan latensi downstream menyebabkan antrean in-flight melonjak melampaui buffer.")
        print("Sesuai Little's Law: L membesar melebihi WORKER_POOL_SIZE + QUEUE_CAPACITY.")
        print("Rekomendasi: Terapkan Adaptive Concurrency Limits (TCP Vegas / BBR style) pada client!")

if __name__ == "__main__":
    execute_simulation()
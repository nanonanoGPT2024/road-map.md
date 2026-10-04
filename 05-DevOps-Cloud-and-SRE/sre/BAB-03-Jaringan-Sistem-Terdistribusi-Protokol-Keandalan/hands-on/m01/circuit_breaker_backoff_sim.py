#!/usr/bin/env python3
"""
SRE Reliability Engineering Simulator
Implementasi:
1. Circuit Breaker (Closed, Open, Half-Open)
2. Exponential Backoff with Full Jitter
3. Request Hedging (Tail Latency Reducer)
4. Simulasi Chaos Network Benchmark
"""

import asyncio
import enum
import math
import random
import statistics
import time
from typing import Callable, Any, Tuple, Optional


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Dilempar ketika Circuit Breaker berstatus OPEN dan menolak request."""
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: float = 0.4,
        recovery_time: float = 2.0,
        sample_size: int = 10,
        half_open_success_threshold: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.sample_size = sample_size
        self.half_open_success_threshold = half_open_success_threshold

        self.state = CircuitState.CLOSED
        self.history = []
        self.last_state_change = time.time()
        self.half_open_successes = 0

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_time:
                self._transit_to(CircuitState.HALF_OPEN)
                return True
            return False
        return True

    def record_result(self, success: bool):
        now = time.time()
        if self.state == CircuitState.HALF_OPEN:
            if success:
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_success_threshold:
                    self._transit_to(CircuitState.CLOSED)
            else:
                self._transit_to(CircuitState.OPEN)
            return

        if self.state == CircuitState.CLOSED:
            self.history.append(1 if success else 0)
            if len(self.history) > self.sample_size:
                self.history.pop(0)

            if len(self.history) >= self.sample_size:
                failure_rate = 1.0 - (sum(self.history) / len(self.history))
                if failure_rate >= self.failure_threshold:
                    self._transit_to(CircuitState.OPEN)

    def _transit_to(self, new_state: CircuitState):
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.HALF_OPEN:
            self.half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self.history.clear()


class UnreliableService:
    """
    Simulasi Downstream Service dengan Chaos Profil:
    - 70% Cepat (Normal: 10-25ms)
    - 20% Latency Spike (Tail Latency / GC Pause: 300-600ms)
    - 10% Kegagalan Total (Exception / Drop)
    """
    def __init__(self, name: str):
        self.name = name

    async def call(self, request_id: int) -> Tuple[int, float]:
        start = time.time()
        dice = random.random()

        if dice < 0.10:
            # 10% Peluang Network Drop / Internal Error
            await asyncio.sleep(0.05)
            raise ConnectionResetError(f"[{self.name}] Drop connection pada req {request_id}")
        elif dice < 0.30:
            # 20% Peluang Latency Spike (Tail Latency)
            delay = random.uniform(0.30, 0.60)
            await asyncio.sleep(delay)
        else:
            # 70% Peluang Jalur Cepat Normal
            delay = random.uniform(0.01, 0.025)
            await asyncio.sleep(delay)

        elapsed = time.time() - start
        return 200, elapsed


def calculate_full_jitter_backoff(attempt: int, base: float = 0.05, cap: float = 1.0) -> float:
    """Formula: Full Jitter = random(0, min(cap, base * 2^attempt))"""
    temp = min(cap, base * (2 ** attempt))
    return random.uniform(0, temp)


class ResilientClient:
    def __init__(self, services: list[UnreliableService]):
        self.services = services
        self.circuit_breaker = CircuitBreaker()
        self.hedge_delay = 0.040  # Kirim request hedging jika latensi melampaui 40ms

    async def execute_request(self, request_id: int, enable_hedging: bool = True) -> Tuple[bool, float, str]:
        start_time = time.time()
        max_retries = 3

        for attempt in range(max_retries):
            if not self.circuit_breaker.can_execute():
                # Fast fail jika Circuit Breaker Open
                return False, time.time() - start_time, "FAST_FAIL_CIRCUIT_OPEN"

            service = random.choice(self.services)

            try:
                if enable_hedging:
                    success, elapsed, source = await self._hedged_call(service, request_id)
                else:
                    status, _ = await service.call(request_id)
                    success, elapsed, source = True, time.time() - start_time, service.name

                self.circuit_breaker.record_result(True)
                return True, elapsed, source

            except Exception as e:
                self.circuit_breaker.record_result(False)
                if attempt == max_retries - 1:
                    return False, time.time() - start_time, f"FAILED_MAX_RETRIES: {str(e)}"

                # Sleep dengan Exponential Backoff + Full Jitter
                sleep_duration = calculate_full_jitter_backoff(attempt)
                await asyncio.sleep(sleep_duration)

        return False, time.time() - start_time, "UNKNOWN_ERROR"

    async def _hedged_call(self, primary_service: UnreliableService, request_id: int) -> Tuple[bool, float, str]:
        start = time.time()
        primary_task = asyncio.create_task(primary_service.call(request_id))

        # Tunggu sampai hedge_delay untuk melihat apakah primary selesai
        done, pending = await asyncio.wait([primary_task], timeout=self.hedge_delay)

        if primary_task in done and not primary_task.cancelled():
            try:
                primary_task.result()
                return True, time.time() - start, f"PRIMARY ({primary_service.name})"
            except Exception:
                # Jika primary gagal instan, biarkan flow jatuh ke hedging/fallback
                pass

        # Hedge Trigger: Eksekusi replika sekunder secara spekulatif
        backup_candidates = [s for s in self.services if s != primary_service]
        secondary_service = random.choice(backup_candidates) if backup_candidates else primary_service
        secondary_task = asyncio.create_task(secondary_service.call(request_id))

        all_tasks = set(pending) | {secondary_task}

        while all_tasks:
            done_set, all_tasks = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done_set:
                try:
                    t.result()
                    # Batalkan task lain yang masih berjalan
                    for p in all_tasks:
                        p.cancel()
                    source_str = "HEDGED_REPLICA" if t == secondary_task else "PRIMARY_LATE"
                    return True, time.time() - start, source_str
                except Exception:
                    # Task ini gagal, loop lanjut jika masih ada task yang pending
                    continue

        raise ConnectionError("Semua target request (Primary & Hedged) mengalami kegagalan.")


async def run_benchmark():
    random.seed(42)  # Deterministic seed untuk reproduksibilitas edukasi
    print("=" * 80)
    print("SRE LAB: DISTRIBUTED PROTOCOLS & NETWORK RELIABILITY SIMULATION")
    print("=" * 80)

    replicas = [UnreliableService(f"pod-eu-west-{i}") for i in range(1, 4)]
    client = ResilientClient(replicas)
    num_requests = 100

    print(f"\n[1] Menjalankan baseline: 100 Requests TANPA Request Hedging...")
    baseline_latencies = []
    baseline_failures = 0

    for i in range(num_requests):
        success, elapsed, _ = await client.execute_request(request_id=i, enable_hedging=False)
        if success:
            baseline_latencies.append(elapsed * 1000)
        else:
            baseline_failures += 1
        await asyncio.sleep(0.01)

    print(f"[2] Menjalankan pengujian: 100 Requests DENGAN Request Hedging + CB + Jitter...")
    # Reset Circuit Breaker untuk benchmark yang adil
    client.circuit_breaker = CircuitBreaker()
    resilient_latencies = []
    resilient_failures = 0
    sources = {}

    for i in range(num_requests):
        success, elapsed, src = await client.execute_request(request_id=i, enable_hedging=True)
        sources[src] = sources.get(src, 0) + 1
        if success:
            resilient_latencies.append(elapsed * 1000)
        else:
            resilient_failures += 1
        await asyncio.sleep(0.01)

    # Perhitungan Statistik
    def calc_percentiles(data):
        if not data:
            return 0, 0, 0
        sorted_d = sorted(data)
        p50 = statistics.median(sorted_d)
        p90 = sorted_d[int(0.90 * len(sorted_d))]
        p99 = sorted_d[int(0.99 * len(sorted_d))]
        return p50, p90, p99

    b_p50, b_p90, b_p99 = calc_percentiles(baseline_latencies)
    r_p50, r_p90, r_p99 = calc_percentiles(resilient_latencies)

    print("\n" + "=" * 80)
    print(f"{'Metrik Benchmark':<25} | {'Baseline (No Hedge)':<22} | {'Resilient Pattern':<22}")
    print("-" * 80)
    print(f"{'Sukses Rate':<25} | {f'{num_requests - baseline_failures}/{num_requests}':<22} | {f'{num_requests - resilient_failures}/{num_requests}':<22}")
    print(f"{'Latency p50 (Median)':<25} | {f'{b_p50:.2f} ms':<22} | {f'{r_p50:.2f} ms':<22}")
    print(f"{'Latency p90':<25} | {f'{b_p90:.2f} ms':<22} | {f'{r_p90:.2f} ms':<22}")
    print(f"{'Latency p99 (Tail)':<25} | {f'{b_p99:.2f} ms':<22} | {f'{r_p99:.2f} ms':<22}")
    print("=" * 80)

    print("\nDistribusi Pemrosesan Resilient Client:")
    for src, count in sources.items():
        print(f" - {src:<30}: {count} requests ({count/num_requests*100:.1f}%)")

    improvement = ((b_p99 - r_p99) / b_p99) * 100 if b_p99 > 0 else 0
    print(f"\n[Kesimpulan SRE]: Request Hedging berhasil mereduksi tail latency p99 sebesar {improvement:.1f}%!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
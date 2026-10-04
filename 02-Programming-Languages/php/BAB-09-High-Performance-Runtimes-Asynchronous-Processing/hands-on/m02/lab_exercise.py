#!/usr/bin/env python3
"""
Lab Hands-on: High-Performance PHP Runtimes & Asynchronous Processing
Fokus: Perbandingan Arsitektur PHP-FPM (Shared-Nothing) vs Persistent Async Runtime (Swoole/RoadRunner/FrankenPHP)
dan Mitigasi State Leakage pada Persistent Memory Model.
"""

import asyncio
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_RED = "\033[31m"

@dataclass
class HttpRequest:
    request_id: str
    path: str
    user_id: int
    simulated_io_ms: float

@dataclass
class ExecutionResult:
    runtime: str
    total_time_ms: float
    requests_processed: int
    throughput_rps: float
    avg_latency_ms: float
    state_corrupted: bool

class StaticLeakMock:
    """
    Simulasi container global/static state pada PHP (misal: Singleton atau Global Registry).
    Dalam runtime persisten, variabel static tidak dibersihkan otomatis per request.
    """
    _shared_context: Dict[str, Any] = {}

    @classmethod
    def set(cls, key: str, val: Any) -> None:
        cls._shared_context[key] = val

    @classmethod
    def get(cls, key: str) -> Any:
        return cls._shared_context.get(key)

    @classmethod
    def reset(cls) -> None:
        cls._shared_context.clear()


class PhpFpmRuntimeSimulator:
    """
    Simulasi model PHP-FPM klasik:
    - Shared-Nothing architecture.
    - Set Up / Bootstrap Overhead per request (autoloading, parsing, container build).
    - Synchronous blocking I/O (DB, cURL, File).
    - Teardown & memory cleanup menyeluruh saat request selesai.
    """
    BOOTSTRAP_OVERHEAD_MS = 6.0  # Overhead framework boot (Symfony/Laravel cold loop)
    WORKER_POOL_SIZE = 4         # Simulates pm.max_children = 4

    def handle_request(self, req: HttpRequest) -> float:
        start = time.perf_counter()
        
        # 1. Framework Bootstrapping per request
        time.sleep(self.BOOTSTRAP_OVERHEAD_MS / 1000.0)
        
        # 2. Inisialisasi Environment & Memory Isolasi
        StaticLeakMock.reset()
        StaticLeakMock.set("current_user", req.user_id)
        
        # 3. Synchronous Blocking I/O Simulation
        time.sleep(req.simulated_io_ms / 1000.0)
        
        # 4. Verifikasi Isolasi State (Aman di FPM karena memori di-reset per request)
        resolved_user = StaticLeakMock.get("current_user")
        assert resolved_user == req.user_id, "FPM state isolation failure"
        
        # 5. Teardown / RSHUTDOWN
        StaticLeakMock.reset()
        
        return (time.perf_counter() - start) * 1000.0

    def run_benchmark(self, requests: List[HttpRequest]) -> ExecutionResult:
        start_all = time.perf_counter()
        latencies = []
        
        # Simulasi worker pool sederhana memproses antrean request
        # 4 worker menangani beban secara concurrent batch
        for i in range(0, len(requests), self.WORKER_POOL_SIZE):
            chunk = requests[i:i + self.WORKER_POOL_SIZE]
            # Karena FPM process blocking, latency chunk ditentukan oleh total waktu worker
            for r in chunk:
                latencies.append(self.handle_request(r))
                
        total_time_ms = (time.perf_counter() - start_all) * 1000.0
        rps = (len(requests) / (total_time_ms / 1000.0))
        avg_latency = sum(latencies) / len(latencies)

        return ExecutionResult(
            runtime="Traditional PHP-FPM",
            total_time_ms=total_time_ms,
            requests_processed=len(requests),
            throughput_rps=rps,
            avg_latency_ms=avg_latency,
            state_corrupted=False
        )


class PersistentAsyncRuntimeSimulator:
    """
    Simulasi persistent runtime (Swoole / FrankenPHP / RoadRunner):
    - Framework bootstrap hanya dijalankan 1 kali saat worker start (Warm Boot).
    - Event-driven non-blocking I/O multiplexing via Coroutine / Fiber engine.
    - Resiko State Leakage jika developer menyimpan context pada static/singleton.
    """
    def __init__(self, simulate_state_leak: bool = False):
        self.simulate_state_leak = simulate_state_leak
        self.state_corrupted = False
        self._framework_bootstrapped = False

    def bootstrap_framework(self) -> None:
        """Booting kernel, registering service providers (hanya 1x)."""
        time.sleep(8.0 / 1000.0)
        self._framework_bootstrapped = True

    async def _handle_request_coroutine(self, req: HttpRequest, fiber_context: dict) -> float:
        req_start = time.perf_counter()

        if self.simulate_state_leak:
            # BUG: Menyimpan state request langsung ke global static (Pola anti di Swoole/RoadRunner)
            StaticLeakMock.set("active_tenant", req.user_id)
        else:
            # FIX: Coroutine Context isolation (seperti Swoole\\Coroutine::getContext())
            fiber_context["active_tenant"] = req.user_id

        # Non-blocking async I/O simulation (Database query / Microservice call)
        await asyncio.sleep(req.simulated_io_ms / 1000.0)

        # Verifikasi integritas state
        if self.simulate_state_leak:
            retrieved = StaticLeakMock.get("active_tenant")
            if retrieved != req.user_id:
                self.state_corrupted = True
        else:
            retrieved = fiber_context.get("active_tenant")
            assert retrieved == req.user_id

        return (time.perf_counter() - req_start) * 1000.0

    async def run_benchmark_async(self, requests: List[HttpRequest]) -> ExecutionResult:
        # Step 1: Warm boot
        boot_start = time.perf_counter()
        self.bootstrap_framework()
        boot_time = (time.perf_counter() - boot_start) * 1000.0

        benchmark_start = time.perf_counter()
        
        # Step 2: Concurrently dispatch non-blocking Coroutines
        tasks = []
        for req in requests:
            fiber_ctx = {} # Coroutine-local context
            task = asyncio.create_task(self._handle_request_coroutine(req, fiber_ctx))
            tasks.append(task)

        latencies = await asyncio.gather(*tasks)
        total_time_ms = (time.perf_counter() - benchmark_start) * 1000.0
        rps = len(requests) / (total_time_ms / 1000.0)
        avg_latency = sum(latencies) / len(latencies)

        return ExecutionResult(
            runtime="Async Persistent (Swoole/RoadRunner)",
            total_time_ms=total_time_ms,
            requests_processed=len(requests),
            throughput_rps=rps,
            avg_latency_ms=avg_latency,
            state_corrupted=self.state_corrupted
        )


def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_YELLOW}>>> {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")

def print_result_row(res: ExecutionResult) -> None:
    print(f"{CLR_BOLD}{CLR_BLUE}[Runtime: {res.runtime}]{CLR_RESET}")
    print(f"  • Total Processed : {res.requests_processed} requests")
    print(f"  • Total Wall Time : {res.total_time_ms:.2f} ms")
    print(f"  • Avg Latency/Req : {res.avg_latency_ms:.2f} ms")
    print(f"  • Throughput      : {CLR_GREEN}{res.throughput_rps:.2f} req/sec{CLR_RESET}")
    leak_status = f"{CLR_RED}DETECTED (Data Poisoning!){CLR_RESET}" if res.state_corrupted else f"{CLR_GREEN}CLEAN (Isolated Context){CLR_RESET}"
    print(f"  • State Leakage   : {leak_status}\n")

async def main():
    print_header("LAB ENGINE: PHP HIGH-PERFORMANCE RUNTIMES & FIBER/ASYNC EVALUATOR")
    print("Menganalisis perbedaan arsitektur antara synchronous PHP-FPM dengan")
    print("persistent event-loop/coroutine engine (Swoole, RoadRunner, FrankenPHP).\n")

    # Generate payload: 16 request HTTP dengan I/O database sintetis (12-25ms)
    random.seed(42)
    requests = [
        HttpRequest(
            request_id=f"req_{idx:03d}",
            path=f"/api/v1/resource/{idx}",
            user_id=1000 + idx,
            simulated_io_ms=random.uniform(12.0, 22.0)
        )
        for idx in range(16)
    ]

    # --- EXPERIMENT 1: PHP-FPM (Traditional Shared-Nothing) ---
    print(f"{CLR_BOLD}Phase 1: Mengeksekusi beban kerja di PHP-FPM Classic Worker Pool...{CLR_RESET}")
    fpm_sim = PhpFpmRuntimeSimulator()
    fpm_result = fpm_sim.run_benchmark(requests)
    print_result_row(fpm_result)

    # --- EXPERIMENT 2: Persistent Async Engine with Proper Coroutine Isolation ---
    print(f"{CLR_BOLD}Phase 2: Mengeksekusi pada Persistent Async Engine (Isolated Context)...{CLR_RESET}")
    async_sim = PersistentAsyncRuntimeSimulator(simulate_state_leak=False)
    async_result = await async_sim.run_benchmark_async(requests)
    print_result_row(async_result)

    # --- EXPERIMENT 3: Persistent Runtime with State Leak Trap (Anti-Pattern) ---
    print(f"{CLR_BOLD}Phase 3: Uji Kerentanan State Leak (Penggunaan Static Variable Global)...{CLR_RESET}")
    leaky_sim = PersistentAsyncRuntimeSimulator(simulate_state_leak=True)
    leaky_result = await leaky_sim.run_benchmark_async(requests)
    print_result_row(leaky_result)

    # --- SUMMARY & COMPARISON ---
    speedup = async_result.throughput_rps / fpm_result.throughput_rps
    latency_reduction = (1 - (async_result.avg_latency_ms / fpm_result.avg_latency_ms)) * 100

    print_header("DIAGNOSA TEKNIS & KESIMPULAN ARSITEKTURAL")
    print(f"1. {CLR_BOLD}Throughput Gain:{CLR_RESET} Runtime Persisten {CLR_GREEN}{speedup:.2f}x lebih cepat{CLR_RESET} dibanding FPM.")
    print(f"2. {CLR_BOLD}Boot Elimination:{CLR_RESET} FPM membayar bootstrap overhead ~{PhpFpmRuntimeSimulator.BOOTSTRAP_OVERHEAD_MS}ms per request,")
    print("   sedangkan Async Persistent engine hanya menginisialisasi framework satu kali.")
    print(f"3. {CLR_BOLD}Concurrency Model:{CLR_RESET} FPM tertahan pada I/O blocking thread, sementara Async engine")
    print("   melakukan multiplexing I/O via Coroutine/Fiber scheduling.")
    print(f"4. {CLR_BOLD}State Pitfall:{CLR_RESET} Phase 3 mendemonstrasikan bahaya 'Static Pollution' di runtime persisten.")
    print("   Solusi arsitektur: Gunakan Reset Interfaces, Request-scoped DI container,")
    print("   atau Context Provider lokal (misal: Swoole\\Coroutine::getContext()).\n")

if __name__ == "__main__":
    asyncio.run(main())
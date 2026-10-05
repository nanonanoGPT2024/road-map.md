#!/usr/bin/env python3
"""
Lab Exercise: Asynchronous Django, Distributed Task Queues & Advanced Caching
BAB-08: Asynchronous Django, Distributed Tasks & Caching

Simulasi arsitektur produksi Django tingkat lanjut:
1. ASGI Asynchronous Views & Concurrency Handling (asyncio)
2. Distributed Task Queue (Celery Worker + Broker + Retry / Exponential Backoff)
3. Production Caching Strategies (Cache-Aside, Dogpile Lock / Stampede Prevention)
4. Real-time Event Streaming (Django Channels Layer Simulation)
"""

import sys
import time
import uuid
import random
import asyncio
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

# ==========================================
# Terminal ANSI Color Palette
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


def header(title: str) -> None:
    print(f"\n{Style.BOLD}{Style.BG_BLUE}{Style.WHITE} === {title} === {Style.RESET}\n")


def log_step(component: str, msg: str, color: str = Style.CYAN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Style.DIM}[{timestamp}]{Style.RESET} {color}[{component:^14}]{Style.RESET} {msg}")


# ==========================================
# 1. Distributed Cache (Redis Simulator)
# ==========================================
@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class RedisCacheSimulator:
    """Simulasi in-memory Redis cluster dengan support TTL dan Mutex Lock."""
    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        entry = self._store.get(key)
        if entry:
            if entry.expires_at > now:
                return entry.value
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def acquire_lock(self, lock_key: str) -> threading.Lock:
        with self._global_lock:
            if lock_key not in self._locks:
                self._locks[lock_key] = threading.Lock()
            return self._locks[lock_key]


# ==========================================
# 2. Distributed Task Queue (Celery Simulator)
# ==========================================
@dataclass
class CeleryTask:
    task_id: str
    name: str
    args: tuple
    kwargs: dict
    retries: int = 0
    max_retries: int = 3


class CeleryClusterSimulator:
    """Simulasi Celery Worker dengan RabbitMQ/Redis Broker & Retry Backoff."""
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.dead_letter_queue: list = []
        self.results: Dict[str, Any] = {}
        self._running = False

    async def enqueue(self, name: str, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = CeleryTask(task_id=task_id, name=name, args=args, kwargs=kwargs)
        await self.queue.put(task)
        log_step("CELERY-BROKER", f"Task {Style.BOLD}{name} [{task_id}]{Style.RESET} diteruskan ke Queue broker.", Style.YELLOW)
        return task_id

    async def worker_loop(self, worker_id: int):
        while self._running:
            try:
                task: CeleryTask = await asyncio.wait_for(self.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            log_step(f"WORKER-{worker_id}", f"Memulai eksekusi task: {task.name} ({task.task_id})", Style.BLUE)
            
            # Simulasi eksekusi task dengan kemungkinan gagal & retry
            success = False
            simulated_failure = task.kwargs.get("simulate_error", False) and task.retries == 0

            await asyncio.sleep(0.4)  # Simulasi IO/Processing time

            if simulated_failure:
                task.retries += 1
                backoff = 0.5 * (2 ** (task.retries - 1))
                log_step(
                    f"WORKER-{worker_id}",
                    f"{Style.RED}Task {task.task_id} Gagal!{Style.RESET} Retry {task.retries}/{task.max_retries} dalam {backoff:.1f}s (Exponential Backoff)",
                    Style.RED
                )
                await asyncio.sleep(backoff)
                await self.queue.put(task)
            else:
                success = True
                result = f"DONE: {task.name} with payload={task.args}"
                self.results[task.task_id] = result
                log_step(
                    f"WORKER-{worker_id}",
                    f"{Style.GREEN}Task {task.task_id} Selesai! Result disimpan ke Backend.{Style.RESET}",
                    Style.GREEN
                )
            self.queue.task_done()


# ==========================================
# 3. High-Concurrency Cache-Aside & Stampede Prevention
# ==========================================
async def fetch_expensive_db_record(record_id: int) -> dict:
    """Simulasi query agregasi berat database PostgreSQL (200ms delay)."""
    await asyncio.sleep(0.2)
    return {
        "id": record_id,
        "name": f"Analytics_Report_{record_id}",
        "computed_sum": random.randint(10000, 99999),
        "timestamp": time.time(),
    }


async def get_or_set_cached_data_stampede_safe(cache: RedisCacheSimulator, key: str, record_id: int) -> dict:
    """Implementasi Cache-Aside dengan Distributed Mutex Lock (Mencegah Dogpile/Stampede)."""
    cached = cache.get(key)
    if cached is not None:
        log_step("CACHE-HIT", f"Key '{key}' ditemukan di Redis Cache Memory.", Style.GREEN)
        return cached

    log_step("CACHE-MISS", f"Key '{key}' tidak ada. Meminta Mutex Lock untuk mencegah Stampede.", Style.MAGENTA)
    lock = cache.acquire_lock(f"lock:{key}")

    # Re-check setelah lock (Double-Checked Locking Pattern)
    with lock:
        cached_double_check = cache.get(key)
        if cached_double_check is not None:
            log_step("CACHE-LOCK", f"Key '{key}' sudah di-populate oleh thread rival (Stampede terhindar).", Style.GREEN)
            return cached_double_check

        log_step("DB-FALLBACK", f"Eksekusi Expensive Query ke Primary DB untuk id={record_id}...", Style.RED)
        data = await fetch_expensive_db_record(record_id)
        cache.set(key, data, ttl_seconds=3.0)
        log_step("CACHE-STORE", f"Data berhasil disimpan ke Redis Cache (TTL: 3.0s)", Style.CYAN)
        return data


# ==========================================
# 4. Asynchronous View Benchmark
# ==========================================
async def async_view_handler(request_id: int) -> str:
    """Simulasi Async View (ASGI) Django 4.2+ / 5.x non-blocking call."""
    await asyncio.sleep(0.1)  # Non-blocking IO simulate
    return f"Response for Req #{request_id}"


def sync_view_handler(request_id: int) -> str:
    """Simulasi Synchronous View (WSGI) Django blocking call."""
    time.sleep(0.1)  # Blocking IO
    return f"Response for Req #{request_id}"


async def run_benchmark_comparison():
    header("BENCHMARK: ASYNC VIEW (ASGI) VS SYNC VIEW (WSGI)")
    total_requests = 15
    print(f"Mengirim {total_requests} request konkuren simulasi IO external API (100ms per request)...\n")

    # 1. Benchmark Sync
    start_sync = time.time()
    log_step("WSGI-TEST", f"Menjalankan {total_requests} sync requests bertahap (Sequential Blocking)...", Style.YELLOW)
    for i in range(total_requests):
        sync_view_handler(i)
    sync_duration = time.time() - start_sync
    print(f"{Style.RED}Total Waktu WSGI (Sync) : {sync_duration:.3f} detik{Style.RESET}")

    # 2. Benchmark Async
    start_async = time.time()
    log_step("ASGI-TEST", f"Menjalankan {total_requests} async requests (Concurrent non-blocking asyncio.gather)...", Style.CYAN)
    tasks = [async_view_handler(i) for i in range(total_requests)]
    await asyncio.gather(*tasks)
    async_duration = time.time() - start_async
    print(f"{Style.GREEN}Total Waktu ASGI (Async): {async_duration:.3f} detik{Style.RESET}")

    speedup = sync_duration / async_duration if async_duration > 0 else 1.0
    print(f"\n{Style.BOLD}{Style.WHITE}Hasil: ASGI {speedup:.1f}x lebih efisien pada IO-bound concurrency workload.{Style.RESET}\n")


# ==========================================
# 5. Full Distributed Flow Interactive Demo
# ==========================================
async def run_full_production_flow():
    header("SIMULASI PIPELINE DISTRIBUSI LENGKAP PRODUKSI")
    cache = RedisCacheSimulator()
    celery = CeleryClusterSimulator()
    celery._running = True

    # Jalankan 2 concurrent background workers
    worker_tasks = [
        asyncio.create_task(celery.worker_loop(worker_id=1)),
        asyncio.create_task(celery.worker_loop(worker_id=2)),
    ]

    print(f"{Style.CYAN}Step 1: Request masuk ke Django Async View (Order Checkout flow){Style.RESET}")
    user_id = 1042
    cache_key = f"user_cart:{user_id}"

    # Cache-Aside Test
    cart = await get_or_set_cached_data_stampede_safe(cache, cache_key, user_id)
    print(f"Cart Data: {cart['name']} (Computed Val: {cart['computed_sum']})")

    # Second hit (Cache Hit)
    print(f"\n{Style.CYAN}Step 2: Request kedua untuk resource yang sama (Verifikasi Hit){Style.RESET}")
    await get_or_set_cached_data_stampede_safe(cache, cache_key, user_id)

    # Celery Async Offload
    print(f"\n{Style.CYAN}Step 3: Offload tugas berat ke Background Worker (Generate PDF Invoice & Email Notification){Style.RESET}")
    task_id1 = await celery.enqueue("tasks.generate_pdf_invoice", {"order_id": 9981}, simulate_error=True)
    task_id2 = await celery.enqueue("tasks.send_realtime_broadcast", {"channel": "notifications_all"}, simulate_error=False)

    print(f"{Style.DIM}Menunggu background worker menyelesaikan antrean...{Style.RESET}")
    await asyncio.sleep(2.0)

    # Cache Invalidation on Mutation
    print(f"\n{Style.CYAN}Step 4: Database Model Save Signal Triggered -> Invalidate Redis Cache{Style.RESET}")
    cache.delete(cache_key)
    log_step("SIGNAL", f"post_save signal membersihkan cache key '{cache_key}'", Style.RED)

    # Post-invalidation Hit
    print(f"\n{Style.CYAN}Step 5: Verifikasi Cache-Aside setelah Invalidation{Style.RESET}")
    await get_or_set_cached_data_stampede_safe(cache, cache_key, user_id)

    # Cleanup workers
    celery._running = False
    await asyncio.gather(*worker_tasks, return_exceptions=True)
    print(f"\n{Style.GREEN}{Style.BOLD}Pipeline Produksi Selesai Dijalankan dengan Sukses!{Style.RESET}\n")


# ==========================================
# 6. Interactive CLI Main Loop
# ==========================================
def print_menu():
    print(f"{Style.BOLD}{Style.WHITE}Django Advanced Architecture Lab Playground:{Style.RESET}")
    print(f" {Style.CYAN}1.{Style.RESET} Run Async vs Sync View Concurrency Benchmark")
    print(f" {Style.CYAN}2.{Style.RESET} Run Cache Stampede & Distributed Mutex Lock Demo")
    print(f" {Style.CYAN}3.{Style.RESET} Run Celery Task Queue Worker + Retry Backoff Demo")
    print(f" {Style.CYAN}4.{Style.RESET} Run Full End-to-End Distributed Architecture Demo")
    print(f" {Style.CYAN}5.{Style.RESET} Exit Lab")


async def run_cache_stampede_demo():
    header("DEMO: CACHE STAMPEDE (DOGPILE EFFECT) PREVENTION")
    cache = RedisCacheSimulator()
    key = "global_leaderboard"

    log_step("STAMPEDE-SIM", "Mengirim 8 request konkuren serentak saat cache kosong...", Style.YELLOW)
    
    # 8 concurrent requests simultaneously attempting to read empty cache
    async def client_request(cid: int):
        await asyncio.sleep(random.uniform(0.01, 0.05))
        return await get_or_set_cached_data_stampede_safe(cache, key, 777)

    results = await asyncio.gather(*[client_request(i) for i in range(8)])
    print(f"\n{Style.GREEN}Seluruh 8 concurrent request selesai. Database hanya di-query 1x berkat Mutex Lock!{Style.RESET}\n")


async def run_celery_demo():
    header("DEMO: CELERY WORKER, BROKER & AUTOMATIC RETRY BACKOFF")
    celery = CeleryClusterSimulator()
    celery._running = True

    worker = asyncio.create_task(celery.worker_loop(worker_id=1))

    await celery.enqueue("tasks.send_slack_alert", {"msg": "Server Load Alert"}, simulate_error=True)
    await celery.enqueue("tasks.sync_stripe_webhooks", {"customer_id": "cus_9918"}, simulate_error=False)

    await asyncio.sleep(2.5)
    celery._running = False
    await worker
    print(f"\n{Style.GREEN}Celery Worker antrean tuntas.{Style.RESET}\n")


async def async_main():
    # If run in non-interactive environment (CI / pipe) or with --demo argument
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        await run_benchmark_comparison()
        await run_cache_stampede_demo()
        await run_celery_demo()
        await run_full_production_flow()
        return

    # Interactive Loop
    while True:
        print_menu()
        try:
            choice = input(f"{Style.BOLD}{Style.YELLOW}Pilih opsi [1-5]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab...")
            break

        if choice == "1":
            await run_benchmark_comparison()
        elif choice == "2":
            await run_cache_stampede_demo()
        elif choice == "3":
            await run_celery_demo()
        elif choice == "4":
            await run_full_production_flow()
        elif choice == "5":
            print(f"{Style.GREEN}Terima kasih telah mengikuti Lab BAB-08! Sampai jumpa.{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 1-5.{Style.RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nLab terminated by user.")

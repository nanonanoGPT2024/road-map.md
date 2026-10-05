#!/usr/bin/env python3
"""
=============================================================================
LAB EXERCISE M01: ASYNCHRONOUS DJANGO, DISTRIBUTED TASKS & CACHING FOUNDATION
BAB-08: Asynchronous Django, Distributed Tasks & Caching
=============================================================================
Simulasi komprehensif konsep fondasi inti:
1. ASGI Non-blocking Request Lifecycle & Sync-to-Async / Async-to-Sync Adapter
2. Distributed Task Queue (Broker-Worker Architecture, Retries & State Tracking)
3. Advanced Caching Engine (Cache-Aside Strategy, TTL Invalidation & Hit Ratio)
4. Integrated Pipeline (Async API Endpoint + Cache + Async Task Offloading)

Dibuat untuk eksekusi mandiri (Python 3.8+) tanpa dependensi eksternal.
=============================================================================
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# =============================================================================
# ANSI COLOR CONSTANTS
# =============================================================================
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner(title: str):
    width = 75
    print(f"\n{Colors.CYAN}{'=' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW} {title.center(width - 2)} {Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * width}{Colors.RESET}")


def print_section(title: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}>>> [STEP] {title}{Colors.RESET}")


# =============================================================================
# KOMPONEN 1: ASGI & SYNC-TO-ASYNC ADAPTER SIMULATION
# =============================================================================
class MockORMDatabase:
    """Simulasi Django Synchronous ORM yang memblokir Event Loop jika tidak diisolasi."""

    def __init__(self):
        self._data = {
            101: {"id": 101, "name": "Budi Santoso", "tier": "VIP", "balance": 4500000},
            102: {"id": 102, "name": "Siti Nurhaliza", "tier": "Standard", "balance": 1200000},
            103: {"id": 103, "name": "Rian Pratama", "tier": "VIP", "balance": 9800000},
        }

    def sync_query(self, user_id: int) -> Optional[Dict[str, Any]]:
        # Simulasi operasi blocking I/O (misal: psycopg2 / PostgreSQL connection)
        time.sleep(0.35)
        return self._data.get(user_id)


async def sync_to_async_adapter(sync_fn: Callable, *args, **kwargs) -> Any:
    """
    Simulasi `asgiref.sync.sync_to_async`:
    Mendelegasikan fungsi blocking synchronous ke threadpool worker
    sehingga ASGI Event Loop utama tetap non-blocking.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sync_fn, *args, **kwargs)


# =============================================================================
# KOMPONEN 2: MULTI-TIER CACHE ENGINE (CACHE-ASIDE PATTERN)
# =============================================================================
@dataclass
class CacheEntry:
    val: Any
    expires_at: float


class InMemoryCacheEngine:
    """Simulasi Django Cache Framework (Redis/Memcached backend) dengan TTL."""

    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self.hits: int = 0
        self.misses: int = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry.val

    def set(self, key: str, val: Any, timeout: float = 2.0) -> None:
        self._store[key] = CacheEntry(val=val, expires_at=time.time() + timeout)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100.0) if total > 0 else 0.0


# =============================================================================
# KOMPONEN 3: DISTRIBUTED TASK QUEUE (CELERY ARCHITECTURE SIMULATOR)
# =============================================================================
class TaskState(Enum):
    PENDING = "PENDING"
    RETRY = "RETRY"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


@dataclass
class CeleryTaskMessage:
    task_id: str
    task_name: str
    args: tuple
    kwargs: dict
    retries: int = 0
    max_retries: int = 3
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: Optional[str] = None


class DistributedTaskQueue:
    """Simulasi Message Broker (Redis/RabbitMQ) dan Worker Pool."""

    def __init__(self):
        self.queue: asyncio.Queue[CeleryTaskMessage] = asyncio.Queue()
        self.backend: Dict[str, CeleryTaskMessage] = {}
        self.is_running: bool = False
        self._workers: List[asyncio.Task] = []

    def delay(self, task_name: str, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())[:8]
        msg = CeleryTaskMessage(
            task_id=task_id,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
        )
        self.backend[task_id] = msg
        self.queue.put_nowait(msg)
        return task_id

    async def _worker_loop(self, worker_id: int):
        while self.is_running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            task.state = TaskState.STARTED
            print(
                f"  {Colors.DIM}[Worker-{worker_id}]{Colors.RESET} Memproses Task "
                f"{Colors.YELLOW}{task.task_id}{Colors.RESET} ({task.task_name})..."
            )

            try:
                # Simulasi eksekusi background job
                if task.task_name == "send_push_notification":
                    user_id, message = task.args
                    await asyncio.sleep(0.3)
                    task.result = f"Push notification dikirim ke User {user_id}: '{message}'"
                    task.state = TaskState.SUCCESS
                elif task.task_name == "generate_pdf_report":
                    user_id = task.args[0]
                    # Simulasi kegagalan intermiten dengan mekanisme retry
                    if task.retries < 1:
                        task.retries += 1
                        task.state = TaskState.RETRY
                        print(
                            f"  {Colors.RED}✖ [Worker-{worker_id}] Task {task.task_id} gagal I/O! "
                            f"Scheduling Retry ({task.retries}/{task.max_retries})...{Colors.RESET}"
                        )
                        await asyncio.sleep(0.2)
                        await self.queue.put(task)
                        self.queue.task_done()
                        continue
                    await asyncio.sleep(0.4)
                    task.result = f"PDF Report Finansial User {user_id} selesai dibuat (1.4 MB)"
                    task.state = TaskState.SUCCESS
                else:
                    task.state = TaskState.FAILURE
                    task.error = f"Unknown task: {task.task_name}"

                print(
                    f"  {Colors.GREEN}✔ [Worker-{worker_id}] Task {task.task_id} status: {task.state.value}{Colors.RESET}"
                )
            except Exception as ex:
                task.state = TaskState.FAILURE
                task.error = str(ex)
            finally:
                self.queue.task_done()

    def start_workers(self, worker_count: int = 2):
        self.is_running = True
        for i in range(1, worker_count + 1):
            self._workers.append(asyncio.create_task(self._worker_loop(i)))

    async def stop_workers(self):
        self.is_running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()


# =============================================================================
# SIMULASI SKENARIO LAB
# =============================================================================
db = MockORMDatabase()
cache = InMemoryCacheEngine()
task_queue = DistributedTaskQueue()


async def demo_asgi_vs_sync():
    print_section("1. Perbandingan Karakteristik: Blocking Sync vs Non-blocking ASGI")
    print("Skenario: Memproses 3 request konkuren untuk membaca data ORM.")

    # 1. Blocking Approach (Melumpuhkan Event Loop jika dijalankan langsung)
    start_time = time.perf_counter()
    print(f"\n{Colors.YELLOW}[A] Simulasi Sync Tradisional (Blocking sequential):{Colors.RESET}")
    for uid in [101, 102, 103]:
        res = db.sync_query(uid)
        print(f"    - User {uid}: {res['name']} ({res['tier']})")
    seq_duration = time.perf_counter() - start_time
    print(f"    {Colors.RED}Total waktu Sync: {seq_duration:.3f} detik{Colors.RESET}")

    # 2. Asynchronous ASGI with sync_to_async adapter
    start_time = time.perf_counter()
    print(f"\n{Colors.GREEN}[B] Simulasi ASGI + sync_to_async (Concurrent non-blocking):{Colors.RESET}")

    async def fetch_user_async(uid: int):
        data = await sync_to_async_adapter(db.sync_query, uid)
        print(f"    - [ASGI Threadpool] User {uid}: {data['name']} ({data['tier']})")
        return data

    await asyncio.gather(
        fetch_user_async(101),
        fetch_user_async(102),
        fetch_user_async(103),
    )
    async_duration = time.perf_counter() - start_time
    print(f"    {Colors.GREEN}Total waktu Concurrent ASGI: {async_duration:.3f} detik{Colors.RESET}")
    speedup = ((seq_duration - async_duration) / seq_duration) * 100
    print(f"    {Colors.BOLD}Efisiensi throughput meningkat: +{speedup:.1f}%{Colors.RESET}")


async def demo_cache_aside():
    print_section("2. Pola Cache-Aside (Django Cache Framework)")
    cache.clear()

    async def get_user_profile(uid: int):
        cache_key = f"user_cache:{uid}"
        # 1. Look in Cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"  {Colors.GREEN}[CACHE HIT]{Colors.RESET} Mengambil key '{cache_key}' dari RAM.")
            return cached_data

        # 2. Cache Miss -> Query Database
        print(f"  {Colors.YELLOW}[CACHE MISS]{Colors.RESET} Querying database via sync_to_async...")
        data = await sync_to_async_adapter(db.sync_query, uid)

        # 3. Store to Cache with TTL 1.5 detik
        if data:
            cache.set(cache_key, data, timeout=1.5)
            print(f"  {Colors.CYAN}[CACHE STORE]{Colors.RESET} Menyimpan '{cache_key}' (TTL: 1.5s)")
        return data

    print("\n* Panggilan ke-1 (Cold Cache):")
    t0 = time.perf_counter()
    u1 = await get_user_profile(101)
    print(f"    Hasil: {u1['name']} (Latensi: {(time.perf_counter() - t0)*1000:.1f}ms)")

    print("\n* Panggilan ke-2 (Warm Cache - Hit):")
    t0 = time.perf_counter()
    u2 = await get_user_profile(101)
    print(f"    Hasil: {u2['name']} (Latensi: {(time.perf_counter() - t0)*1000:.1f}ms)")

    print(f"\n* Menunggu 1.8 detik hingga Cache Expiration (TTL Exceeded)...")
    await asyncio.sleep(1.8)

    print("\n* Panggilan ke-3 (Expired Cache - Stale Invalidation):")
    t0 = time.perf_counter()
    u3 = await get_user_profile(101)
    print(f"    Hasil: {u3['name']} (Latensi: {(time.perf_counter() - t0)*1000:.1f}ms)")

    print(f"\n{Colors.BOLD}Statistik Cache:{Colors.RESET}")
    print(f"  Hits: {cache.hits} | Misses: {cache.misses} | Hit Ratio: {cache.hit_ratio:.1f}%")


async def demo_distributed_pipeline():
    print_section("3. Pipeline Terintegrasi: Async View + Cache + Distributed Celery Worker")
    task_queue.start_workers(worker_count=2)

    try:
        print("Skenario: Request HTTP POST /api/v1/user/101/checkout masuk ke ASGI Handler.")

        async def handle_checkout_request(uid: int):
            t0 = time.perf_counter()
            print(f"  {Colors.CYAN}[ASGI Handler]{Colors.RESET} Request diterima untuk User #{uid}")

            # Step 1: Ambil data via Cache-Aside
            user_data = cache.get(f"user_cache:{uid}")
            if not user_data:
                user_data = await sync_to_async_adapter(db.sync_query, uid)
                cache.set(f"user_cache:{uid}", user_data, timeout=3.0)

            print(f"  {Colors.GREEN}[ASGI Handler]{Colors.RESET} User valid: {user_data['name']}")

            # Step 2: Offload background tasks (Non-blocking ke Client)
            task_pdf_id = task_queue.delay("generate_pdf_report", uid)
            task_notify_id = task_queue.delay(
                "send_push_notification",
                uid,
                f"Pesanan berhasil diproses! Sisa saldo: Rp{user_data['balance']:,}",
            )

            response_time = (time.perf_counter() - t0) * 1000
            print(
                f"  {Colors.BOLD}{Colors.GREEN}✔ [HTTP 200 OK]{Colors.RESET} Response dikirim ke client dalam "
                f"{Colors.BOLD}{response_time:.2f}ms{Colors.RESET}"
            )
            print(
                f"    -> Enqueued Background Tasks: [{task_pdf_id} (PDF), {task_notify_id} (Push Notif)]\n"
            )

            return [task_pdf_id, task_notify_id]

        dispatched_ids = await handle_checkout_request(101)

        print(f"{Colors.BLUE}[Celery Worker Pool]{Colors.RESET} Menunggu task worker selesai...")
        await asyncio.sleep(1.2)

        print(f"\n{Colors.BOLD}Status Akhir Task di Result Backend:{Colors.RESET}")
        for tid in dispatched_ids:
            task_record = task_queue.backend[tid]
            color = Colors.GREEN if task_record.state == TaskState.SUCCESS else Colors.RED
            print(
                f"  • Task [{task_record.task_id}] {task_record.task_name}: "
                f"{color}{task_record.state.value}{Colors.RESET} -> {task_record.result}"
            )

    finally:
        await task_queue.stop_workers()


async def run_all():
    print_banner("SIMULASI LABORATORIUM DJANGO ASGI, CELERY & CACHING")
    print(f"{Colors.DIM}Mempersiapkan infrastruktur simulasi in-memory...{Colors.RESET}")
    await asyncio.sleep(0.5)

    await demo_asgi_vs_sync()
    await demo_cache_aside()
    await demo_distributed_pipeline()

    print_banner("LABORATORIUM M01 SELESAI DENGAN SUKSES")
    print(f"{Colors.GREEN}Semua konsep fondasi telah diverifikasi dan berjalan normal.{Colors.RESET}\n")


def main():
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Simulasi dihentikan oleh user.{Colors.RESET}")


if __name__ == "__main__":
    main()

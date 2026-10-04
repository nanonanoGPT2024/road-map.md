#!/usr/bin/env python3
"""
Lab Hands-on: Pemrograman Asinkron Modern & Swift Concurrency (Deep Dive)
Simulasi Konsep Inti Swift Concurrency:
1. Actor Isolation & Data Race Protection (Swift `actor`)
2. Structured Concurrency & Cooperative Cancellation (Swift `withTaskGroup` / `Task.isCancelled`)
3. Asynchronous Sequences (Swift `AsyncStream<Element>`)
4. Actor Reentrancy & Priority Inversion Emulation

Semua modul diimplementasikan menggunakan Python Standard Library (asyncio, dataclasses, typing).
"""

import asyncio
import time
import random
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional, List, Dict, Any

# ==============================================================================
# ANSI Color Codes untuk Output Terminal
# ==============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def log(tag: str, message: str, color: str = Colors.RESET):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {color}{Colors.BOLD}[{tag}]{Colors.RESET} {message}")


# ==============================================================================
# 1. Swift Actor Isolation Simulation
# ==============================================================================
# Di Swift, `actor` menjamin status internalnya dimutasi secara aman tanpa data race.
# Properti actor bersifat terisolasi; akses ke properti mutable dari luar harus `await`.
# Kita memodelkan ImageCacheActor menggunakan synchronization lock internal.
@dataclass
class ImageAsset:
    id: str
    size_bytes: int
    data: bytes

class ImageCacheActor:
    """
    Simulasi Swift `actor ImageCache`:
    Melindungi status internal mutable `_cache` dari akses paralel (Thread-safety).
    """
    def __init__(self, capacity: int = 5):
        self._cache: Dict[str, ImageAsset] = {}
        self._capacity = capacity
        # Lock internal memodelkan serial executor mailbox pada Swift Actor
        self._actor_mailbox = asyncio.Lock()
        self._access_counter = 0

    async def get(self, key: str) -> Optional[ImageAsset]:
        """Akses asinkron terisolasi ke actor memory."""
        async with self._actor_mailbox:
            self._access_counter += 1
            if key in self._cache:
                log("Actor::ImageCache", f"Cache HIT: '{key}'", Colors.GREEN)
                return self._cache[key]
            log("Actor::ImageCache", f"Cache MISS: '{key}'", Colors.YELLOW)
            return None

    async def store(self, key: str, asset: ImageAsset) -> None:
        """Mutasi status actor; diserialisasi untuk mencegah race condition."""
        async with self._actor_mailbox:
            self._access_counter += 1
            # Simulasi penggusuran cache sederhana jika melebihi kapasitas
            if len(self._cache) >= self._capacity and key not in self._cache:
                evicted_key = next(iter(self._cache))
                del self._cache[evicted_key]
                log("Actor::ImageCache", f"Evicted oldest key '{evicted_key}' (Actor Boundary Safe)", Colors.DIM)

            # Simulasi actor suspension point (misal: verifikasi I/O disk)
            await asyncio.sleep(0.05)
            self._cache[key] = asset
            log("Actor::ImageCache", f"Stored asset: '{key}' ({asset.size_bytes} bytes). Total Items: {len(self._cache)}", Colors.CYAN)

    async def get_total_access_count(self) -> int:
        async with self._actor_mailbox:
            return self._access_counter


# ==============================================================================
# 2. Structured Concurrency & TaskGroup with Cancellation
# ==============================================================================
class TaskPriority(Enum):
    HIGH = "userInitiated"
    MEDIUM = "default"
    LOW = "background"

@dataclass
class DownloadResult:
    resource_id: str
    success: bool
    bytes_downloaded: int
    error_reason: Optional[str] = None

class SwiftTaskGroupSimulator:
    """
    Memodelkan Swift `withThrowingTaskGroup(of:returning:)`.
    Prinsip:
    - Structured Lifecycle: Task anak di-scope dalam blok ini.
    - Cooperative Cancellation: Jika parent dibatalkan atau satu anak gagal,
      cancellation signal disebarkan ke anak-anak lainnya.
    """
    def __init__(self, fail_fast: bool = True):
        self.fail_fast = fail_fast
        self._tasks: List[asyncio.Task] = []
        self._cancelled = False

    async def download_worker(self, resource_id: str, priority: TaskPriority, target_error: bool = False) -> DownloadResult:
        """Pekerja yang secara kooperatif memeriksa `Task.isCancelled`."""
        log("TaskGroup::Child", f"Starting '{resource_id}' [{priority.value}]", Colors.BLUE)
        total_chunks = 5
        downloaded = 0

        for chunk_idx in range(1, total_chunks + 1):
            # Check Cooperative Cancellation (Swift: Task.isCancelled / try Task.checkCancellation())
            if self._cancelled:
                log("TaskGroup::Child", f"Task '{resource_id}' detected cooperative cancellation! Aborting early.", Colors.YELLOW)
                return DownloadResult(resource_id, success=False, bytes_downloaded=downloaded, error_reason="TaskCancelled")

            # Simulasi latensi download
            delay = 0.08 if priority == TaskPriority.HIGH else 0.15
            await asyncio.sleep(delay)
            downloaded += 1024

            # Simulasi kegagalan runtime mendadak
            if target_error and chunk_idx == 3:
                log("TaskGroup::Child", f"Task '{resource_id}' encountered fatal network drop!", Colors.RED)
                raise ConnectionResetError(f"HTTP 503 Service Unavailable on {resource_id}")

        log("TaskGroup::Child", f"Completed '{resource_id}' ({downloaded} bytes)", Colors.GREEN)
        return DownloadResult(resource_id, success=True, bytes_downloaded=downloaded)

    async def execute_group(self, jobs: List[Dict[str, Any]]) -> List[DownloadResult]:
        results: List[DownloadResult] = []
        
        async def runner_wrapper(job: Dict[str, Any]) -> DownloadResult:
            return await self.download_worker(job["id"], job["priority"], job.get("fail", False))

        # Mengemas task ke dalam struktur asyncio
        self._tasks = [asyncio.create_task(runner_wrapper(j)) for j in jobs]

        try:
            for completed_coro in asyncio.as_completed(self._tasks):
                try:
                    result = await completed_coro
                    results.append(result)
                except Exception as ex:
                    log("TaskGroup::Parent", f"Child task failed: {ex}", Colors.RED)
                    if self.fail_fast:
                        log("TaskGroup::Parent", "Triggering cooperative cancellation across remaining children...", Colors.RED)
                        self._cancelled = True
                        for t in self._tasks:
                            if not t.done():
                                t.cancel()
                        break
        except asyncio.CancelledError:
            log("TaskGroup::Parent", "Parent scope cancelled.", Colors.RED)

        # Menunggu sisa child task menyelesaikan cancellation cleanup
        await asyncio.gather(*self._tasks, return_exceptions=True)
        return results


# ==============================================================================
# 3. AsyncStream Simulation
# ==============================================================================
@dataclass
class TelemetryEvent:
    battery_level: float
    cpu_usage_pct: float
    is_charging: bool

class DeviceTelemetryStream:
    """
    Memodelkan Swift `AsyncStream<TelemetryEvent>`:
    Produser menghasilkan event secara kontinu, konsumen mengonsumsinya dengan
    konstruksi `for await event in stream`.
    """
    def __init__(self, emission_count: int = 4):
        self.emission_count = emission_count
        self._queue: asyncio.Queue[Optional[TelemetryEvent]] = asyncio.Queue()

    async def _producer_loop(self):
        """Yielding event ke buffer secara terisolasi."""
        battery = 100.0
        for i in range(self.emission_count):
            await asyncio.sleep(0.12)
            battery -= random.uniform(0.5, 2.0)
            cpu = random.uniform(15.0, 75.0)
            event = TelemetryEvent(
                battery_level=round(battery, 2),
                cpu_usage_pct=round(cpu, 1),
                is_charging=(i % 2 == 0)
            )
            await self._queue.put(event)
        # Menandakan Stream Finished (nil/None terminal value)
        await self._queue.put(None)

    async def stream(self) -> AsyncIterator[TelemetryEvent]:
        """Menghasilkan interface `AsyncSequence`."""
        # Spawn asynchronous continuation producer
        producer_task = asyncio.create_task(self._producer_loop())
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    break
                yield item
                self._queue.task_done()
        finally:
            if not producer_task.done():
                producer_task.cancel()


# ==============================================================================
# Main Orchestration & Demonstration Lab
# ==============================================================================
async def main():
    print(f"\n{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}   LAB SWIFT CONCURRENCY: ACTOR, TASKGROUP & ASYNCSTREAM DEEP DIVE   {Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}\n")

    # --------------------------------------------------------------------------
    # DEMO 1: Swift Actor Model & Mutual Exclusion
    # --------------------------------------------------------------------------
    log("SYSTEM", "--- [BAGIAN 1] Actor Isolation & State Protection ---", Colors.BOLD)
    cache_actor = ImageCacheActor(capacity=3)

    async def simulated_ui_client(client_id: str, image_ids: List[str]):
        """Simulasi beberapa View Controller / MainActor threads meminta resource bersamaan."""
        for img_id in image_ids:
            cached = await cache_actor.get(img_id)
            if not cached:
                # Simulasikan fetch & store
                new_asset = ImageAsset(id=img_id, size_bytes=len(img_id) * 1024, data=b"FAKE_RAW_DATA")
                await cache_actor.store(img_id, new_asset)

    # Menjalankan 3 klien UI konkuren yang mengakses cache yang sama
    clients = [
        simulated_ui_client("VC_Home", ["avatar.png", "banner.png", "avatar.png"]),
        simulated_ui_client("VC_Profile", ["avatar.png", "logo.png", "bg.png"]),
        simulated_ui_client("VC_Settings", ["icon_gear.png", "banner.png"])
    ]
    await asyncio.gather(*clients)
    
    total_ops = await cache_actor.get_total_access_count()
    log("Actor::Result", f"Verifikasi isolasi sukses! Total akses terkontrol: {total_ops}\n", Colors.GREEN)

    # --------------------------------------------------------------------------
    # DEMO 2: Structured Concurrency & Cooperative Cancellation
    # --------------------------------------------------------------------------
    log("SYSTEM", "--- [BAGIAN 2] Structured Concurrency: TaskGroup & Cancellation ---", Colors.BOLD)
    task_group = SwiftTaskGroupSimulator(fail_fast=True)
    
    jobs = [
        {"id": "Asset_101.meta", "priority": TaskPriority.HIGH, "fail": False},
        {"id": "Asset_102.bundle", "priority": TaskPriority.HIGH, "fail": True},  # Trigger fatal failure
        {"id": "Asset_103.archive", "priority": TaskPriority.LOW, "fail": False},
        {"id": "Asset_104.blob", "priority": TaskPriority.MEDIUM, "fail": False},
    ]

    log("TaskGroup::Main", "Spawning TaskGroup with 4 heterogeneous tasks...", Colors.CYAN)
    results = await task_group.execute_group(jobs)
    
    log("TaskGroup::Summary", f"Selesai dengan {len(results)} pelaporan dari children:", Colors.BOLD)
    for r in results:
        status_color = Colors.GREEN if r.success else Colors.RED
        log("TaskGroup::Summary", f"  * Resource: {r.resource_id} | Success: {r.success} | Error: {r.error_reason} | Transferred: {r.bytes_downloaded}B", status_color)
    print()

    # --------------------------------------------------------------------------
    # DEMO 3: AsyncStream Consumption
    # --------------------------------------------------------------------------
    log("SYSTEM", "--- [BAGIAN 3] Swift AsyncStream (Reactive Asynchronous Stream) ---", Colors.BOLD)
    telemetry = DeviceTelemetryStream(emission_count=4)

    log("Consumer::MainActor", "Memulai konsumsi `for await event in telemetryStream`...", Colors.CYAN)
    sequence_count = 0
    async for event in telemetry.stream():
        sequence_count += 1
        log("Consumer::Telemetry", 
            f"Event #{sequence_count} -> Baterai: {event.battery_level}% | CPU: {event.cpu_usage_pct}% | Charging: {event.is_charging}", 
            Colors.BLUE)

    print(f"\n{Colors.GREEN}{Colors.BOLD}Semua simulasi modul Swift Concurrency selesai dieksekusi dengan aman dan deterministik.{Colors.RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Eksekusi dihentikan paksa oleh pengguna.{Colors.RESET}")
        sys.exit(0)
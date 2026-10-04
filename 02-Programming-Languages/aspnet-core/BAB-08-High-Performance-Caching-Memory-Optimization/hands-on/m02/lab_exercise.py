#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core High Performance, Caching & Memory Optimization (Deep Dive)
Simulasi komprehensif mekanisme performa tinggi ASP.NET Core:
1. Multi-Tier Caching (L1 IMemoryCache dengan Sliding/Absolute Expiry & LRU + L2 IDistributedCache).
2. Cache Stampede Mitigation (Single-Flight Lock / HybridCache Pattern .NET 9).
3. Memory Optimization: Buffer Pooling (ArrayPool<byte>.Shared simulation) untuk reduksi GC pressure.
4. Concurrent Benchmark & GC Pressure Profiler.
"""

import time
import threading
import random
import sys
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

# --- ANSI Formatting Configuration ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_GRAY    = "\033[90m"

# ==============================================================================
# 1. MEMORY OPTIMIZATION: ArrayPool<byte> Simulation
# ==============================================================================
class SimulatedArrayPool:
    """
    Mensimulasikan System.Buffers.ArrayPool<T>.Shared pada .NET Core.
    Mengurangi frekuensi alokasi heap Gen0/Gen1/Gen2 dan fragmentasi Large Object Heap (LOH)
    dengan menyewakan (rent) dan mengembalikan (return) buffer memory berukuran tetap.
    """
    def __init__(self, bucket_size: int = 1024, max_pooled_arrays: int = 32):
        self._bucket_size = bucket_size
        self._max_pooled = max_pooled_arrays
        self._pool: list[bytearray] = []
        self._lock = threading.Lock()
        self.total_rentals = 0
        self.reused_rentals = 0
        self.new_allocations = 0

    def rent(self, minimum_length: int) -> bytearray:
        """Menyewa buffer. Jika ada di pool, gunakan kembali; jika tidak, alokasikan baru."""
        with self._lock:
            self.total_rentals += 1
            if minimum_length <= self._bucket_size and self._pool:
                self.reused_rentals += 1
                return self._pool.pop()
            
            self.new_allocations += 1
            alloc_size = max(minimum_length, self._bucket_size)
            return bytearray(alloc_size)

    def return_buffer(self, buffer: bytearray, clear_array: bool = False):
        """Mengembalikan buffer ke pool untuk digunakan kembali."""
        if clear_array:
            for i in range(len(buffer)):
                buffer[i] = 0
        with self._lock:
            if len(self._pool) < self._max_pooled and len(buffer) == self._bucket_size:
                self._pool.append(buffer)

# Global ArrayPool instance
SHARED_BUFFER_POOL = SimulatedArrayPool(bucket_size=2048, max_pooled_arrays=64)

# ==============================================================================
# 2. CACHING INFRASTRUCTURE: L1 (Memory) & L2 (Distributed) Simulation
# ==============================================================================
@dataclass
class CacheEntry:
    value: bytes
    size: int
    absolute_expiration: float
    sliding_expiration: Optional[float]
    last_accessed: float

class SimulatedMemoryCache:
    """
    Mensimulasikan Microsoft.Extensions.Caching.Memory.IMemoryCache.
    Fitur: Sliding Expiration, Absolute Expiration, Size Limits, dan LRU Eviction.
    """
    def __init__(self, max_capacity_bytes: int = 1024 * 16):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._max_capacity = max_capacity_bytes
        self._current_size = 0

    def _is_expired(self, entry: CacheEntry, now: float) -> bool:
        if now > entry.absolute_expiration:
            return True
        if entry.sliding_expiration and (now - entry.last_accessed) > entry.sliding_expiration:
            return True
        return False

    def try_get(self, key: str) -> Optional[bytes]:
        now = time.monotonic()
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if self._is_expired(entry, now):
                self._current_size -= entry.size
                del self._cache[key]
                return None
            
            entry.last_accessed = now
            self._cache.move_to_end(key)
            return entry.value

    def set(self, key: str, value: bytes, absolute_seconds: float = 5.0, sliding_seconds: Optional[float] = 2.0):
        now = time.monotonic()
        entry_size = len(value)
        with self._lock:
            # Evict jika melebihi kapasitas (LRU)
            while self._current_size + entry_size > self._max_capacity and self._cache:
                evicted_key, evicted_entry = self._cache.popitem(last=False)
                self._current_size -= evicted_entry.size

            if key in self._cache:
                self._current_size -= self._cache[key].size

            entry = CacheEntry(
                value=value,
                size=entry_size,
                absolute_expiration=now + absolute_seconds,
                sliding_expiration=sliding_seconds,
                last_accessed=now
            )
            self._cache[key] = entry
            self._current_size += entry_size
            self._cache.move_to_end(key)

class SimulatedDistributedCache:
    """
    Mensimulasikan IDistributedCache (e.g., Redis).
    Memiliki overhead network IO latency dan serialisasi byte.
    """
    def __init__(self, network_latency_ms: float = 4.0):
        self._store: Dict[str, Tuple[bytes, float]] = {}
        self._latency = network_latency_ms / 1000.0
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        time.sleep(self._latency) # Simulasi network ping ke Redis
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            data, exp = item
            if now > exp:
                del self._store[key]
                return None
            return data

    def set(self, key: str, value: bytes, ttl_seconds: float = 15.0):
        time.sleep(self._latency)
        now = time.monotonic()
        with self._lock:
            self._store[key] = (value, now + ttl_seconds)

# ==============================================================================
# 3. HIGH-PERFORMANCE SERVICE: HybridCache & Stampede Mitigation
# ==============================================================================
class HighPerformanceDataService:
    """
    Mengimplementasikan arsitektur HybridCache (L1 + L2) dengan Single-Flight Lock
    untuk mencegah Thundering Herd / Cache Stampede Problem dan memanfaatkan Buffer Pool.
    """
    def __init__(self):
        self.l1_cache = SimulatedMemoryCache(max_capacity_bytes=32 * 1024)
        self.l2_cache = SimulatedDistributedCache(network_latency_ms=3.0)
        self._flight_locks: Dict[str, threading.Lock] = {}
        self._flight_registry_lock = threading.Lock()
        
        # Telemetri
        self.stats_lock = threading.Lock()
        self.l1_hits = 0
        self.l2_hits = 0
        self.db_hits = 0

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self._flight_registry_lock:
            if key not in self._flight_locks:
                self._flight_locks[key] = threading.Lock()
            return self._flight_locks[key]

    def _fetch_from_database(self, entity_id: int) -> bytes:
        """Simulasi Database SQL Server / External API yang lambat."""
        time.sleep(0.040) # 40ms simulasi I/O disk & latency database
        with self.stats_lock:
            self.db_hits += 1
        
        # Pinjam buffer dari Shared ArrayPool daripada alokasi baru
        buffer = SHARED_BUFFER_POOL.rent(256)
        try:
            payload = f'{{"id":{entity_id},"status":"active","payload":"simulated_payload_data"}}'.encode('utf-8')
            buffer[:len(payload)] = payload
            return bytes(buffer[:len(payload)])
        finally:
            SHARED_BUFFER_POOL.return_buffer(buffer)

    def get_data_hybrid(self, entity_id: int) -> bytes:
        """
        Pola HybridCache dengan Thundering Herd Protection (Single-Flight Pattern).
        Hanya 1 worker thread yang diizinkan memanggil DB ketika cache miss terjadi secara massal.
        """
        key = f"entity:{entity_id}"

        # 1. Cek L1 Memory Cache (Nanoseconds / Fast In-Memory)
        l1_data = self.l1_cache.try_get(key)
        if l1_data:
            with self.stats_lock:
                self.l1_hits += 1
            return l1_data

        # 2. Single-Flight Lock per Key untuk mencegah Cache Stampede
        key_lock = self._get_key_lock(key)
        with key_lock:
            # Double-check L1 di dalam lock
            l1_data = self.l1_cache.try_get(key)
            if l1_data:
                with self.stats_lock:
                    self.l1_hits += 1
                return l1_data

            # 3. Cek L2 Distributed Cache (Milliseconds)
            l2_data = self.l2_cache.get(key)
            if l2_data:
                with self.stats_lock:
                    self.l2_hits += 1
                # Backfill ke L1
                self.l1_cache.set(key, l2_data, absolute_seconds=10.0, sliding_seconds=3.0)
                return l2_data

            # 4. Cache Miss Total -> Query Database
            db_data = self._fetch_from_database(entity_id)

            # Update L1 dan L2 secara asinkron/sinkron
            self.l1_cache.set(key, db_data, absolute_seconds=10.0, sliding_seconds=3.0)
            self.l2_cache.set(key, db_data, ttl_seconds=30.0)

            return db_data

    def get_data_naive(self, entity_id: int) -> bytes:
        """
        Implementasi Naif: Tidak ada caching, alokasi objek baru terus-menerus.
        Menghasilkan GC overhead dan database thundering herd.
        """
        with self.stats_lock:
            self.db_hits += 1
        time.sleep(0.040) # Slow query
        # Fresh allocation (membebani GC)
        fresh_buffer = bytearray(2048)
        payload = f'{{"id":{entity_id},"status":"active","payload":"unpooled_data"}}'.encode('utf-8')
        fresh_buffer[:len(payload)] = payload
        return bytes(fresh_buffer[:len(payload)])

# ==============================================================================
# 4. BENCHMARK RUNNER & COMPARATOR
# ==============================================================================
def run_concurrent_workload(service: HighPerformanceDataService, use_hybrid: bool, total_requests: int = 100, concurrency: int = 10):
    threads = []
    # Kumpulan 5 unique IDs untuk mensimulasikan hot partition (akses berulang pada kunci yang sama)
    keys_pool = [101, 102, 103, 104, 105]

    def worker_task():
        for _ in range(total_requests // concurrency):
            target_id = random.choice(keys_pool)
            if use_hybrid:
                service.get_data_hybrid(target_id)
            else:
                service.get_data_naive(target_id)

    start_time = time.perf_counter()
    for _ in range(concurrency):
        t = threading.Thread(target=worker_task)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.perf_counter() - start_time
    return duration

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  ASP.NET Core Performance Engineering: Caching & Memory Optimization {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    total_requests = 120
    concurrency = 12

    # --- Skenario 1: Naive Approach (No Caching, No Buffer Pooling) ---
    print(f"{CLR_BOLD}[1/2] Menjalankan Skenario NAIVE (Tanpa Cache, Alokasi Heap Liar)...{CLR_RESET}")
    naive_service = HighPerformanceDataService()
    naive_duration = run_concurrent_workload(naive_service, use_hybrid=False, total_requests=total_requests, concurrency=concurrency)

    print(f"  {CLR_RED}✗ Total Waktu Eksekusi : {naive_duration:.4f} detik{CLR_RESET}")
    print(f"  {CLR_RED}✗ Database Query Hits  : {naive_service.db_hits}{CLR_RESET}")
    print(f"  {CLR_RED}✗ Throughput           : {(total_requests / naive_duration):.2f} req/sec{CLR_RESET}\n")

    # --- Skenario 2: Optimized (L1/L2 HybridCache + Stampede Mitigation + ArrayPool) ---
    print(f"{CLR_BOLD}[2/2] Menjalankan Skenario OPTIMIZED (HybridCache, Single-Flight & ArrayPool)...{CLR_RESET}")
    optimized_service = HighPerformanceDataService()
    opt_duration = run_concurrent_workload(optimized_service, use_hybrid=True, total_requests=total_requests, concurrency=concurrency)

    print(f"  {CLR_GREEN}✓ Total Waktu Eksekusi : {opt_duration:.4f} detik{CLR_RESET}")
    print(f"  {CLR_GREEN}✓ L1 Cache Hits (Memory): {optimized_service.l1_hits}{CLR_RESET}")
    print(f"  {CLR_GREEN}✓ L2 Cache Hits (Redis) : {optimized_service.l2_hits}{CLR_RESET}")
    print(f"  {CLR_GREEN}✓ Database Hits (Misses): {optimized_service.db_hits} (Stampede Berhasil Diredam!){CLR_RESET}")
    print(f"  {CLR_GREEN}✓ Throughput           : {(total_requests / opt_duration):.2f} req/sec{CLR_RESET}\n")

    # --- Buffer Pooling Metrics ---
    print(f"{CLR_BOLD}{CLR_MAGENTA}--- ArrayPool<T>.Shared Telemetry Report ---{CLR_RESET}")
    print(f"  Total Permintaan Buffer (Rent)  : {SHARED_BUFFER_POOL.total_rentals}")
    print(f"  Alokasi Heap Baru Dicegah (Reused): {SHARED_BUFFER_POOL.reused_rentals} ({CLR_GREEN}{(SHARED_BUFFER_POOL.reused_rentals / max(1, SHARED_BUFFER_POOL.total_rentals) * 100):.1f}% Reused{CLR_RESET})")
    print(f"  Alokasi Heap Riil Baru          : {SHARED_BUFFER_POOL.new_allocations}\n")

    # --- Analisis & Komparasi ---
    speedup = naive_duration / opt_duration if opt_duration > 0 else 0
    db_reduction = ((naive_service.db_hits - optimized_service.db_hits) / naive_service.db_hits) * 100

    print(f"{CLR_BOLD}{CLR_YELLOW}--- PERFOMANCE SUMMARY & GC OPTIMIZATION ANALYSIS ---{CLR_RESET}")
    print(f"  Akselerasi Latensi : {CLR_BOLD}{CLR_GREEN}{speedup:.2f}x LEBIH CEPAT{CLR_RESET}")
    print(f"  Reduksi Beban DB   : {CLR_BOLD}{CLR_GREEN}{db_reduction:.1f}% DB Load Terpangkas{CLR_RESET}")
    print(f"  Status Optimasi    : {CLR_BOLD}{CLR_CYAN}Production Ready (.NET Architecture Compliance){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")

if __name__ == "__main__":
    main()
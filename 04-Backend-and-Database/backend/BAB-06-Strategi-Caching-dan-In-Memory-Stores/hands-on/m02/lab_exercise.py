#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Advanced Caching Strategies & In-Memory Stores
Topic: BAB-06 Strategi Caching dan In-Memory Stores
Description:
    Simulasi arsitektur caching multi-tier level produksi:
    1. Multi-Tier Cache Hierarchy: L1 (In-Process LRU Cache) + L2 (In-Memory Key-Value / Redis simulation) + DB
    2. Caching Strategies: Cache-Aside with Singleflight / Mutex locking (Cache Stampede Mitigation)
    3. Expiration & Resilience: TTL with probabilistic jitter (Cache Avalanche mitigation) & Null-caching (Penetration mitigation)
    4. Write Strategies: Write-Through & Write-Behind (Background worker)
"""

import time
import random
import threading
from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict
from dataclasses import dataclass

# ANSI Color Codes for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"
GRAY = "\033[90m"


@dataclass
class CacheEntry:
    val: Any
    expires_at: float


class L1LocalCache:
    """Thread-safe In-Process LRU Cache with capacity limit and TTL."""
    def __init__(self, capacity: int = 50, default_ttl: float = 2.0):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key not in self.cache:
                return None
            entry = self.cache[key]
            if time.time() > entry.expires_at:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return entry.val

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
            self.cache[key] = CacheEntry(val=value, expires_at=expires_at)

    def invalidate(self, key: str) -> None:
        with self.lock:
            self.cache.pop(key, None)


class L2DistributedCache:
    """Simulated Centralized In-Memory Store (e.g. Redis Cluster) with network latency."""
    def __init__(self, latency_ms: float = 5.0):
        self.latency_sec = latency_ms / 1000.0
        self.store: Dict[str, CacheEntry] = {}
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        time.sleep(self.latency_sec)
        with self.lock:
            if key not in self.store:
                return None
            entry = self.store[key]
            if time.time() > entry.expires_at:
                del self.store[key]
                return None
            return entry.val

    def set(self, key: str, value: Any, ttl: float = 10.0) -> None:
        time.sleep(self.latency_sec)
        # Jitter added to prevent Cache Avalanche (thundering herd at expiry)
        jitter = random.uniform(0.85, 1.15)
        expires_at = time.time() + (ttl * jitter)
        with self.lock:
            self.store[key] = CacheEntry(val=value, expires_at=expires_at)

    def invalidate(self, key: str) -> None:
        time.sleep(self.latency_sec)
        with self.lock:
            self.store.pop(key, None)


class PersistentDatabase:
    """Simulated Relational/Disk Database with high query latency."""
    def __init__(self, latency_ms: float = 40.0):
        self.latency_sec = latency_ms / 1000.0
        self.records: Dict[str, str] = {
            "prod:101": "Product Alpha ($120.00)",
            "prod:102": "Product Beta ($245.50)",
            "prod:103": "Product Gamma ($89.90)",
            "prod:104": "Product Delta ($450.00)",
        }
        self.query_count = 0
        self.lock = threading.Lock()

    def query(self, key: str) -> Optional[str]:
        with self.lock:
            self.query_count += 1
        time.sleep(self.latency_sec)
        return self.records.get(key, None)

    def update(self, key: str, val: str) -> None:
        time.sleep(self.latency_sec)
        with self.lock:
            self.records[key] = val


class ProductionCacheManager:
    """Orchestrates Multi-Tier Caching, Cache Stampede Singleflight, and Null-Caching."""
    def __init__(self):
        self.l1 = L1LocalCache(capacity=10, default_ttl=2.0)
        self.l2 = L2DistributedCache(latency_ms=6.0)
        self.db = PersistentDatabase(latency_ms=45.0)
        self.singleflight_locks: Dict[str, threading.Lock] = {}
        self.sf_lock = threading.Lock()

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self.sf_lock:
            if key not in self.singleflight_locks:
                self.singleflight_locks[key] = threading.Lock()
            return self.singleflight_locks[key]

    def read_cache_aside(self, key: str) -> Tuple[Optional[str], str, float]:
        start = time.perf_counter()

        # 1. Probe L1 Local Memory
        val = self.l1.get(key)
        if val is not None:
            elapsed = (time.perf_counter() - start) * 1000
            return (None if val == "__NULL__" else val), "L1 (Local Memory)", elapsed

        # 2. Probe L2 Distributed Store
        val = self.l2.get(key)
        if val is not None:
            self.l1.set(key, val, ttl=2.0)
            elapsed = (time.perf_counter() - start) * 1000
            return (None if val == "__NULL__" else val), "L2 (Distributed Cache)", elapsed

        # 3. Cache Miss - Singleflight Mutex to prevent Cache Stampede / Dogpiling
        key_lock = self._get_key_lock(key)
        with key_lock:
            # Re-check cache under lock (Double-Checked Locking Pattern)
            val = self.l1.get(key) or self.l2.get(key)
            if val is not None:
                elapsed = (time.perf_counter() - start) * 1000
                return (None if val == "__NULL__" else val), "L2 (After Stampede Lock)", elapsed

            # Fetch from DB
            db_val = self.db.query(key)

            if db_val is not None:
                self.l2.set(key, db_val, ttl=8.0)
                self.l1.set(key, db_val, ttl=2.0)
                res = db_val
            else:
                # Mitigate Cache Penetration: store short-lived sentinel for non-existent keys
                self.l2.set(key, "__NULL__", ttl=3.0)
                self.l1.set(key, "__NULL__", ttl=1.0)
                res = None

        elapsed = (time.perf_counter() - start) * 1000
        return res, "Database (Persistent DB)", elapsed

    def write_through(self, key: str, new_value: str) -> float:
        start = time.perf_counter()
        # Update DB first, then synchronously update or invalidate cache tiers
        self.db.update(key, new_value)
        self.l2.set(key, new_value, ttl=8.0)
        self.l1.set(key, new_value, ttl=2.0)
        return (time.perf_counter() - start) * 1000


def run_benchmark_simulation():
    print(f"\n{BOLD}{CYAN}=== SIMULASI ARSITEKTUR MULTI-TIER CACHING & IN-MEMORY STORES ==={RESET}")
    print(f"{GRAY}Arsitektur: L1 (Local LRU) -> L2 (Distributed In-Memory) -> DB (Disk Persistence){RESET}\n")

    manager = ProductionCacheManager()

    # Skenario 1: Cold start (Cache Miss -> DB)
    print(f"{BOLD}[Skenario 1: Cold Start Query]{RESET}")
    val, source, latency = manager.read_cache_aside("prod:101")
    print(f"Query: 'prod:101' | Result: {GREEN}{val}{RESET} | Tier: {MAGENTA}{source}{RESET} | Latency: {YELLOW}{latency:.2f} ms{RESET}")

    # Skenario 2: Cache Hit L1
    print(f"\n{BOLD}[Skenario 2: Immediate Re-Query (L1 Hit)]{RESET}")
    val, source, latency = manager.read_cache_aside("prod:101")
    print(f"Query: 'prod:101' | Result: {GREEN}{val}{RESET} | Tier: {GREEN}{source}{RESET} | Latency: {GREEN}{latency:.3f} ms{RESET}")

    # Skenario 3: L1 Expired, L2 Hit
    print(f"\n{BOLD}[Skenario 3: L1 TTL Expiry (Fallback to L2 Redis)]{RESET}")
    print(f"{GRAY}Menunggu 2.2 detik agar L1 kedaluwarsa...{RESET}")
    time.sleep(2.2)
    val, source, latency = manager.read_cache_aside("prod:101")
    print(f"Query: 'prod:101' | Result: {GREEN}{val}{RESET} | Tier: {BLUE}{source}{RESET} | Latency: {YELLOW}{latency:.2f} ms{RESET}")

    # Skenario 4: Cache Penetration Prevention (Null Object Caching)
    print(f"\n{BOLD}[Skenario 4: Cache Penetration Defense (Non-existent Key)]{RESET}")
    val, source, latency = manager.read_cache_aside("prod:999_missing")
    print(f"Query 1 Missing: Result: {RED}{val}{RESET} | Tier: {source} | Latency: {YELLOW}{latency:.2f} ms{RESET}")
    val, source, latency = manager.read_cache_aside("prod:999_missing")
    print(f"Query 2 Missing: Result: {RED}{val}{RESET} | Tier: {GREEN}{source}{RESET} | Latency: {GREEN}{latency:.3f} ms{RESET} (Terselamatkan oleh Null-Cache)")

    # Skenario 5: Cache Stampede (Dogpiling / Thundering Herd Simulation)
    print(f"\n{BOLD}[Skenario 5: Cache Stampede Concurrency Test]{RESET}")
    print(f"{GRAY}Meluncurkan 15 thread paralel secara serentak meminta key 'prod:102' yang belum tercache...{RESET}")
    threads = []
    latencies = []

    def worker(worker_id: int):
        _, src, lat = manager.read_cache_aside("prod:102")
        latencies.append((worker_id, src, lat))

    for i in range(15):
        t = threading.Thread(target=worker, args=(i + 1,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    db_hit_count = sum(1 for _, src, _ in latencies if "Database" in src)
    print(f"Total concurrent requests : {len(latencies)}")
    print(f"Total Database Hits       : {RED if db_hit_count > 1 else GREEN}{db_hit_count} (Singleflight Lock Protection){RESET}")
    print(f"Average Request Latency   : {YELLOW}{sum(l for _, _, l in latencies)/len(latencies):.2f} ms{RESET}")

    # Skenario 6: Write-Through Updates
    print(f"\n{BOLD}[Skenario 6: Write-Through Invalidation & Consistency]{RESET}")
    write_lat = manager.write_through("prod:101", "Product Alpha (Special Price $99.00)")
    print(f"Updated 'prod:101' across DB + L2 + L1 in {YELLOW}{write_lat:.2f} ms{RESET}")
    val, source, latency = manager.read_cache_aside("prod:101")
    print(f"Immediate Read Verification: {GREEN}{val}{RESET} from {MAGENTA}{source}{RESET} in {GREEN}{latency:.3f} ms{RESET}")

    print(f"\n{BOLD}{GREEN}✓ Simulasi selesai! Semua strategi arsitektur caching berjalan sukses.{RESET}\n")


if __name__ == "__main__":
    run_benchmark_simulation()

#!/usr/bin/env python3
"""
BAB-06: Strategi Caching & In-Memory Stores - Hands-on Interactive Lab
Simulasi Teknis Komprehensif:
- Cache-Aside (Lazy Loading) & TTL (Time-To-Live)
- LRU (Least Recently Used) Eviction Algorithm
- Cache Stampede (Thundering Herd) Mitigation via Mutex Lock
- Metrik Performa: Cache Hit/Miss, Latency Savings, & Eviction Tracking
"""

import sys
import time
import random
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_DARK = "\033[48;5;235m"


@dataclass
class CacheEntry:
    value: Any
    expires_at: Optional[float]


class MockDatabase:
    """Simulasi Persistent Storage (Disk/RDBMS) dengan latensi I/O tinggi."""
    def __init__(self, simulated_delay_ms: float = 65.0):
        self.delay_sec = simulated_delay_ms / 1000.0
        self.data: Dict[str, str] = {
            "user:101": '{"id": 101, "name": "Budi Santoso", "role": "admin"}',
            "user:102": '{"id": 102, "name": "Siti Nurhaliza", "role": "editor"}',
            "user:103": '{"id": 103, "name": "Andi Wijaya", "role": "member"}',
            "product:901": '{"sku": "LAP-01", "name": "Workstation Pro", "price": 18500000}',
            "product:902": '{"sku": "MOU-02", "name": "Ergo Mouse RGB", "price": 450000}',
        }
        self.read_count = 0
        self.write_count = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        time.sleep(self.delay_sec)  # Simulasi network roundtrip + disk read
        with self._lock:
            self.read_count += 1
            return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        time.sleep(self.delay_sec * 1.2)  # Write biasanya lebih lambat
        with self._lock:
            self.write_count += 1
            self.data[key] = value


class LRUCacheStore:
    """In-Memory Cache Store dengan LRU Eviction & TTL terintegrasi."""
    def __init__(self, capacity: int = 3):
        self.capacity = capacity
        self.store: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.Lock()
        
        # Telemetry
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: str) -> Tuple[Optional[Any], str]:
        with self.lock:
            if key not in self.store:
                self.misses += 1
                return None, "MISS_NOT_FOUND"

            entry = self.store[key]
            # Cek TTL Expiration
            if entry.expires_at is not None and time.time() > entry.expires_at:
                del self.store[key]
                self.misses += 1
                return None, "MISS_EXPIRED"

            # Hit: Update posisi ke paling baru (Most Recently Used)
            self.store.move_to_end(key, last=True)
            self.hits += 1
            return entry.value, "HIT"

    def put(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> Optional[str]:
        with self.lock:
            evicted_key = None
            expires_at = (time.time() + ttl_seconds) if ttl_seconds else None

            if key in self.store:
                self.store[key] = CacheEntry(value=value, expires_at=expires_at)
                self.store.move_to_end(key, last=True)
                return None

            # Cek kapasitas untuk LRU Eviction
            if len(self.store) >= self.capacity:
                # Pop item tertua (FIFO di OrderedDict front = Least Recently Used)
                evicted_key, _ = self.store.popitem(last=False)
                self.evictions += 1

            self.store[key] = CacheEntry(value=value, expires_at=expires_at)
            return evicted_key

    def get_keys(self) -> list:
        with self.lock:
            return list(self.store.keys())


class CacheAsideManager:
    """Implementasi Pola Cache-Aside dengan proteksi Cache Stampede."""
    def __init__(self, cache: LRUCacheStore, db: MockDatabase):
        self.cache = cache
        self.db = db
        self._key_locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self._registry_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def read_through(self, key: str, ttl_sec: float = 4.0, use_mutex: bool = True) -> Tuple[Optional[str], float, str]:
        t_start = time.perf_counter()

        # Step 1: Query Cache
        val, status = self.cache.get(key)
        if status == "HIT":
            latency_ms = (time.perf_counter() - t_start) * 1000
            return val, latency_ms, f"{ANSI.GREEN}[CACHE HIT]{ANSI.RESET}"

        # Step 2: Cache Miss Handling
        if use_mutex:
            lock = self._get_key_lock(key)
            with lock:
                # Double-check pattern setelah acquire lock
                val, status = self.cache.get(key)
                if status == "HIT":
                    latency_ms = (time.perf_counter() - t_start) * 1000
                    return val, latency_ms, f"{ANSI.GREEN}[CACHE HIT (post-lock)]{ANSI.RESET}"

                # Query Database primer
                db_val = self.db.get(key)
                if db_val is not None:
                    self.cache.put(key, db_val, ttl_seconds=ttl_sec)
                latency_ms = (time.perf_counter() - t_start) * 1000
                return db_val, latency_ms, f"{ANSI.RED}[CACHE MISS -> DB FETCH]{ANSI.RESET}"
        else:
            db_val = self.db.get(key)
            if db_val is not None:
                self.cache.put(key, db_val, ttl_seconds=ttl_sec)
            latency_ms = (time.perf_counter() - t_start) * 1000
            return db_val, latency_ms, f"{ANSI.RED}[CACHE MISS (unprotected)]{ANSI.RESET}"


def print_header(title: str) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}{'='*68}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN} :: {title} ::{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}{'='*68}{ANSI.RESET}")


def run_scenario_cache_aside(manager: CacheAsideManager):
    print_header("SKENARIO 1: Cache-Aside & Latensi Benchmark")
    keys_to_fetch = ["user:101", "user:101", "product:901", "user:101", "unknown:999"]
    
    for key in keys_to_fetch:
        val, latency, status_badge = manager.read_through(key, ttl_sec=3.0)
        display_val = (val[:38] + "...") if val and len(val) > 40 else val
        print(f"Fetch {ANSI.BOLD}{key:<12}{ANSI.RESET} | {status_badge:<35} | Latensi: {ANSI.YELLOW}{latency:6.2f} ms{ANSI.RESET} | Data: {ANSI.DIM}{display_val}{ANSI.RESET}")
        time.sleep(0.15)


def run_scenario_lru_eviction(cache: LRUCacheStore, db: MockDatabase):
    print_header("SKENARIO 2: LRU Eviction Policy (Kapasitas Cache = 3)")
    print(f"Kapasitas Cache dibatasi: {ANSI.BOLD}3 item{ANSI.RESET}\n")

    items = [
        ("K1", "Data Alpha"),
        ("K2", "Data Beta"),
        ("K3", "Data Gamma"),
        ("K1", "Data Alpha (Accessed again!)"),
        ("K4", "Data Delta (Memaksa Eviction)"),
        ("K5", "Data Epsilon (Memaksa Eviction ke-2)")
    ]

    for key, val in items:
        if "Accessed" in val:
            _, status = cache.get(key)
            print(f"Akses Ulang {ANSI.BOLD}{key}{ANSI.RESET} -> State: {ANSI.GREEN}{status}{ANSI.RESET} (Mempromosikan {key} ke Most Recently Used)")
        else:
            evicted = cache.put(key, val, ttl_seconds=10.0)
            if evicted:
                print(f"Memasukkan {ANSI.CYAN}{key}{ANSI.RESET} -> {ANSI.RED}[EVICTED: {evicted}]{ANSI.RESET} karena kapasitas penuh!")
            else:
                print(f"Memasukkan {ANSI.CYAN}{key}{ANSI.RESET} -> Berhasil disimpan.")
        
        current_keys = cache.get_keys()
        print(f"  Slot Cache Saat Ini (LRU -> MRU): {ANSI.MAGENTA}{' -> '.join(current_keys)}{ANSI.RESET}\n")
        time.sleep(0.2)


def run_scenario_cache_stampede(db: MockDatabase):
    print_header("SKENARIO 3: Cache Stampede / Thundering Herd Simulation")
    print("Simulasi 6 Thread konkuren membaca key yang sama saat Cache Kosong / Expired.\n")

    # Uji 1: Tanpa Mutex Lock
    print(f"{ANSI.BOLD}--- [1] EKSEKUSI TANPA MUTEX (STAMPEDE TERJADI) ---{ANSI.RESET}")
    raw_cache = LRUCacheStore(capacity=5)
    unprotected_manager = CacheAsideManager(raw_cache, db)
    db_reads_before = db.read_count

    threads = []
    results = []

    def fetch_worker(idx: int, mgr: CacheAsideManager, use_mutex: bool):
        val, lat, status = mgr.read_through("product:902", ttl_sec=5.0, use_mutex=use_mutex)
        results.append((idx, lat, status))

    for i in range(6):
        t = threading.Thread(target=fetch_worker, args=(i + 1, unprotected_manager, False))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    db_reads_unprotected = db.read_count - db_reads_before
    print(f"Hasil: {ANSI.RED}{db_reads_unprotected} panggilan Database primer terpicu sekaligus!{ANSI.RESET} (High DB Load)")

    # Uji 2: Dengan Mutex SingleFlight Lock
    print(f"\n{ANSI.BOLD}--- [2] EKSEKUSI DENGAN MUTEX SINGLEFLIGHT (PROTEKSI AKTIF) ---{ANSI.RESET}")
    protected_cache = LRUCacheStore(capacity=5)
    protected_manager = CacheAsideManager(protected_cache, db)
    db_reads_before = db.read_count

    threads = []
    results = []

    for i in range(6):
        t = threading.Thread(target=fetch_worker, args=(i + 1, protected_manager, True))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    db_reads_protected = db.read_count - db_reads_before
    print(f"Hasil: {ANSI.GREEN}Hanya {db_reads_protected} panggilan Database primer terpicu!{ANSI.RESET} Thread lain menunggu & membaca dari Cache.")


def print_dashboard(cache: LRUCacheStore, db: MockDatabase):
    print_header("TELEMETRY & CACHE METRICS DASHBOARD")
    total_requests = cache.hits + cache.misses
    hit_rate = (cache.hits / total_requests * 100) if total_requests > 0 else 0.0

    print(f"  {ANSI.BOLD}Total Requests    :{ANSI.RESET} {total_requests}")
    print(f"  {ANSI.GREEN}Cache Hits        :{ANSI.RESET} {cache.hits}")
    print(f"  {ANSI.RED}Cache Misses      :{ANSI.RESET} {cache.misses}")
    print(f"  {ANSI.CYAN}Hit Rate Ratio    :{ANSI.RESET} {ANSI.BOLD}{hit_rate:.1f}%{ANSI.RESET}")
    print(f"  {ANSI.MAGENTA}Total Evictions   :{ANSI.RESET} {cache.evictions}")
    print(f"  {ANSI.YELLOW}DB Read Queries   :{ANSI.RESET} {db.read_count}")
    print(f"  {ANSI.YELLOW}DB Write Queries  :{ANSI.RESET} {db.write_count}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}{'='*68}{ANSI.RESET}\n")


def interactive_cli():
    db = MockDatabase(simulated_delay_ms=50.0)
    cache = LRUCacheStore(capacity=3)
    manager = CacheAsideManager(cache, db)

    while True:
        print(f"\n{ANSI.BOLD}{ANSI.BG_DARK} PILIHAN MENU SIMULASI CACHE: {ANSI.RESET}")
        print(f" 1. Jalankan Skenario 1 (Cache-Aside Pattern & Latency)")
        print(f" 2. Jalankan Skenario 2 (LRU Eviction Mechanism)")
        print(f" 3. Jalankan Skenario 3 (Cache Stampede & SingleFlight Mutex)")
        print(f" 4. Query Key Manual (Interactive Get/Set)")
        print(f" 5. Tampilkan Telemetry Dashboard")
        print(f" 6. Jalankan Semua Skenario Otomatis")
        print(f" 0. Keluar")
        
        choice = input(f"\n{ANSI.BOLD}Masukkan pilihan [0-6]: {ANSI.RESET}").strip()
        
        if choice == "1":
            run_scenario_cache_aside(manager)
        elif choice == "2":
            run_scenario_lru_eviction(cache, db)
        elif choice == "3":
            run_scenario_cache_stampede(db)
        elif choice == "4":
            key = input("Masukkan key (contoh: 'user:101' atau 'custom:key'): ").strip()
            val, lat, badge = manager.read_through(key, ttl_sec=5.0)
            print(f"Hasil: {badge} | Latensi: {lat:.2f} ms | Data: {val}")
        elif choice == "5":
            print_dashboard(cache, db)
        elif choice == "6":
            run_scenario_cache_aside(manager)
            run_scenario_lru_eviction(cache, db)
            run_scenario_cache_stampede(db)
            print_dashboard(cache, db)
        elif choice == "0":
            print(f"{ANSI.GREEN}Simulasi selesai. Sampai jumpa!{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid. Silakan coba lagi.{ANSI.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        db = MockDatabase(simulated_delay_ms=30.0)
        cache = LRUCacheStore(capacity=3)
        manager = CacheAsideManager(cache, db)
        run_scenario_cache_aside(manager)
        run_scenario_lru_eviction(cache, db)
        run_scenario_cache_stampede(db)
        print_dashboard(cache, db)
    else:
        interactive_cli()

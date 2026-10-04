#!/usr/bin/env python3
"""
Lab Exercise: ASP.NET Core High-Performance Caching & Memory Optimization Simulation
Fokus Konsep:
1. IMemoryCache (Absolute vs Sliding Expiration, Cache Eviction Priority, Size Limits)
2. IDistributedCache (Distributed Redis-style Caching with Serialization)
3. Cache Stampede Mitigation (SingleFlight / SemaphoreSlim Double-Check Locking)
4. ArrayPool<T> & MemoryPool Buffer Recycling (Zero Allocation Pipeline)
"""

import sys
import time
import threading
from typing import Any, Dict, Optional, Tuple

# ANSI Terminal Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

def print_header(title: str) -> None:
    print(f"\n{BOLD}{BLUE}{'=' * 68}{RESET}")
    print(f"{BOLD}{CYAN} [LAB ASP.NET CORE] {title.upper()}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 68}{RESET}")

def print_step(step_no: int, desc: str) -> None:
    print(f"\n{BOLD}{YELLOW}>>> STEP {step_no}:{RESET} {BOLD}{desc}{RESET}")

class CacheEntry:
    def __init__(self, key: str, value: Any, size: int, absolute_exp: Optional[float], sliding_exp: Optional[float]):
        self.key = key
        self.value = value
        self.size = size
        self.absolute_exp = absolute_exp
        self.sliding_exp = sliding_exp
        self.last_accessed = time.time()
        self.created_at = time.time()

    def is_expired(self, current_time: float) -> bool:
        if self.absolute_exp and current_time >= self.absolute_exp:
            return True
        if self.sliding_exp and (current_time - self.last_accessed) >= self.sliding_exp:
            return True
        return False

class InMemoryCacheSimulator:
    """Simulasi IMemoryCache ASP.NET Core dengan Absolute & Sliding Expiration serta SizeLimit."""
    def __init__(self, size_limit: int = 100):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.size_limit = size_limit
        self.current_size = 0

    def set(self, key: str, value: Any, size: int = 1, absolute_seconds: Optional[float] = None, sliding_seconds: Optional[float] = None):
        with self._lock:
            now = time.time()
            abs_exp = now + absolute_seconds if absolute_seconds else None
            
            # Eviction sederhana jika size limit terlampaui
            if self.current_size + size > self.size_limit:
                print(f"  {YELLOW}[Memory Pressure] Size limit ({self.size_limit}) tercapai. Evicting oldest entry...{RESET}")
                if self._cache:
                    oldest_key = next(iter(self._cache))
                    removed = self._cache.pop(oldest_key)
                    self.current_size -= removed.size
                    print(f"  {RED}[Evicted] Key: {oldest_key} freed {removed.size} units{RESET}")

            entry = CacheEntry(key, value, size, abs_exp, sliding_seconds)
            self._cache[key] = entry
            self.current_size += size
            print(f"  {GREEN}[IMemoryCache SET]{RESET} Key='{key}', Size={size}, AbsExp={absolute_seconds}s, Sliding={sliding_seconds}s")

    def get(self, key: str) -> Tuple[bool, Any]:
        with self._lock:
            now = time.time()
            entry = self._cache.get(key)
            if not entry:
                return False, None
            
            if entry.is_expired(now):
                print(f"  {RED}[IMemoryCache EXPIRED]{RESET} Key='{key}' kedaluwarsa.")
                self.current_size -= entry.size
                del self._cache[key]
                return False, None
            
            entry.last_accessed = now
            print(f"  {CYAN}[IMemoryCache HIT]{RESET} Key='{key}' -> Value={entry.value} (Sliding reset)")
            return True, entry.value

class DistributedCacheSimulator:
    """Simulasi IDistributedCache (misal Redis) dengan Byte Serialization."""
    def __init__(self):
        self._store: Dict[str, bytes] = {}
        self._lock = threading.Lock()

    def set_string(self, key: str, value: str):
        with self._lock:
            payload = value.encode('utf-8')
            self._store[key] = payload
            print(f"  {MAGENTA}[IDistributedCache SET]{RESET} Key='{key}', Payload={len(payload)} bytes")

    def get_string(self, key: str) -> Optional[str]:
        with self._lock:
            payload = self._store.get(key)
            if payload is None:
                print(f"  {YELLOW}[IDistributedCache MISS]{RESET} Key='{key}'")
                return None
            print(f"  {GREEN}[IDistributedCache HIT]{RESET} Key='{key}', Deserialized {len(payload)} bytes")
            return payload.decode('utf-8')

class CacheStampedeMitigator:
    """Simulasi proteksi Thundering Herd / Cache Stampede menggunakan SemaphoreSlim locking pattern."""
    def __init__(self, cache: InMemoryCacheSimulator):
        self.cache = cache
        self.semaphore = threading.Lock()
        self.db_access_count = 0

    def get_or_set(self, key: str, fallback_calc_time: float = 0.5) -> Any:
        found, val = self.cache.get(key)
        if found:
            return val
        
        # Double-check locking pattern ala ASP.NET Core
        with self.semaphore:
            found, val = self.cache.get(key)
            if found:
                print(f"  {GREEN}[Stampede Prevented]{RESET} Thread mendapati cache sudah diisi thread pendahulu.")
                return val
            
            print(f"  {RED}[Database Query Executing]{RESET} Lock didapat, query slow storage/DB...")
            time.sleep(fallback_calc_time)
            self.db_access_count += 1
            calculated_val = f"Heavy_Record_{key}_{self.db_access_count}"
            self.cache.set(key, calculated_val, size=5, absolute_seconds=10)
            return calculated_val

class ArrayPoolSimulator:
    """Simulasi System.Buffers.ArrayPool<T>.Shared untuk Zero Allocation buffer reuse."""
    def __init__(self, max_buffer_size: int = 1024):
        self._pool = []
        self._lock = threading.Lock()
        self.max_buffer_size = max_buffer_size
        self.rented_count = 0
        self.returned_count = 0

    def rent(self, min_size: int) -> bytearray:
        with self._lock:
            self.rented_count += 1
            if self._pool:
                buf = self._pool.pop()
                print(f"  {GREEN}[ArrayPool Rent REUSED]{RESET} Buffer capacity {len(buf)} bytes dipinjam kembali (0 Alloc GC).")
                return buf
            else:
                alloc_size = max(min_size, 256)
                print(f"  {YELLOW}[ArrayPool Rent ALLOC]{RESET} Pool kosong, alokasi memori baru: {alloc_size} bytes.")
                return bytearray(alloc_size)

    def return_to_pool(self, buffer: bytearray, clear_array: bool = True):
        with self._lock:
            self.returned_count += 1
            if clear_array:
                for i in range(len(buffer)):
                    buffer[i] = 0
            self._pool.append(buffer)
            print(f"  {CYAN}[ArrayPool Return]{RESET} Buffer {len(buffer)} bytes dikembalikan ke shared pool (siap didaur ulang).")

def run_simulation():
    print_header("Simulasi Memory & Caching ASP.NET Core")
    
    # 1. IMemoryCache Expiration & SizeLimit
    print_step(1, "Eksperimen IMemoryCache: Absolute & Sliding Expiration")
    mem_cache = InMemoryCacheSimulator(size_limit=10)
    mem_cache.set("User_101", {"name": "Budi"}, size=3, absolute_seconds=2, sliding_seconds=1)
    
    print("  Membaca User_101 segera:")
    mem_cache.get("User_101")
    
    print("  Tidur 1.2 detik (melewati sliding limit jika tidak disentuh, tapi absolut 2 detik):")
    time.sleep(1.2)
    mem_cache.get("User_101")  # Should be expired due to sliding expiration (1.0s limit)

    # 2. Size Limit Pressure & Eviction
    print_step(2, "Eksperimen IMemoryCache: SizeLimit & Cache Compaction")
    mem_cache.set("Item_A", "Payload A", size=4)
    mem_cache.set("Item_B", "Payload B", size=4)
    print(f"  Total ukuran cache sekarang: {mem_cache.current_size}/10")
    print("  Menambahkan Item_C (size=5) -> Memicu pressure eviction:")
    mem_cache.set("Item_C", "Payload C", size=5)

    # 3. IDistributedCache
    print_step(3, "Eksperimen IDistributedCache: Redis Serialization")
    dist_cache = DistributedCacheSimulator()
    dist_cache.set_string("catalog:prod:99", '{"title":"Laptop Core i9","stock":12}')
    prod_data = dist_cache.get_string("catalog:prod:99")
    print(f"  Data terambil: {prod_data}")

    # 4. Cache Stampede Mitigation
    print_step(4, "Mitigasi Cache Stampede (SemaphoreSlim Locking vs Concurrency)")
    shared_cache = InMemoryCacheSimulator(size_limit=50)
    mitigator = CacheStampedeMitigator(shared_cache)

    def worker_request(thread_id: int):
        val = mitigator.get_or_set("heavy_stats_2026", fallback_calc_time=0.4)
        print(f"    Thread-{thread_id} menerima hasil: {val}")

    threads = []
    print("  Meluncurkan 4 thread bersamaan mengakses cache miss yang lambat:")
    for i in range(1, 5):
        t = threading.Thread(target=worker_request, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    print(f"  Total eksekusi database nyata: {BOLD}{mitigator.db_access_count}{RESET} kali (Seharusnya hanya 1x).")

    # 5. ArrayPool<T> Recycling
    print_step(5, "Eksperimen ArrayPool<byte>.Shared (Zero Allocation Optimization)")
    pool = ArrayPoolSimulator()
    
    # Renting buffer pertama
    buf1 = pool.rent(256)
    buf1[0:5] = b"HELLO"
    print(f"  Menulis header ke buffer: {bytes(buf1[0:5])}")
    
    # Return buffer
    pool.return_to_pool(buf1, clear_array=True)
    
    # Renting lagi untuk request berikutnya
    buf2 = pool.rent(256)
    print(f"  Isi byte awal buffer hasil reuse: {buf2[0]} (telah di-clear)")
    pool.return_to_pool(buf2)

    print_header("Simulasi Selesai dengan Sukses!")

if __name__ == "__main__":
    try:
        run_simulation()
    except KeyboardInterrupt:
        print(f"\n{RED}Simulasi dihentikan oleh user.{RESET}")
        sys.exit(0)

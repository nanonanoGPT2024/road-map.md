#!/usr/bin/env python3
"""
Lab Hands-on: Caching Strategies & Background Job Basics
Topic: 01-Core-Foundations / Bab 09 - Modul 02 Deep Dive

Tujuan:
1. Mengimplementasikan Thread-Safe LRU Cache dengan Time-To-Live (TTL).
2. Mengimplementasikan Cache-Aside Pattern (Lazy Loading) untuk optimasi read.
3. Mengimplementasikan Background Job Worker berbasis producer-consumer queue
   untuk tugas asinkron (misal: pengiriman notifikasi & audit trail).
"""

import time
import threading
import queue
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict
from enum import Enum
import uuid

# --- ANSI Color Utilities untuk Output Terminal ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

# ============================================================================
# 1. CACHING LAYER: Thread-Safe LRU Cache with TTL
# ============================================================================

@dataclass
class CacheEntry:
    value: Any
    expires_at: Optional[float]

class LRUCacheTTL:
    """
    LRU (Least Recently Used) Cache dengan TTL (Time-To-Live) dan Thread-Safety.
    Menghapus item tertua saat kapasitas penuh, atau item yang telah kedaluwarsa.
    """
    def __init__(self, capacity: int = 5, default_ttl_seconds: float = 3.0):
        self.capacity = capacity
        self.default_ttl = default_ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        
        # Telemetry / Metrics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

    def get(self, key: str) -> Optional[Any]:
        """Ambil data dari cache jika ada dan belum kedaluwarsa."""
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            entry = self._cache[key]
            
            # Cek TTL Expiration
            if entry.expires_at and time.time() > entry.expires_at:
                del self._cache[key]
                self.expirations += 1
                self.misses += 1
                return None

            # Mark as recently used
            self._cache.move_to_end(key)
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Simpan data ke cache dengan auto-eviction jika melebihi kapasitas."""
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            expires_at = time.time() + ttl if ttl > 0 else None

            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self.capacity:
                # Evict oldest entry (FIFO order of access)
                evicted_key, _ = self._cache.popitem(last=False)
                self.evictions += 1
                print(f"  {Colors.YELLOW}[LRU EVICT]{Colors.RESET} Menghapus key tertua: '{evicted_key}'")

            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "size": len(self._cache),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "expirations": self.expirations,
            }

# ============================================================================
# 2. BACKGROUND JOBS LAYER: Asynchronous Queue & Worker
# ============================================================================

class JobStatus(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class Job:
    name: str
    task_fn: Callable[..., Any]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    created_at: float = field(default_factory=time.time)

class BackgroundJobRunner:
    """
    Background worker pool sederhana menggunakan threading dan thread-safe queue.
    Mensimulasikan broker seperti Celery/Redis Queue untuk proses offloading backend.
    """
    def __init__(self, num_workers: int = 2):
        self.num_workers = num_workers
        self.job_queue: queue.Queue[Optional[Job]] = queue.Queue()
        self.workers = []
        self.completed_jobs: Dict[str, Job] = {}
        self._is_running = True

        for i in range(num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"Worker-{i+1}", daemon=True)
            self.workers.append(t)
            t.start()

    def _worker_loop(self):
        worker_name = threading.current_thread().name
        while self._is_running:
            try:
                job = self.job_queue.get(timeout=0.5)
                if job is None:
                    # Sentinel value untuk graceful shutdown
                    break
            except queue.Empty:
                continue

            job.status = JobStatus.PROCESSING
            print(f"  {Colors.BLUE}[BG WORKER]{Colors.RESET} [{worker_name}] Memproses: '{job.name}' (ID: {job.job_id})")
            
            try:
                job.result = job.task_fn(*job.args, **job.kwargs)
                job.status = JobStatus.COMPLETED
                print(f"  {Colors.GREEN}[BG SUCCESS]{Colors.RESET} [{worker_name}] Selesai: '{job.name}' (ID: {job.job_id}) -> {job.result}")
            except Exception as e:
                job.status = JobStatus.FAILED
                job.result = str(e)
                print(f"  {Colors.RED}[BG ERROR]{Colors.RESET} [{worker_name}] Gagal: '{job.name}': {e}")
            finally:
                self.completed_jobs[job.job_id] = job
                self.job_queue.task_done()

    def enqueue(self, name: str, fn: Callable, *args, **kwargs) -> Job:
        job = Job(name=name, task_fn=fn, args=args, kwargs=kwargs)
        self.job_queue.put(job)
        return job

    def shutdown(self):
        """Tunggu semua task selesai dan shutdown worker threads."""
        self.job_queue.join()  # Tunggu queue habis
        self._is_running = False
        for _ in range(self.num_workers):
            self.job_queue.put(None)
        for w in self.workers:
            w.join()

# ============================================================================
# 3. DOMAIN SIMULATION & CACHE-ASIDE PATTERN
# ============================================================================

# Mock Slow Database
MOCK_DATABASE = {
    "user:101": {"id": 101, "name": "Alice Developer", "tier": "Enterprise"},
    "user:102": {"id": 102, "name": "Bob Architect", "tier": "Pro"},
    "user:103": {"id": 103, "name": "Charlie Ops", "tier": "Free"},
    "user:104": {"id": 104, "name": "David Security", "tier": "Enterprise"},
    "user:105": {"id": 105, "name": "Eva QA", "tier": "Pro"},
}

def simulate_heavy_database_query(key: str) -> Optional[dict]:
    """Simulasi query latency disk/network I/O ke relational DB (300ms)."""
    time.sleep(0.3)
    return MOCK_DATABASE.get(key)

# Mock Background Tasks
def task_send_welcome_email(user_email: str) -> str:
    time.sleep(0.2)
    return f"Email sent to {user_email}"

def task_sync_audit_log(action: str, entity_id: str) -> str:
    time.sleep(0.15)
    return f"Audit log written for {action} on {entity_id}"

class UserService:
    def __init__(self, cache: LRUCacheTTL, job_runner: BackgroundJobRunner):
        self.cache = cache
        self.job_runner = job_runner

    def get_user_profile(self, user_key: str) -> Optional[dict]:
        """
        Implementasi Cache-Aside Pattern:
        1. Cek Cache.
        2. Jika HIT, return data seketika.
        3. Jika MISS, fetch dari Database (lambat), tulis ke Cache, lalu return.
        """
        cached_data = self.cache.get(user_key)
        if cached_data is not None:
            print(f"  {Colors.GREEN}[CACHE HIT]{Colors.RESET} '{user_key}' didapatkan langsung dari Memory!")
            return cached_data

        print(f"  {Colors.RED}[CACHE MISS]{Colors.RESET} '{user_key}' tidak ada di cache. Query Database...")
        db_record = simulate_heavy_database_query(user_key)
        
        if db_record:
            # Simpan hasil query ke cache untuk read berikutnya
            self.cache.set(user_key, db_record)
            
            # Offload proses non-blocking (Audit log) ke background job queue
            self.job_runner.enqueue("SyncAuditLog", task_sync_audit_log, "READ_USER", user_key)
            
        return db_record

# ============================================================================
# 4. MAIN TEST HARNESS & LAB EXECUTION
# ============================================================================

def main():
    print(f"{Colors.BOLD}{Colors.HEADER}=== LAB: CACHING STRATEGIES & BACKGROUND JOBS ==={Colors.RESET}\n")

    # Inisialisasi: Cache berkapasitas 3 item, TTL pendek 1.5 detik
    cache = LRUCacheTTL(capacity=3, default_ttl_seconds=1.5)
    job_runner = BackgroundJobRunner(num_workers=2)
    service = UserService(cache, job_runner)

    try:
        # TEST 1: Cache Miss vs Cache Hit
        print(f"{Colors.CYAN}[SKENARIO 1] Pengujian Cache-Aside (Cold vs Warm Read){Colors.RESET}")
        start_time = time.time()
        service.get_user_profile("user:101")
        miss_elapsed = time.time() - start_time
        print(f"  Latensi Cold Read (Cache Miss): {miss_elapsed:.4f} detik")

        start_time = time.time()
        service.get_user_profile("user:101")
        hit_elapsed = time.time() - start_time
        print(f"  Latensi Warm Read (Cache Hit) : {hit_elapsed:.4f} detik")
        speedup = miss_elapsed / max(hit_elapsed, 0.00001)
        print(f"  {Colors.BOLD}Percepatan: {speedup:.1f}x lebih cepat{Colors.RESET}\n")

        # TEST 2: Kapasitas Cache & LRU Eviction Policy
        print(f"{Colors.CYAN}[SKENARIO 2] Pengujian LRU Eviction Policy (Kapasitas = 3){Colors.RESET}")
        print("  Memasukkan user:102, user:103...")
        service.get_user_profile("user:102")
        service.get_user_profile("user:103")
        # Cache saat ini: [user:101, user:102, user:103] (penuh)

        print("  Mengakses user:101 kembali agar menjadi Most-Recently-Used...")
        service.get_user_profile("user:101")
        # Urutan penggunaan: user:102 (tertua), user:103, user:101 (terbaru)

        print("  Memasukkan user:104 (Seharusnya user:102 di-evict)...")
        service.get_user_profile("user:104")

        print("  Verifikasi: Mengakses user:102 (Seharusnya Miss karena telah dievict):")
        service.get_user_profile("user:102")
        print()

        # TEST 3: TTL (Time-To-Live) Expiration
        print(f"{Colors.CYAN}[SKENARIO 3] Pengujian TTL Expiration (TTL = 1.5 detik){Colors.RESET}")
        print("  Menulis key 'temp:session' dengan TTL 1.0 detik...")
        cache.set("temp:session", {"session_token": "xyz-123"}, ttl_seconds=1.0)
        
        val = cache.get("temp:session")
        print(f"  Akses instan: {val}")

        print("  Tidur 1.2 detik menunggu waktu TTL habis...")
        time.sleep(1.2)

        val_expired = cache.get("temp:session")
        print(f"  Akses setelah TTL habis: {val_expired} (None = Berhasil terhapus)")
        print()

        # TEST 4: Dispatch Background Tasks Non-Blocking
        print(f"{Colors.CYAN}[SKENARIO 4] Pengujian Background Worker Queue{Colors.RESET}")
        print("  Mengantrekan tugas pengiriman batch email async...")
        for i in range(3):
            email = f"user_{i}@example.com"
            job_runner.enqueue("SendWelcomeEmail", task_send_welcome_email, email)

        print("  Main thread TIDAK terblokir, langsung melanjutkan eksekusi!")
        print("  Menunggu Background Job Runner menyelesaikan queue...")

    finally:
        # Graceful shutdown worker pool
        job_runner.shutdown()

    # LAPORAN AKHIR
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== LAPORAN METRIK AKHIR ==={Colors.RESET}")
    stats = cache.stats()
    print(f"  Cache Hits        : {Colors.GREEN}{stats['hits']}{Colors.RESET}")
    print(f"  Cache Misses      : {Colors.RED}{stats['misses']}{Colors.RESET}")
    print(f"  Total Evictions   : {Colors.YELLOW}{stats['evictions']}{Colors.RESET}")
    print(f"  Total Expirations : {Colors.YELLOW}{stats['expirations']}{Colors.RESET}")
    print(f"  Hit Ratio         : {(stats['hits'] / max(stats['hits'] + stats['misses'], 1)) * 100:.1f}%")
    print(f"  Jobs Processed    : {len(job_runner.completed_jobs)}")
    print(f"{Colors.BOLD}{Colors.GREEN}Lab Berhasil Dieksekusi Secara Utuh.{Colors.RESET}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lab Exercise: BAB-07-Materi-Lanjutan (Backend Beginner)
Tema: Simulasi Komponen Fondasi Backend Lanjutan
- In-Memory Cache dengan LRU Eviction & TTL
- Token Bucket Rate Limiter
- Asynchronous Task Queue & Worker Simulation

Dapat dijalankan secara mandiri dengan Python standard library.
"""

import sys
import time
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

# ANSI Terminal Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"


class ANSIHelper:
    @staticmethod
    def header(text: str) -> None:
        print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
        print(f"{BOLD}{CYAN}{text.center(60)}{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")

    @staticmethod
    def success(msg: str) -> None:
        print(f" {GREEN}[✓ SUCCESS]{RESET} {msg}")

    @staticmethod
    def info(msg: str) -> None:
        print(f" {BLUE}[i INFO]{RESET} {msg}")

    @staticmethod
    def warning(msg: str) -> None:
        print(f" {YELLOW}[! WARN]{RESET} {msg}")

    @staticmethod
    def alert(msg: str) -> None:
        print(f" {RED}[✗ BLOCKED]{RESET} {msg}")


# -------------------------------------------------------------
# 1. In-Memory Cache with LRU & TTL (Simulasi Caching Backend)
# -------------------------------------------------------------
@dataclass
class CacheEntry:
    value: Any
    expiry: Optional[float]


class SimpleCache:
    def __init__(self, capacity: int = 3, default_ttl_sec: float = 3.0):
        self.capacity = capacity
        self.default_ttl = default_ttl_sec
        self.store: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Tuple[Optional[Any], str]:
        now = time.time()
        if key not in self.store:
            self.misses += 1
            return None, "CACHE_MISS"

        entry = self.store[key]
        if entry.expiry and now > entry.expiry:
            del self.store[key]
            self.misses += 1
            return None, "CACHE_EXPIRED"

        # Mark as recently used
        self.store.move_to_end(key)
        self.hits += 1
        return entry.value, "CACHE_HIT"

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> Optional[str]:
        evicted = None
        now = time.time()
        expiry = now + (ttl if ttl is not None else self.default_ttl)

        if key in self.store:
            self.store.move_to_end(key)
        elif len(self.store) >= self.capacity:
            # Evict oldest entry (LRU)
            evicted, _ = self.store.popitem(last=False)

        self.store[key] = CacheEntry(value=value, expiry=expiry)
        return evicted


# -------------------------------------------------------------
# 2. Token Bucket Rate Limiter (Simulasi Throttling API)
# -------------------------------------------------------------
class TokenBucketRateLimiter:
    def __init__(self, capacity: int = 5, refill_rate_per_sec: float = 2.0):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(float(self.capacity), self.tokens + new_tokens)
        self.last_refill = now

    def allow_request(self, tokens_needed: int = 1) -> Tuple[bool, float]:
        with self._lock:
            self._refill()
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True, self.tokens
            return False, self.tokens


# -------------------------------------------------------------
# 3. Asynchronous Worker Queue (Simulasi Background Jobs)
# -------------------------------------------------------------
@dataclass
class Job:
    id: int
    name: str
    payload: Dict[str, Any]
    status: str = "PENDING"


class JobQueue:
    def __init__(self):
        self.queue: list[Job] = []
        self._counter = 1

    def enqueue(self, name: str, payload: Dict[str, Any]) -> Job:
        job = Job(id=self._counter, name=name, payload=payload)
        self._counter += 1
        self.queue.append(job)
        return job

    def process_next(self) -> Optional[Job]:
        if not self.queue:
            return None
        job = self.queue.pop(0)
        job.status = "PROCESSING"
        return job


# -------------------------------------------------------------
# Interactive Interactive Scenarios & Demonstrations
# -------------------------------------------------------------
def demo_cache_lifecycle():
    ANSIHelper.header("SIMULASI 1: IN-MEMORY CACHE DENGAN LRU & TTL")
    cache = SimpleCache(capacity=3, default_ttl_sec=2.0)

    print(f"{YELLOW}Kapasitas Cache = 3, Default TTL = 2.0 detik{RESET}\n")

    # Set data
    for user_id in [101, 102, 103]:
        evicted = cache.set(f"user:{user_id}", {"id": user_id, "name": f"User_{user_id}"})
        ANSIHelper.info(f"SET user:{user_id} (Evicted: {evicted})")

    # Hit test
    val, status = cache.get("user:101")
    ANSIHelper.success(f"GET user:101 -> Status: {status} | Data: {val}")

    # LRU Eviction Test (tambah item ke-4)
    ANSIHelper.info("Menambahkan item ke-4 ('user:104') untuk memicu LRU eviction...")
    evicted = cache.set("user:104", {"id": 104, "name": "User_104"})
    ANSIHelper.warning(f"Item ter-evict akibat batas kapasitas: {evicted}")

    # Cek user:102 (harus ter-evict karena 101 baru saja diakses)
    val, status = cache.get("user:102")
    if status != "CACHE_HIT":
        ANSIHelper.alert(f"GET user:102 -> Status: {status} (Telah terdepak oleh LRU)")

    # TTL Expiration Test
    ANSIHelper.info("Menunggu 2.2 detik untuk menguji Time-To-Live (TTL)...")
    time.sleep(2.2)
    val, status = cache.get("user:101")
    ANSIHelper.alert(f"GET user:101 setelah 2.2s -> Status: {status}")
    print(f"\n{BOLD}Statistik Cache:{RESET} Hits: {GREEN}{cache.hits}{RESET} | Misses: {RED}{cache.misses}{RESET}")


def demo_rate_limiter():
    ANSIHelper.header("SIMULASI 2: TOKEN BUCKET RATE LIMITER")
    limiter = TokenBucketRateLimiter(capacity=4, refill_rate_per_sec=2.0)
    print(f"{YELLOW}Bucket Capacity = 4 tokens, Refill Rate = 2 tokens/detik{RESET}\n")

    requests = [
        "GET /api/v1/profile",
        "GET /api/v1/orders",
        "POST /api/v1/checkout",
        "GET /api/v1/notifications",
        "GET /api/v1/feed",
        "GET /api/v1/search",
    ]

    for req in requests:
        allowed, remaining = limiter.allow_request()
        if allowed:
            ANSIHelper.success(f"{req:<28} -> 200 OK (Sisa Token: {remaining:.2f})")
        else:
            ANSIHelper.alert(f"{req:<28} -> 429 Too Many Requests (Token: {remaining:.2f})")
        time.sleep(0.15)

    ANSIHelper.info("Istirahat 1 detik untuk pengisian ulang token...")
    time.sleep(1.0)
    allowed, remaining = limiter.allow_request()
    if allowed:
        ANSIHelper.success(f"{'GET /api/v1/retry':<28} -> 200 OK (Sisa Token: {remaining:.2f})")


def demo_job_queue():
    ANSIHelper.header("SIMULASI 3: ASYNC TASK QUEUE (BACKGROUND WORKER)")
    queue = JobQueue()

    tasks = [
        ("SEND_WELCOME_EMAIL", {"email": "alex@example.com", "template": "onboarding"}),
        ("GENERATE_PDF_INVOICE", {"order_id": "INV-9901", "amount": 450000}),
        ("SYNC_ANALYTICS_DATA", {"event": "user_signup", "timestamp": time.time()}),
    ]

    for name, payload in tasks:
        job = queue.enqueue(name, payload)
        ANSIHelper.info(f"Enqueued Job #{job.id} - {job.name}")

    print(f"\n{MAGENTA}{BOLD}Worker mulai mengeksekusi antrean tugas...{RESET}")
    while True:
        job = queue.process_next()
        if not job:
            break
        print(f" {YELLOW}[▶ EXECUTING]{RESET} Job #{job.id} [{job.name}] ...", end="", flush=True)
        time.sleep(0.3)
        job.status = "COMPLETED"
        print(f"\r {GREEN}[✓ FINISHED]{RESET}  Job #{job.id} [{job.name}] Status: {job.status}     ")


def main_menu():
    while True:
        ANSIHelper.header("BACKEND BEGINNER: BAB-07 LAB EXERCISE INTERAKTIF")
        print(" Pilih skenario demonstrasi:")
        print(f"  {BOLD}1.{RESET} In-Memory Cache (LRU & TTL)")
        print(f"  {BOLD}2.{RESET} API Rate Limiting (Token Bucket)")
        print(f"  {BOLD}3.{RESET} Background Asynchronous Worker Queue")
        print(f"  {BOLD}4.{RESET} Jalankan Seluruh Simulasi Sekaligus")
        print(f"  {BOLD}5.{RESET} Keluar")

        choice = input(f"\n{BOLD}Pilihan Anda (1-5): {RESET}").strip()

        if choice == "1":
            demo_cache_lifecycle()
        elif choice == "2":
            demo_rate_limiter()
        elif choice == "3":
            demo_job_queue()
        elif choice == "4":
            demo_cache_lifecycle()
            demo_rate_limiter()
            demo_job_queue()
        elif choice == "5":
            print(f"\n{GREEN}Selesai. Terima kasih telah menyelesaikan lab BAB-07!{RESET}\n")
            sys.exit(0)
        else:
            ANSIHelper.warning("Pilihan tidak valid, silakan coba lagi.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        demo_cache_lifecycle()
        demo_rate_limiter()
        demo_job_queue()
        sys.exit(0)
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Program dihentikan pengguna.{RESET}")
        sys.exit(0)

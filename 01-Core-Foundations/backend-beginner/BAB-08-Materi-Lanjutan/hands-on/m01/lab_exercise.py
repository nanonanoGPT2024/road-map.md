#!/usr/bin/env python3
"""
Lab Exercise: Hands-on Fondasi Inti Backend Lanjutan (BAB-08)
Simulasi Interaktif Komponen Arsitektur Backend:
1. In-Memory Cache & TTL Expiration (Cache-Aside Pattern)
2. Token Bucket Rate Limiter (Traffic Shaping)
3. Background Worker & Job Queue (Asynchronous Processing)
4. Pub/Sub Event Bus (Event-Driven Decoupling)
"""

import time
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"


# ============================================================================
# 1. In-Memory Cache with TTL (Cache-Aside Simulation)
# ============================================================================
@dataclass
class CacheEntry:
    val: Any
    expires_at: float


class InMemoryCache:
    def __init__(self, default_ttl_sec: float = 3.0):
        self.default_ttl = default_ttl_sec
        self.store: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self.store.get(key)
        if entry:
            if time.time() < entry.expires_at:
                self.hits += 1
                return entry.val
            else:
                del self.store[key]  # Expired item lazy cleanup
        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self.store[key] = CacheEntry(val=value, expires_at=expiry)

    def stats(self) -> str:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total * 100) if total > 0 else 0.0
        return f"{CYAN}Hits: {self.hits} | Misses: {self.misses} | Hit Ratio: {hit_ratio:.1f}%{RESET}"


# ============================================================================
# 2. Token Bucket Rate Limiter
# ============================================================================
class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = float(capacity)
        self.refill_rate = refill_rate_per_sec
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def allow_request(self, tokens_requested: int = 1) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens_requested:
                self.tokens -= tokens_requested
                return True
            return False


# ============================================================================
# 3. Asynchronous Job Queue & Background Worker
# ============================================================================
@dataclass
class Job:
    job_id: str
    task_name: str
    payload: dict
    created_at: float = field(default_factory=time.time)


class BackgroundJobWorker:
    def __init__(self):
        self.work_queue: queue.Queue = queue.Queue()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.processed_count = 0

    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False

    def enqueue(self, task_name: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id=job_id, task_name=task_name, payload=payload)
        self.work_queue.put(job)
        return job_id

    def _worker_loop(self):
        while self.running:
            try:
                job: Job = self.work_queue.get(timeout=0.2)
                # Simulasi pekerjaan backend intensif (e.g. kirim email/generate PDF)
                time.sleep(0.4)
                self.processed_count += 1
                print(f"  {MAGENTA}[Worker Processed]{RESET} Job #{job.job_id} [{job.task_name}] -> Payload: {job.payload}")
                self.work_queue.task_done()
            except queue.Empty:
                continue


# ============================================================================
# 4. Event-Driven Pub/Sub Bus
# ============================================================================
class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[dict], None]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[dict], None]):
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append(handler)

    def publish(self, event_name: str, data: dict):
        if event_name in self.subscribers:
            for handler in self.subscribers[event_name]:
                handler(data)


# ============================================================================
# Interactive Demos & CLI Runner
# ============================================================================
def demo_cache_aside():
    print(f"\n{BOLD}{YELLOW}=== DEMO 1: Cache-Aside & TTL Simulation ==={RESET}")
    cache = InMemoryCache(default_ttl_sec=2.0)

    def fetch_user_data(user_id: int):
        cached = cache.get(f"user:{user_id}")
        if cached:
            print(f"  {GREEN}[CACHE HIT]{RESET} user:{user_id} diambil dari cache memory: {cached}")
            return cached
        print(f"  {RED}[CACHE MISS]{RESET} Query lambat ke Database untuk user:{user_id}...")
        time.sleep(0.3)
        user_record = {"id": user_id, "name": f"User_{user_id}", "status": "active"}
        cache.set(f"user:{user_id}", user_record, ttl=2.0)
        return user_record

    print(f"{CYAN}1. Request pertama (dingin):{RESET}")
    fetch_user_data(101)
    print(f"{CYAN}2. Request kedua (panas - harus cache hit):{RESET}")
    fetch_user_data(101)
    print(f"{CYAN}3. Menunggu 2.2 detik hingga TTL kedaluwarsa...{RESET}")
    time.sleep(2.2)
    print(f"{CYAN}4. Request ketiga setelah TTL habis (kembali cache miss):{RESET}")
    fetch_user_data(101)
    print(f"Statistik: {cache.stats()}")


def demo_rate_limiter():
    print(f"\n{BOLD}{YELLOW}=== DEMO 2: Token Bucket Rate Limiter ==={RESET}")
    # Kapasitas 3 token, refill 1 token/detik
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_sec=1.0)
    print(f"Konfigurasi: Kapasitas Bucket = 3, Refill Rate = 1 token/detik")

    for i in range(1, 7):
        allowed = limiter.allow_request()
        if allowed:
            print(f"  Request #{i}: {GREEN}200 OK (Traffic diizinkan){RESET} - Tokens tersisa: {limiter.tokens:.1f}")
        else:
            print(f"  Request #{i}: {RED}429 Too Many Requests (Rate limit terlampaui!){RESET}")
        time.sleep(0.2)

    print(f"{CYAN}Pendingin traffic: jeda 2.1 detik untuk isi ulang token...{RESET}")
    time.sleep(2.1)
    allowed = limiter.allow_request()
    status = f"{GREEN}200 OK{RESET}" if allowed else f"{RED}429 Blocked{RESET}"
    print(f"  Request #{7} (setelah jeda): {status} - Tokens tersisa: {limiter.tokens:.1f}")


def demo_worker_and_events():
    print(f"\n{BOLD}{YELLOW}=== DEMO 3: Asynchronous Job Worker & Pub/Sub Bus ==={RESET}")
    bus = EventBus()
    worker = BackgroundJobWorker()
    worker.start()

    # Event subscribers
    def on_order_created(event):
        print(f"  {BLUE}[EventBus]{RESET} Event 'ORDER_CREATED' diterima untuk Order #{event['order_id']}")
        # Enqueue background task
        worker.enqueue("SEND_INVOICE_EMAIL", {"to": event["email"], "amount": event["total"]})
        worker.enqueue("UPDATE_INVENTORY", {"sku": event["item"], "qty": 1})

    bus.subscribe("ORDER_CREATED", on_order_created)

    print(f"{CYAN}Publishing Event: Simulasi checkout order pelanggan...{RESET}")
    bus.publish("ORDER_CREATED", {"order_id": 9012, "email": "buyer@example.com", "item": "LAPTOP-X", "total": 12500000})

    print(f"{CYAN}Main thread tidak terblokir! Menunggu background worker memproses antrean...{RESET}")
    worker.work_queue.join()
    worker.stop()
    print(f"{GREEN}Semua asynchronous tasks selesai dikerjakan worker.{RESET}")


def interactive_menu():
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{GREEN}  LAB EXERCISE: KONSEP BACKEND LANJUTAN (BAB-08)     {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}")
    print("Pilih modul simulasi:")
    print(" [1] Jalankan Semua Demo Otomatis (Cache, Rate Limiter, Worker, Pub/Sub)")
    print(" [2] Simulasi Cache-Aside & TTL Expiration")
    print(" [3] Simulasi Token Bucket Rate Limiter")
    print(" [4] Simulasi Async Job Worker & EventBus")
    print(" [5] Keluar")

    while True:
        try:
            choice = input(f"\n{BOLD}Pilih opsi [1-5]: {RESET}").strip()
            if choice == "1":
                demo_cache_aside()
                demo_rate_limiter()
                demo_worker_and_events()
            elif choice == "2":
                demo_cache_aside()
            elif choice == "3":
                demo_rate_limiter()
            elif choice == "4":
                demo_worker_and_events()
            elif choice == "5":
                print(f"{GREEN}Terima kasih telah menjalankan lab backend-beginner!{RESET}")
                break
            else:
                print(f"{RED}Pilihan tidak valid, silakan pilih 1-5.{RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Lab dihentikan.{RESET}")
            break


if __name__ == "__main__":
    interactive_menu()

#!/usr/bin/env python3
"""
Hands-On Lab: Backend Foundation - Materi Lanjutan (BAB 09)
Simulasi Interaktif Fondasi Arsitektur Backend:
1. Rate Limiter (Token Bucket Algorithm)
2. In-Memory Cache dengan Time-To-Live (TTL) & Invalidation
3. Asynchronous Background Task Queue & Worker
4. In-Memory Pub/Sub Event Bus
"""

import sys
import time
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# ANSI Color Codes untuk Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"


# ============================================================================
# 1. RATE LIMITER (Token Bucket Algorithm)
# ============================================================================
class TokenBucketRateLimiter:
    """
    Mengontrol laju request masuk untuk mencegah brute-force dan DoS.
    Kapasitas bucket terisi ulang secara berkala seiring berjalannya waktu.
    """
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def allow_request(self, cost: int = 1) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            # Tambahkan token baru berdasarkan waktu yang berlalu
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


# ============================================================================
# 2. CACHE LAYER (Key-Value In-Memory dengan TTL)
# ============================================================================
@dataclass
class CacheEntry:
    val: Any
    expires_at: float


class TTLCache:
    """
    Menyimpan hasil komputasi berat / query database sementara
    untuk mereduksi latency respon backend.
    """
    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if time.time() > entry.expires_at:
                del self._store[key]
                return None
            return entry.val

    def set(self, key: str, value: Any, ttl_seconds: float):
        with self.lock:
            self._store[key] = CacheEntry(val=value, expires_at=time.time() + ttl_seconds)

    def invalidate(self, key: str):
        with self.lock:
            if key in self._store:
                del self._store[key]


# ============================================================================
# 3. BACKGROUND TASK QUEUE (Worker Pool)
# ============================================================================
@dataclass
class Task:
    task_id: str
    name: str
    payload: Any


class BackgroundJobWorker:
    """
    Memproses tugas non-blocking (seperti kirim email, generate report)
    di luar siklus request-response HTTP utama.
    """
    def __init__(self, num_workers: int = 2):
        self.task_queue: queue.Queue[Optional[Task]] = queue.Queue()
        self.workers: List[threading.Thread] = []
        self.running = True

        for i in range(num_workers):
            t = threading.Thread(target=self._worker_loop, args=(f"Worker-{i+1}",), daemon=True)
            t.start()
            self.workers.append(t)

    def enqueue(self, task: Task):
        self.task_queue.put(task)

    def _worker_loop(self, name: str):
        while self.running:
            try:
                task = self.task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if task is None:
                break

            print(f"{MAGENTA}[{name}] Memproses background task '{task.name}' (ID: {task.task_id})...{RESET}")
            # Simulasi waktu eksekusi pekerjaan berat
            time.sleep(0.4)
            print(f"{GREEN}[{name}] Selesai memproses task '{task.name}' (ID: {task.task_id})!{RESET}")
            self.task_queue.task_done()

    def stop(self):
        self.running = False
        for _ in self.workers:
            self.task_queue.put(None)
        for t in self.workers:
            t.join()


# ============================================================================
# 4. EVENT BUS (In-Memory Pub/Sub)
# ============================================================================
class EventBus:
    """
    Pola arsitektur Event-Driven untuk decoupling antar komponen backend.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[Any], None]):
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)

    def publish(self, event_name: str, data: Any):
        if event_name in self._subscribers:
            for handler in self._subscribers[event_name]:
                handler(data)


# ============================================================================
# INTEGRASI SIMULASI SISTEM BACKEND
# ============================================================================
class BackendEngine:
    def __init__(self):
        self.rate_limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_sec=1.0)
        self.cache = TTLCache()
        self.job_worker = BackgroundJobWorker(num_workers=2)
        self.event_bus = EventBus()

        # Wiring Event Bus: Log audit saat user terdaftar
        self.event_bus.subscribe("user_registered", self._on_user_registered_audit)

    def _on_user_registered_audit(self, user_data: Dict[str, Any]):
        print(f"{CYAN}[Audit-Subscriber] Event 'user_registered' diterima untuk: {user_data.get('email')}{RESET}")

    def handle_api_request(self, endpoint: str, client_ip: str) -> Dict[str, Any]:
        print(f"\n{BOLD}{BLUE}--- Incoming HTTP GET {endpoint} dari {client_ip} ---{RESET}")

        # 1. Evaluasi Rate Limiting
        if not self.rate_limiter.allow_request():
            print(f"{RED}[429 Too Many Requests] Rate limit terlampaui untuk {client_ip}!{RESET}")
            return {"status": 429, "error": "Rate limit exceeded. Try again later."}

        # 2. Cek Cache
        cache_key = f"endpoint:{endpoint}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            print(f"{GREEN}[200 OK (CACHE HIT)] Data diambil dari Redis-like memory cache.{RESET}")
            return {"status": 200, "source": "cache", "data": cached_result}

        # 3. Cache Miss: Simulasi Query Database
        print(f"{YELLOW}[CACHE MISS] Mengakses database utama (simulasi latency query)...{RESET}")
        time.sleep(0.3)
        db_data = {"endpoint": endpoint, "timestamp": time.time(), "records": 42}

        # Simpan ke Cache dengan TTL 2.5 detik
        self.cache.set(cache_key, db_data, ttl_seconds=2.5)
        print(f"{CYAN}[Cache Saved] Disimpan ke cache selama 2.5 detik.{RESET}")

        return {"status": 200, "source": "database", "data": db_data}

    def register_user(self, email: str):
        print(f"\n{BOLD}{BLUE}--- Registrasi User: {email} ---{RESET}")
        user_info = {"email": email, "created_at": time.time()}

        # Publish Event
        self.event_bus.publish("user_registered", user_info)

        # Delegasikan pengiriman welcome email ke background queue
        self.job_worker.enqueue(
            Task(
                task_id=f"email-{int(time.time()*1000)}",
                name="SendWelcomeEmail",
                payload={"email": email}
            )
        )
        print(f"{GREEN}[API Response] User terdaftar. Email dikirim secara asynchronous di background.{RESET}")


# ============================================================================
# DEMO RUNNER & INTERACTIVE MENU
# ============================================================================
def run_automatic_demo(engine: BackendEngine):
    print(f"\n{BOLD}{GREEN}=== MEMULAI SIMULASI OTOMATIS (BAB-09 MATERI LANJUTAN) ==={RESET}\n")

    print(f"{YELLOW}[Demo 1] Simulasi Cache Hit vs Cache Miss:{RESET}")
    # Request pertama -> Cache Miss
    res1 = engine.handle_api_request("/api/v1/products", "192.168.1.10")
    # Request kedua -> Cache Hit
    res2 = engine.handle_api_request("/api/v1/products", "192.168.1.10")

    time.sleep(0.5)
    print(f"\n{YELLOW}[Demo 2] Simulasi Rate Limiting (Burst 5 Request Berturut-turut):{RESET}")
    for i in range(1, 6):
        print(f"Request ke-{i}:")
        engine.handle_api_request("/api/v1/orders", "192.168.1.50")
        time.sleep(0.1)

    time.sleep(0.5)
    print(f"\n{YELLOW}[Demo 3] Simulasi Event Bus & Asynchronous Background Tasks:{RESET}")
    engine.register_user("learner@backend-engineer.dev")
    engine.register_user("dev@startup.id")

    # Tunggu worker menyelesaikan antrean task
    print(f"\n{CYAN}Menunggu background worker menyelesaikan antrean...{RESET}")
    engine.job_worker.task_queue.join()
    print(f"\n{BOLD}{GREEN}=== SEMUA DEMO LANJUTAN SELESAI DENGAN SUKSES ==={RESET}\n")


def interactive_menu(engine: BackendEngine):
    while True:
        print(f"\n{BOLD}{CYAN}=== MENU LAB BAB-09 (BACKEND ADVANCED CONCEPTS) ==={RESET}")
        print("1. Kirim API Request (Uji Caching & Rate Limiting)")
        print("2. Daftarkan User Baru (Uji Event Bus & Background Worker)")
        print("3. Jalankan Full Automated Showcase")
        print("4. Keluar")
        choice = input(f"{YELLOW}Pilihan Anda (1-4): {RESET}").strip()

        if choice == "1":
            ep = input("Masukkan path endpoint (default: /api/items): ").strip() or "/api/items"
            engine.handle_api_request(ep, "127.0.0.1")
        elif choice == "2":
            email = input("Masukkan email user (default: test@example.com): ").strip() or "test@example.com"
            engine.register_user(email)
        elif choice == "3":
            run_automatic_demo(engine)
        elif choice == "4":
            print(f"{GREEN}Menutup worker threads dan keluar... Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid! Masukkan angka 1-4.{RESET}")


def main():
    print(f"{BOLD}{MAGENTA}============================================================{RESET}")
    print(f"{BOLD}{MAGENTA}   LAB MANDIRI: MATERI LANJUTAN BACKEND ARCHITECTURE       {RESET}")
    print(f"{BOLD}{MAGENTA}   Konsep: Cache, Rate Limiter, Worker Queue, Event Bus     {RESET}")
    print(f"{BOLD}{MAGENTA}============================================================{RESET}")

    engine = BackendEngine()

    try:
        # Jika argumen --auto diberikan atau terminal non-interaktif, jalankan demo otomatis
        if len(sys.argv) > 1 and sys.argv[1] == "--auto":
            run_automatic_demo(engine)
        else:
            # Berikan pilihan langsung jalankan demo atau masuk menu
            print(f"{CYAN}Menjalankan uji demo awal...{RESET}")
            run_automatic_demo(engine)
            if sys.stdin.isatty():
                interactive_menu(engine)
    finally:
        engine.job_worker.stop()


if __name__ == "__main__":
    main()

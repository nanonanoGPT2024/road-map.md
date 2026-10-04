#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB 10 - Materi Lanjutan Backend Architecture
Topik: Caching (TTL/LRU), Rate Limiting (Token Bucket), dan Asynchronous Task Queue.
Simulasi mandiri interaktif dengan output berwarna ANSI terminal.
"""

import time
import sys
import uuid
import hmac
import hashlib
from collections import OrderedDict

# ANSI Escape Sequences untuk Pewarnaan Terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
BG_BLUE = "\033[44m"


class CacheManager:
    """Simulasi In-Memory Cache dengan LRU dan TTL."""
    def __init__(self, capacity: int = 3, default_ttl: float = 5.0):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.storage = OrderedDict()  # key -> (value, expiry_timestamp)

    def get(self, key: str):
        if key not in self.storage:
            return None
        value, expiry = self.storage[key]
        if time.time() > expiry:
            del self.storage[key]
            return None
        self.storage.move_to_end(key)
        return value

    def set(self, key: str, value: str, ttl: float = None):
        if ttl is None:
            ttl = self.default_ttl
        expiry = time.time() + ttl

        if key in self.storage:
            self.storage.move_to_end(key)
        self.storage[key] = (value, expiry)

        if len(self.storage) > self.capacity:
            evicted_key, _ = self.storage.popitem(last=False)
            print(f"{YELLOW}[CACHE EVIC] Kapasitas penuh ({self.capacity}). Menghapus LRU key: '{evicted_key}'{RESET}")


class TokenBucketRateLimiter:
    """Implementasi Token Bucket Rate Limiter."""
    def __init__(self, capacity: int = 5, refill_rate: float = 1.0):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()

    def allow_request(self) -> tuple[bool, float]:
        now = time.time()
        elapsed = now - self.last_refill
        refill = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, self.tokens
        return False, self.tokens


class BackgroundTaskQueue:
    """Simulasi Async Job Queue dan Worker Processing."""
    def __init__(self):
        self.queue = []

    def enqueue(self, task_name: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "name": task_name,
            "payload": payload,
            "status": "QUEUED",
            "enqueued_at": time.time()
        }
        self.queue.append(job)
        return job_id

    def process_all(self):
        if not self.queue:
            print(f"{YELLOW}Tidak ada antrean tugas di worker queue.{RESET}")
            return

        print(f"\n{BLUE}{BOLD}[WORKER] Memulai pemrosesan {len(self.queue)} job latar belakang...{RESET}")
        while self.queue:
            job = self.queue.pop(0)
            print(f"  {CYAN}-> Memproses Job [{job['id']}] - Tipe: {job['name']}{RESET}")
            time.sleep(0.3)
            print(f"     {GREEN}✓ Selesai. Hasil: Notifikasi terkirim ke {job['payload'].get('target', 'N/A')}{RESET}")


def verify_signature(secret_key: str, message: str, signature: str) -> bool:
    """Verifikasi webhook/request signature dengan HMAC-SHA256."""
    expected = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def generate_signature(secret_key: str, message: str) -> str:
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def print_banner():
    print(f"\n{BG_BLUE}{BOLD} ======================================================== {RESET}")
    print(f"{BOLD}{CYAN}   BAB 10: MATERI LANJUTAN BACKEND - HANDS-ON SIMULATOR   {RESET}")
    print(f"{BG_BLUE}{BOLD} ======================================================== {RESET}")


def run_cache_demo(cache: CacheManager):
    print(f"\n{BOLD}{MAGENTA}=== 1. Simulasi In-Memory Cache (TTL & LRU) ==={RESET}")
    print("Menyimpan data cache dengan kapasitas 3 dan TTL default 3 detik...")
    cache.set("user:101", "Budi Santoso", ttl=3.0)
    cache.set("user:102", "Siti Rahma", ttl=3.0)
    cache.set("user:103", "Ahmad Fauzi", ttl=3.0)

    val = cache.get("user:101")
    print(f"{GREEN}[CACHE HIT] Get 'user:101': {val}{RESET}")

    print("Menambahkan 'user:104' (harus memicu LRU eviction)...")
    cache.set("user:104", "Dewi Lestari", ttl=3.0)

    val_evicted = cache.get("user:102")
    print(f"{RED}[CACHE MISS/EVICTED] Get 'user:102': {val_evicted}{RESET}")

    print("Menunggu 3.5 detik untuk menguji kedaluwarsa TTL...")
    time.sleep(3.5)
    val_expired = cache.get("user:101")
    print(f"{RED}[CACHE EXPIRED] Get 'user:101' setelah 3.5s: {val_expired}{RESET}")


def run_rate_limiter_demo(limiter: TokenBucketRateLimiter):
    print(f"\n{BOLD}{MAGENTA}=== 2. Simulasi Token Bucket Rate Limiter ==={RESET}")
    print("Kapasitas bucket: 3 token, refill rate: 1 token/detik.")
    print("Mengirimkan 5 request berturut-turut:")

    for i in range(1, 6):
        allowed, remaining = limiter.allow_request()
        if allowed:
            print(f"  Req #{i}: {GREEN}200 OK{RESET} | Sisa Token: {remaining:.1f}")
        else:
            print(f"  Req #{i}: {RED}429 Too Many Requests{RESET} | Token Habis: {remaining:.1f}")
        time.sleep(0.15)


def run_queue_demo(task_queue: BackgroundTaskQueue):
    print(f"\n{BOLD}{MAGENTA}=== 3. Simulasi Asynchronous Task Queue & Worker ==={RESET}")
    id1 = task_queue.enqueue("SEND_WELCOME_EMAIL", {"target": "user1@example.com"})
    id2 = task_queue.enqueue("GENERATE_REPORT_PDF", {"target": "finance@example.com"})
    id3 = task_queue.enqueue("PUSH_NOTIFICATION", {"target": "device_token_xyz"})
    print(f"{GREEN}[QUEUED] 3 Job berhasil masuk antrean queue (ID: {id1}, {id2}, {id3}){RESET}")
    task_queue.process_all()


def run_security_demo():
    print(f"\n{BOLD}{MAGENTA}=== 4. Simulasi Verifikasi Webhook HMAC-SHA256 ==={RESET}")
    secret = "backend-super-secret-key-2026"
    payload = '{"event": "payment.success", "amount": 250000, "user_id": 99}'

    valid_sig = generate_signature(secret, payload)
    invalid_sig = "a1b2c3d4e5f60000000000000000000000000000000000000000000000000000"

    print(f"Payload: {payload}")
    print(f"Testing valid signature: {valid_sig[:24]}...")
    is_valid = verify_signature(secret, payload, valid_sig)
    status_str = f"{GREEN}VALID (200 Accepted){RESET}" if is_valid else f"{RED}INVALID{RESET}"
    print(f"  Status: {status_str}")

    print(f"Testing tampered signature: {invalid_sig[:24]}...")
    is_valid_fake = verify_signature(secret, payload, invalid_sig)
    status_str_fake = f"{GREEN}VALID{RESET}" if is_valid_fake else f"{RED}REJECTED (403 Unauthorized){RESET}"
    print(f"  Status: {status_str_fake}")


def main():
    print_banner()
    cache = CacheManager(capacity=3, default_ttl=3.0)
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate=1.0)
    task_queue = BackgroundTaskQueue()

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{BOLD}[MODE AUTOMATED TEST]{RESET}")
        run_cache_demo(cache)
        run_rate_limiter_demo(limiter)
        run_queue_demo(task_queue)
        run_security_demo()
        print(f"\n{GREEN}{BOLD}Semua simulasi fondasi materi lanjutan backend selesai dijalankan.{RESET}\n")
        return

    while True:
        print(f"\n{BOLD}Menu Simulasi Interaktif:{RESET}")
        print("  1. Uji Cache In-Memory (LRU & TTL)")
        print("  2. Uji Token Bucket Rate Limiter")
        print("  3. Uji Asynchronous Task Queue & Worker")
        print("  4. Uji Verifikasi Webhook HMAC-SHA256")
        print("  5. Jalankan Semua Demonstrasi Sekaligus")
        print("  0. Keluar")

        choice = input(f"\n{CYAN}Pilih opsi [0-5]: {RESET}").strip()
        if choice == "1":
            run_cache_demo(cache)
        elif choice == "2":
            run_rate_limiter_demo(limiter)
        elif choice == "3":
            run_queue_demo(task_queue)
        elif choice == "4":
            run_security_demo()
        elif choice == "5":
            run_cache_demo(cache)
            run_rate_limiter_demo(limiter)
            run_queue_demo(task_queue)
            run_security_demo()
        elif choice == "0":
            print(f"{GREEN}Terima kasih! Sesi lab selesai.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lab Exercise: Backend Advanced Concepts Simulator
BAB-05: Materi Lanjutan (Caching, Rate Limiting, Async Worker, and Connection Pool)
"""

import time
import uuid
import hashlib
import threading
from typing import Dict, Any, Optional, List
from collections import deque

# ANSI Color Codes for terminal UI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class MockConnectionPool:
    """Simulates a database connection pool with fixed size."""
    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self._available_conns = deque([f"conn-pg-{i+1}" for i in range(pool_size)])
        self._lock = threading.Lock()

    def acquire(self) -> Optional[str]:
        with self._lock:
            if self._available_conns:
                conn = self._available_conns.popleft()
                print(f"  {DIM}[Pool]{RESET} Acquired {CYAN}{conn}{RESET} (remaining: {len(self._available_conns)})")
                return conn
            print(f"  {RED}[Pool Exhausted]{RESET} No connections available in pool!")
            return None

    def release(self, conn: str):
        with self._lock:
            self._available_conns.append(conn)
            print(f"  {DIM}[Pool]{RESET} Released {CYAN}{conn}{RESET} (available: {len(self._available_conns)})")


class TokenBucketRateLimiter:
    """Simulates Token Bucket Rate Limiting per IP address."""
    def __init__(self, capacity: int = 3, refill_rate_per_sec: float = 1.0):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.storage: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def allow_request(self, client_ip: str) -> bool:
        with self._lock:
            now = time.time()
            if client_ip not in self.storage:
                self.storage[client_ip] = {"tokens": self.capacity, "last_updated": now}

            state = self.storage[client_ip]
            elapsed = now - state["last_updated"]
            added_tokens = elapsed * self.refill_rate
            state["tokens"] = min(self.capacity, state["tokens"] + added_tokens)
            state["last_updated"] = now

            if state["tokens"] >= 1.0:
                state["tokens"] -= 1.0
                tokens_left = round(state["tokens"], 2)
                print(f"  {GREEN}[RateLimiter: ALLOWED]{RESET} IP: {client_ip} | Tokens left: {tokens_left}")
                return True
            else:
                print(f"  {RED}[RateLimiter: 429 TOO MANY REQUESTS]{RESET} IP: {client_ip} | Bucket empty!")
                return False


class CacheManager:
    """Simulates an in-memory cache (like Redis) with TTL."""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if time.time() > entry["expires_at"]:
                del self._store[key]
                return None
            return entry["val"]

    def set(self, key: str, val: Any, ttl_seconds: float):
        with self._lock:
            self._store[key] = {
                "val": val,
                "expires_at": time.time() + ttl_seconds
            }


class BackgroundJobQueue:
    """Simulates asynchronous message queue and background worker thread."""
    def __init__(self):
        self.queue: deque = deque()
        self.running = True
        self.processed_jobs: List[str] = []
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def enqueue(self, task_name: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = {"id": job_id, "task": task_name, "payload": payload}
        self.queue.append(job)
        print(f"  {MAGENTA}[JobQueue]{RESET} Enqueued task '{task_name}' (JobID: {job_id})")
        return job_id

    def _worker_loop(self):
        while self.running:
            if self.queue:
                job = self.queue.popleft()
                time.sleep(0.4)  # Simulate asynchronous worker processing
                result_str = f"Job {job['id']} ({job['task']}) done with payload {job['payload']}"
                self.processed_jobs.append(result_str)
            else:
                time.sleep(0.1)


class BackendAdvancedSimulator:
    """Coordinates advanced backend architecture components."""
    def __init__(self):
        self.pool = MockConnectionPool(pool_size=2)
        self.rate_limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_sec=0.5)
        self.cache = CacheManager()
        self.queue = BackgroundJobQueue()
        self.idempotency_store: Dict[str, Any] = {}

    def handle_request(self, ip: str, path: str, idem_key: Optional[str] = None) -> Dict[str, Any]:
        print(f"\n{BOLD}--> Incoming Request: {CYAN}{path}{RESET} from {YELLOW}{ip}{RESET}")

        # 1. Rate Limiter Check
        if not self.rate_limiter.allow_request(ip):
            return {"status": 429, "error": "Rate limit exceeded"}

        # 2. Idempotency Check (for state-changing endpoints)
        if idem_key:
            if idem_key in self.idempotency_store:
                print(f"  {YELLOW}[Idempotency HIT]{RESET} Returning cached transaction for key: {idem_key}")
                return {"status": 200, "data": self.idempotency_store[idem_key], "idempotent": True}

        # 3. Cache-Aside Pattern
        cached_result = self.cache.get(path)
        if cached_result:
            print(f"  {GREEN}[Cache HIT (Redis)]{RESET} Key: {path} -> {cached_result}")
            return {"status": 200, "data": cached_result, "source": "cache"}

        print(f"  {YELLOW}[Cache MISS]{RESET} Fetching from simulated Database via Connection Pool...")

        # 4. Acquire DB Connection from Pool
        conn = self.pool.acquire()
        if not conn:
            return {"status": 503, "error": "Service Unavailable - DB Connection Pool Exhausted"}

        try:
            # Simulate DB query latency
            time.sleep(0.3)
            computed_data = f"Response data for {path} (hash: {hashlib.sha256(path.encode()).hexdigest()[:6]})"

            # Cache the result for 3 seconds
            self.cache.set(path, computed_data, ttl_seconds=3.0)
            print(f"  {DIM}[Cache SET]{RESET} Cached key '{path}' with TTL 3.0s")

            # If idempotency key provided, remember it
            if idem_key:
                self.idempotency_store[idem_key] = computed_data

            # 5. Dispatch async background task (e.g. audit log or email notification)
            self.queue.enqueue("AUDIT_LOG", {"path": path, "ip": ip, "timestamp": time.time()})

            return {"status": 200, "data": computed_data, "source": "database"}
        finally:
            self.pool.release(conn)


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
  BAB-05: ADVANCED BACKEND CONCEPTS - HANDS-ON INTERACTIVE SIMULATOR
======================================================================{RESET}
{DIM}Simulating:
 1. Connection Pool (Max 2 connections)
 2. Token Bucket Rate Limiting (Capacity 3 tokens, 0.5 token/sec refill)
 3. Cache-Aside Pattern (TTL 3 seconds)
 4. Idempotency Key Handling
 5. Async Worker & Background Job Processing
======================================================================{RESET}
"""
    print(banner)


def run_interactive_menu():
    sim = BackendAdvancedSimulator()
    print_banner()

    menu = f"""
{BOLD}Choose an action to test:{RESET}
 {GREEN}[1]{RESET} Standard Request (Cache-Aside & Connection Pool flow)
 {GREEN}[2]{RESET} Rapid Burst Requests (Trigger Rate Limiter 429)
 {GREEN}[3]{RESET} Idempotent POST Request (Payment / Order simulation)
 {GREEN}[4]{RESET} Concurrency Stress Test (Connection Pool saturation)
 {GREEN}[5]{RESET} Inspect Background Worker Queue status
 {GREEN}[0]{RESET} Exit Simulator
"""
    while True:
        print(menu)
        try:
            choice = input(f"{BOLD}Enter choice [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == "1":
            path = "/api/v1/products/42"
            res = sim.handle_request(ip="192.168.1.10", path=path)
            print(f"  {BOLD}Status:{RESET} {res['status']} | {res}")

        elif choice == "2":
            print(f"{YELLOW}Sending 5 rapid requests in 0.2s interval...{RESET}")
            for i in range(5):
                res = sim.handle_request(ip="10.0.0.99", path=f"/api/v1/search?q=item_{i}")
                print(f"  Response {i+1}: HTTP {res['status']}")
                time.sleep(0.05)

        elif choice == "3":
            key = f"order-tx-{uuid.uuid4().hex[:6]}"
            print(f"\n{CYAN}--> First dispatch with Idempotency-Key: {key}{RESET}")
            res1 = sim.handle_request(ip="192.168.1.50", path="/api/v1/checkout", idem_key=key)
            print(f"Result 1: {res1}")

            print(f"\n{CYAN}--> Duplicate retry with same Idempotency-Key: {key}{RESET}")
            res2 = sim.handle_request(ip="192.168.1.50", path="/api/v1/checkout", idem_key=key)
            print(f"Result 2: {res2}")

        elif choice == "4":
            print(f"{YELLOW}Spawning 4 concurrent threads with pool_size=2...{RESET}")
            threads = []
            for i in range(4):
                t = threading.Thread(
                    target=lambda idx: sim.handle_request(ip=f"10.0.1.{idx}", path=f"/api/heavy/{idx}"),
                    args=(i,)
                )
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        elif choice == "5":
            print(f"\n{MAGENTA}[Background Worker Status]{RESET}")
            print(f"  Pending tasks in queue: {len(sim.queue.queue)}")
            print(f"  Completed jobs count: {len(sim.queue.processed_jobs)}")
            for log in sim.queue.processed_jobs[-5:]:
                print(f"    - {DIM}{log}{RESET}")

        elif choice == "0":
            print(f"{GREEN}Terminating simulator. Good luck with your backend engineering journey!{RESET}")
            sim.queue.running = False
            break
        else:
            print(f"{RED}Invalid option. Please choose 0 to 5.{RESET}")


if __name__ == "__main__":
    run_interactive_menu()

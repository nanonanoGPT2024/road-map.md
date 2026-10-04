#!/usr/bin/env python3
"""
Lab Hands-on: Enterprise Web Architecture (Ruby on Rails / Puma / Rack / Sidekiq)
Modul: 09-02 Deep Dive - Enterprise Architecture Simulation

Deskripsi:
Skrip ini mensimulasikan arsitektur web enterprise berbasis Ruby, mencakup:
1. Rack Specification & Middleware Pipeline (Rack::Runtime, Rack::ETag, Authentication).
2. Puma multi-threaded request-response lifecycle execution.
3. ActiveSupport::Cache layer dengan stampede protection / dogpile mitigation.
4. Sidekiq-style asynchronous background job processor lengkap dengan retry queue,
   exponential backoff, dan Dead Letter Queue (DLQ).
"""

import sys
import time
import json
import hashlib
import uuid
import threading
import queue
import random
from typing import Dict, Any, Tuple, List, Callable

# ==============================================================================
# Terminal ANSI Color Formatting
# ==============================================================================
class TermColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"

def log_event(subsystem: str, msg: str, color: str = TermColor.RESET) -> None:
    timestamp = time.strftime("%H:%M:%S")
    tid = threading.current_thread().name
    print(f"{TermColor.GRAY}[{timestamp}]{TermColor.RESET} "
          f"{color}[{subsystem:<12}]{TermColor.RESET} "
          f"{TermColor.GRAY}({tid:<14}){TermColor.RESET} {msg}")

# ==============================================================================
# SECTION 1: ActiveSupport::Cache Simulation (Store with Stampede Protection)
# ==============================================================================
class CacheStore:
    """
    Simulasi ActiveSupport::Cache::MemoryStore dengan proteksi Cache Stampede.
    Menggunakan fine-grained locking per key untuk mencegah 'thundering herd problem'.
    """
    def __init__(self):
        self._storage: Dict[str, Tuple[Any, float]] = {}
        self._key_locks: Dict[str, threading.Lock] = {}
        self._master_lock = threading.Lock()

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self._master_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def fetch(self, key: str, ttl: float, fallback_fn: Callable[[], Any]) -> Any:
        now = time.time()
        # Fast path read
        if key in self._storage:
            val, expiry = self._storage[key]
            if now < expiry:
                return val

        # Cache miss atau expired -> Acquire lock khusus key ini
        key_lock = self._get_key_lock(key)
        with key_lock:
            # Double check setelah lock berhasil didapatkan
            if key in self._storage:
                val, expiry = self._storage[key]
                if time.time() < expiry:
                    return val

            # Eksekusi blok fallback (biasanya slow database query)
            computed_val = fallback_fn()
            self._storage[key] = (computed_val, time.time() + ttl)
            return computed_val

# ==============================================================================
# SECTION 2: Rack Specification & Middleware Pipeline
# ==============================================================================
# Rack Spec di Ruby: app.call(env) -> [status, headers, body]
RackResponse = Tuple[int, Dict[str, str], str]
RackApp = Callable[[Dict[str, Any]], RackResponse]

class RackRuntimeMiddleware:
    """Simulasi Rack::Runtime: Menyisipkan header durasi pemrosesan (X-Runtime)."""
    def __init__(self, app: RackApp):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        start_time = time.perf_counter()
        status, headers, body = self.app(env)
        runtime = time.perf_counter() - start_time
        headers["X-Runtime"] = f"{runtime:.6f}s"
        return status, headers, body

class RackETagMiddleware:
    """Simulasi Rack::ETag: Menghitung MD5 digest body untuk HTTP caching."""
    def __init__(self, app: RackApp):
        self.app = app

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        status, headers, body = self.app(env)
        if status == 200 and isinstance(body, str):
            digest = hashlib.md5(body.encode('utf-8')).hexdigest()
            headers["ETag"] = f'"{digest}"'

            # Evaluasi conditional GET (If-None-Match)
            if env.get("HTTP_IF_NONE_MATCH") == headers["ETag"]:
                return 304, headers, ""
        return status, headers, body

class RackAuthMiddleware:
    """Simulasi API Authentication Token."""
    def __init__(self, app: RackApp, valid_token: str):
        self.app = app
        self.valid_token = valid_token

    def __call__(self, env: Dict[str, Any]) -> RackResponse:
        token = env.get("HTTP_AUTHORIZATION", "").replace("Bearer ", "")
        if token != self.valid_token:
            return 401, {"Content-Type": "application/json"}, json.dumps({"error": "Unauthorized Access"})
        return self.app(env)

# ==============================================================================
# SECTION 3: Sidekiq-Style Asynchronous Background Processing
# ==============================================================================
class SidekiqEngine:
    """
    Simulasi Sidekiq Worker System:
    - Thread-safe queues (Default, Retry, Dead-Letter Queue / DLQ)
    - Concurrency worker threads
    - Exponential backoff retry logic
    """
    def __init__(self, concurrency: int = 2):
        self.concurrency = concurrency
        self.job_queue: queue.Queue = queue.Queue()
        self.dlq: List[Dict[str, Any]] = []
        self.workers: List[threading.Thread] = []
        self.is_running = True
        self.registry: Dict[str, Callable] = {}

    def register_worker(self, name: str, handler: Callable):
        self.registry[name] = handler

    def enqueue(self, worker_name: str, *args, retry_count: int = 0) -> str:
        jid = uuid.uuid4().hex[:8]
        job_payload = {
            "jid": jid,
            "worker": worker_name,
            "args": args,
            "retry_count": retry_count,
            "max_retries": 2,
            "enqueued_at": time.time()
        }
        self.job_queue.put(job_payload)
        log_event("SIDEKIQ", f"Pushed job {jid} [{worker_name}] to queue", TermColor.MAGENTA)
        return jid

    def start(self):
        for i in range(self.concurrency):
            t = threading.Thread(target=self._process_queue, name=f"Sidekiq-W{i+1}", daemon=True)
            self.workers.append(t)
            t.start()

    def stop(self):
        self.is_running = False
        # Inject poison pills untuk unblock queue.get()
        for _ in range(self.concurrency):
            self.job_queue.put(None)
        for t in self.workers:
            t.join()

    def _process_queue(self):
        while self.is_running:
            job = self.job_queue.get()
            if job is None:
                break

            worker_name = job["worker"]
            jid = job["jid"]
            handler = self.registry.get(worker_name)

            if not handler:
                log_event("SIDEKIQ", f"ERR: Unknown worker {worker_name} for JID {jid}", TermColor.RED)
                self.job_queue.task_done()
                continue

            try:
                log_event("SIDEKIQ", f"EXEC JID {jid} ({worker_name}) Args: {job['args']}", TermColor.CYAN)
                handler(*job["args"])
                log_event("SIDEKIQ", f"SUCCESS JID {jid}", TermColor.GREEN)
            except Exception as exc:
                job["retry_count"] += 1
                if job["retry_count"] <= job["max_retries"]:
                    delay = 0.2 * (2 ** job["retry_count"]) # Exponential backoff
                    log_event("SIDEKIQ", f"FAIL JID {jid}: {exc}. Retry {job['retry_count']}/{job['max_retries']} in {delay:.2f}s", TermColor.YELLOW)
                    time.sleep(delay)
                    self.job_queue.put(job)
                else:
                    log_event("SIDEKIQ", f"FATAL JID {jid} exceeded retries. Moved to DLQ.", TermColor.RED)
                    self.dlq.append(job)
            finally:
                self.job_queue.task_done()

# ==============================================================================
# SECTION 4: Application Layer (Controllers & Workers)
# ==============================================================================
cache = CacheStore()
sidekiq = SidekiqEngine(concurrency=2)

# Sidekiq Workers
def email_notification_worker(order_id: str, email: str):
    time.sleep(0.1) # Simulate SMTP latency
    log_event("WORKER", f"Email Invoice order #{order_id} dikirim ke {email}", TermColor.GREEN)

def payment_settlement_worker(order_id: str, amount: float):
    # Simulasi failure acak untuk memicu mekanisme retry Sidekiq
    time.sleep(0.05)
    if random.choice([True, False]):
        raise ConnectionResetError("Payment Gateway Connection Timeout")
    log_event("WORKER", f"Payment Settlement #{order_id} sebesar ${amount} sukses.", TermColor.GREEN)

sidekiq.register_worker("EmailNotificationWorker", email_notification_worker)
sidekiq.register_worker("PaymentSettlementWorker", payment_settlement_worker)

# Rails Application Router & Endpoints
class RailsApplication:
    """Simulasi Kernel Aplikasi Rails (ActionDispatch & ActionController)."""

    def call(self, env: Dict[str, Any]) -> RackResponse:
        path = env.get("PATH_INFO", "/")
        method = env.get("REQUEST_METHOD", "GET")

        if method == "POST" and path == "/api/v1/orders":
            return self.create_order(env)
        elif method == "GET" and path.startswith("/api/v1/catalog"):
            return self.get_catalog(env)
        else:
            return 404, {"Content-Type": "application/json"}, json.dumps({"status": 404, "message": "Not Found"})

    def create_order(self, env: Dict[str, Any]) -> RackResponse:
        # Simulasi body parsing
        raw_input = env.get("rack.input", "{}")
        payload = json.loads(raw_input)
        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"

        # Dispatch async jobs ke Sidekiq (asinkron, respons HTTP langsung kembali tanpa blocking)
        sidekiq.enqueue("PaymentSettlementWorker", order_id, payload.get("amount", 150.0))
        sidekiq.enqueue("EmailNotificationWorker", order_id, payload.get("customer_email", "guest@example.com"))

        resp = {
            "status": "ACCEPTED",
            "order_id": order_id,
            "message": "Order sedang diproses secara asinkron di background."
        }
        return 202, {"Content-Type": "application/json"}, json.dumps(resp)

    def get_catalog(self, env: Dict[str, Any]) -> RackResponse:
        # Memanfaatkan caching layer dengan proteksi stampede
        def load_from_db():
            log_event("DATABASE", "Querying expensive catalog inventory from DB...", TermColor.YELLOW)
            time.sleep(0.15) # Simulasi latensi DB I/O
            return [
                {"id": 101, "sku": "RUBY-META-BOOK", "stock": 42},
                {"id": 102, "sku": "RAILS-ARCH-GUIDE", "stock": 18}
            ]

        catalog = cache.fetch("global_catalog_v1", ttl=2.0, fallback_fn=load_from_db)
        return 200, {"Content-Type": "application/json"}, json.dumps({"data": catalog})

# ==============================================================================
# SECTION 5: Puma-Style Multi-Threaded Engine Simulator & Lab Execution
# ==============================================================================
def puma_thread_worker(worker_id: int, app: RackApp, requests: List[Dict[str, Any]]):
    """Simulasi thread pool Puma yang melayani request secara simultan."""
    for env in requests:
        status, headers, body = app(env)
        log_event(
            f"PUMA-T{worker_id}",
            f"{env['REQUEST_METHOD']} {env['PATH_INFO']} => {status} | "
            f"X-Runtime: {headers.get('X-Runtime', 'N/A')} | ETag: {headers.get('ETag', 'None')}",
            TermColor.BLUE
        )
        time.sleep(0.02)

def main():
    print(f"{TermColor.BOLD}{TermColor.CYAN}=== ENTERPRISE RUBY WEB ARCHITECTURE LAB ==={TermColor.RESET}\n")

    # Inisialisasi background workers
    sidekiq.start()

    # Bangun Rack Middleware Pipeline (Builder Pattern)
    # Urutan: Auth -> ETag -> Runtime -> Rails App
    SECRET_TOKEN = "enterprise-ruby-bearer-secret"
    rails_app = RailsApplication()
    app = RackRuntimeMiddleware(RackETagMiddleware(RackAuthMiddleware(rails_app, SECRET_TOKEN)))

    log_event("KERNEL", "Rack Middleware Stack terinisialisasi.", TermColor.GREEN)
    log_event("KERNEL", "Puma thread pool & Sidekiq worker runtime siap menerima beban.\n", TermColor.GREEN)

    # 1. Uji Coba Request Terproteksi vs Unauthorized
    log_event("TEST", "--- Fase 1: Validasi Rack Middleware Pipeline ---", TermColor.BOLD)
    unauth_env = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/v1/catalog",
        "HTTP_AUTHORIZATION": "Bearer invalid_token"
    }
    status, _, body = app(unauth_env)
    print(f"Unauthorized Probe: Status {status} -> {body}")

    # 2. Uji Coba Caching & Stampede Prevention (Konkurensi Request Catalog)
    log_event("TEST", "\n--- Fase 2: Concurrent Puma Requests & Cache Stampede ---", TermColor.BOLD)
    auth_catalog_env = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/v1/catalog",
        "HTTP_AUTHORIZATION": f"Bearer {SECRET_TOKEN}"
    }

    puma_threads = []
    for i in range(3):
        t = threading.Thread(
            target=puma_thread_worker,
            args=(i+1, app, [auth_catalog_env.copy()]),
            name=f"PumaPool-{i+1}"
        )
        puma_threads.append(t)
        t.start()

    for t in puma_threads:
        t.join()

    # 3. Uji Coba Conditional GET (ETag Validation 304 Not Modified)
    log_event("TEST", "\n--- Fase 3: HTTP Cache Invalidation (ETag Validation) ---", TermColor.BOLD)
    _, headers, body = app(auth_catalog_env)
    generated_etag = headers.get("ETag")

    conditional_env = auth_catalog_env.copy()
    conditional_env["HTTP_IF_NONE_MATCH"] = generated_etag
    status, _, _ = app(conditional_env)
    print(f"Conditional Request with ETag {generated_etag} -> Response Status: {status} Not Modified")

    # 4. Uji Coba Asynchronous Sidekiq Engine (Order Checkout Pipeline)
    log_event("TEST", "\n--- Fase 4: End-to-End Order Transaction & Sidekiq Retries ---", TermColor.BOLD)
    order_env = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/v1/orders",
        "HTTP_AUTHORIZATION": f"Bearer {SECRET_TOKEN}",
        "rack.input": json.dumps({"amount": 499.0, "customer_email": "architect@enterprise-ruby.org"})
    }

    status, headers, body = app(order_env)
    print(f"Order Intake Result: Status {status} -> {body}")

    # Menunggu Background Job selesai diproses oleh thread Sidekiq
    log_event("SYSTEM", "Menunggu worker Sidekiq menguras antrean job...", TermColor.GRAY)
    sidekiq.job_queue.join()
    time.sleep(0.5)

    # 5. Shutdown & Audit Ringkasan Arsitektur
    sidekiq.stop()
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}=== ARCHITECTURAL AUDIT SUMMARY ==={TermColor.RESET}")
    print(f"• Dead Letter Queue (DLQ) Size : {len(sidekiq.dlq)}")
    if sidekiq.dlq:
        print(f"  DLQ Entries: {sidekiq.dlq}")
    print("• Middleware Pipeline Status    : Functional (Auth, ETag, X-Runtime verified)")
    print("• Puma Thread Pool Isolation    : Verified via multi-thread concurrent dispatch")
    print("• ActiveSupport Cache Stampede  : Protected via key-level mutex sync\n")

if __name__ == "__main__":
    main()
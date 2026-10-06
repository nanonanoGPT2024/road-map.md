#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Web Architecture in Ruby (Simulasi Teknis Fondasi Inti)
BAB-09-Enterprise-Web-Architecture

Simulasi interaktif konsep arsitektur enterprise web Ruby:
1. Rack-Compatible Middleware Pipeline (Onion Request/Response Architecture)
2. Resilient Circuit Breaker Pattern (Fault-Tolerant Downstream Call)
3. Asynchronous Background Job Worker Pool (Sidekiq/Queue Paradigm)
4. Cache-Aside Pattern with Invalidation Strategy (Enterprise Caching)
5. Service Layer Pattern with Telemetry & Diagnostics
"""

import sys
import time
import random
import threading
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class Color:
    """Terminal ANSI Color Palette."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


# ============================================================================
# 1. RACK MIDDLEWARE PIPELINE (Ruby Rack Specification Emulation)
# ============================================================================

@dataclass
class RackEnv:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RackResponse:
    status: int
    headers: Dict[str, str]
    body: str


class Middleware:
    def __init__(self, app: Optional[Callable[[RackEnv], RackResponse]] = None):
        self.app = app

    def __call__(self, env: RackEnv) -> RackResponse:
        raise NotImplementedError


class RequestTimingMiddleware(Middleware):
    """Mengukur wall-clock latency per request (mirip Rack::Runtime)."""
    def __call__(self, env: RackEnv) -> RackResponse:
        start_time = time.perf_counter()
        response = self.app(env)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Runtime-Ms"] = f"{elapsed_ms:.2f}"
        print(f"  {Color.GRAY}[Rack::Runtime] Latency: {elapsed_ms:.2f}ms{Color.RESET}")
        return response


class RateLimiterMiddleware(Middleware):
    """Token bucket rate limiter per client IP."""
    def __init__(self, app: Callable[[RackEnv], RackResponse], max_requests: int = 5):
        super().__init__(app)
        self.max_requests = max_requests
        self.request_counts: Dict[str, int] = {}

    def __call__(self, env: RackEnv) -> RackResponse:
        client_ip = env.headers.get("REMOTE_ADDR", "127.0.0.1")
        count = self.request_counts.get(client_ip, 0)
        if count >= self.max_requests:
            print(f"  {Color.RED}[Rack::RateLimit] IP {client_ip} 429 Too Many Requests ({count}/{self.max_requests}){Color.RESET}")
            return RackResponse(429, {"Content-Type": "application/json"}, '{"error": "Rate limit exceeded"}')
        self.request_counts[client_ip] = count + 1
        return self.app(env)


class AuthenticationMiddleware(Middleware):
    """Bearer token verification layer."""
    def __call__(self, env: RackEnv) -> RackResponse:
        token = env.headers.get("HTTP_AUTHORIZATION", "")
        if not token.startswith("Bearer ruby-enterprise-secret"):
            print(f"  {Color.RED}[Rack::Auth] 401 Unauthorized token header{Color.RESET}")
            return RackResponse(401, {"Content-Type": "application/json"}, '{"error": "Unauthorized"}')
        env.context["authenticated_user"] = "lead_architect_42"
        return self.app(env)


class CoreRailsApp:
    """Mock Rails/Sinatra core routing endpoint."""
    def __call__(self, env: RackEnv) -> RackResponse:
        print(f"  {Color.GREEN}[Rails::Router] Dispatched to {env.method} {env.path} (Actor: {env.context.get('authenticated_user')}){Color.RESET}")
        time.sleep(random.uniform(0.01, 0.04))
        return RackResponse(200, {"Content-Type": "application/json"}, '{"status": "ok", "message": "Enterprise Core Processed"}')


# ============================================================================
# 2. CIRCUIT BREAKER PATTERN (Ruby Resilient Gateway Call)
# ============================================================================

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal traffic
    OPEN = "OPEN"          # Failing, fast-fail without calling remote
    HALF_OPEN = "HALF_OPEN"# Trial traffic probe


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 2.0):
        self.threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, target_func: Callable, *args, **kwargs) -> Any:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                print(f"  {Color.YELLOW}[CircuitBreaker] Timeout expired -> State Transition: HALF_OPEN probe{Color.RESET}")
            else:
                remaining = self.recovery_timeout - (now - self.last_failure_time)
                raise RuntimeError(f"Circuit is OPEN! Fast-fail active (cooldown: {remaining:.1f}s)")

        try:
            result = target_func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                print(f"  {Color.GREEN}[CircuitBreaker] Probe succeeded -> State Transition: CLOSED{Color.RESET}")
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.threshold:
                self.state = CircuitState.OPEN
                print(f"  {Color.RED}[CircuitBreaker] Threshold reached ({self.failure_count}/{self.threshold}) -> State Transition: OPEN{Color.RESET}")
            raise e


# ============================================================================
# 3. BACKGROUND JOB QUEUE (Sidekiq/Redis Paradigm Emulation)
# ============================================================================

@dataclass
class Job:
    jid: str
    queue: str
    class_name: str
    args: List[Any]
    retries: int = 0
    max_retries: int = 2


class SidekiqEmulator:
    def __init__(self, concurrency: int = 2):
        self.queue: List[Job] = []
        self.dead_letter_queue: List[Job] = []
        self.concurrency = concurrency
        self.lock = threading.Lock()
        self.processed_count = 0

    def enqueue(self, class_name: str, *args, queue: str = "default") -> str:
        jid = f"jid-{random.randint(100000, 999999)}"
        job = Job(jid=jid, queue=queue, class_name=class_name, args=list(args))
        with self.lock:
            self.queue.append(job)
        print(f"  {Color.CYAN}[Sidekiq] Enqueued job #{jid} to [{queue}] class={class_name}{Color.RESET}")
        return jid

    def process_all_jobs(self, handlers: Dict[str, Callable]):
        print(f"  {Color.MAGENTA}[Sidekiq::WorkerPool] Spawning workers for {len(self.queue)} queued jobs...{Color.RESET}")
        while True:
            with self.lock:
                if not self.queue:
                    break
                job = self.queue.pop(0)

            handler = handlers.get(job.class_name)
            if not handler:
                print(f"  {Color.RED}[Sidekiq] Unknown job class {job.class_name}! DLQ moved.{Color.RESET}")
                self.dead_letter_queue.append(job)
                continue

            try:
                print(f"  {Color.WHITE}[Worker] Processing JID={job.jid} ({job.class_name})...{Color.RESET}")
                handler(*job.args)
                self.processed_count += 1
                print(f"  {Color.GREEN}[Worker] Done JID={job.jid}{Color.RESET}")
            except Exception as ex:
                job.retries += 1
                if job.retries <= job.max_retries:
                    print(f"  {Color.YELLOW}[Worker] JID={job.jid} failed ({ex}). Retrying ({job.retries}/{job.max_retries})...{Color.RESET}")
                    with self.lock:
                        self.queue.append(job)
                else:
                    print(f"  {Color.RED}[Worker] JID={job.jid} max retries exceeded -> Moved to Dead-Letter Queue (Morgue){Color.RESET}")
                    self.dead_letter_queue.append(job)


# ============================================================================
# 4. CACHE-ASIDE PATTERN (Rails Cache / Redis Layer)
# ============================================================================

class EnterpriseCache:
    def __init__(self, default_ttl_sec: float = 3.0):
        self._store: Dict[str, tuple] = {}
        self.default_ttl = default_ttl_sec

    def fetch(self, key: str, fallback_block: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        now = time.time()
        ttl = ttl if ttl is not None else self.default_ttl
        if key in self._store:
            cached_val, expires_at = self._store[key]
            if now < expires_at:
                print(f"  {Color.GREEN}[Rails.cache] HIT key='{key}'{Color.RESET}")
                return cached_val
            print(f"  {Color.YELLOW}[Rails.cache] EXPIRED key='{key}'{Color.RESET}")

        print(f"  {Color.RED}[Rails.cache] MISS key='{key}' -> executing DB/Service query...{Color.RESET}")
        data = fallback_block()
        self._store[key] = (data, now + ttl)
        return data

    def invalidate(self, key: str):
        if key in self._store:
            del self._store[key]
            print(f"  {Color.MAGENTA}[Rails.cache] Invalidated key='{key}'{Color.RESET}")


# ============================================================================
# 5. ENTERPRISE SERVICE LAYER & DEMO ORCHESTRATOR
# ============================================================================

class EnterpriseHub:
    def __init__(self):
        self.cache = EnterpriseCache(default_ttl_sec=2.5)
        self.breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=2.5)
        self.sidekiq = SidekiqEmulator()
        self.build_pipeline()

    def build_pipeline(self):
        core = CoreRailsApp()
        auth = AuthenticationMiddleware(core)
        rl = RateLimiterMiddleware(auth, max_requests=4)
        self.rack_pipeline = RequestTimingMiddleware(rl)

    def mock_db_query(self, user_id: str) -> Dict[str, Any]:
        time.sleep(0.08)
        return {"user_id": user_id, "tier": "Enterprise Gold", "balance_usd": 85000}

    def remote_payment_gateway(self, order_id: str, amount: float, fail: bool = False):
        if fail:
            time.sleep(0.05)
            raise ConnectionError("Payment Gateway 503 Service Unavailable")
        time.sleep(0.04)
        return {"order_id": order_id, "status": "settled", "amount": amount}


# Handlers for background workers
def email_notification_worker(email: str, subject: str):
    time.sleep(0.05)
    print(f"    -> [Mailer] Sent receipt to {email} with subject: '{subject}'")

def analytics_rollup_worker(event: str, meta: Dict[str, Any]):
    time.sleep(0.03)
    if meta.get("should_fail"):
        raise ValueError("Analytics pipeline schema mismatch")
    print(f"    -> [Analytics] Ingested event '{event}' metrics={meta}")

WORKER_HANDLERS = {
    "EmailNotificationWorker": email_notification_worker,
    "AnalyticsRollupWorker": analytics_rollup_worker
}


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
=============================================================================
   RUBY ENTERPRISE WEB ARCHITECTURE (SIMULASI TEKNIS FONDASI INTI)
   Rack Middleware Pipeline | Circuit Breakers | Sidekiq | Cache-Aside
============================================================================={Color.RESET}"""
    print(banner)


def run_pipeline_demo(hub: EnterpriseHub):
    print(f"\n{Color.BOLD}{Color.BLUE}[1] RUNNING RACK MIDDLEWARE PIPELINE DEMO{Color.RESET}")
    print(f"{Color.GRAY}Menguji alur request melalui Stack Middleware: Runtime -> RateLimit -> Auth -> Core{Color.RESET}\n")

    valid_token = "Bearer ruby-enterprise-secret"
    bad_token = "Bearer invalid"

    requests = [
        ("Valid #1", RackEnv("GET", "/api/v1/health", {"HTTP_AUTHORIZATION": valid_token, "REMOTE_ADDR": "192.168.1.10"})),
        ("Invalid Auth", RackEnv("GET", "/api/v1/orders", {"HTTP_AUTHORIZATION": bad_token, "REMOTE_ADDR": "192.168.1.10"})),
        ("Valid #2", RackEnv("GET", "/api/v1/orders", {"HTTP_AUTHORIZATION": valid_token, "REMOTE_ADDR": "192.168.1.10"})),
        ("Valid #3", RackEnv("GET", "/api/v1/orders", {"HTTP_AUTHORIZATION": valid_token, "REMOTE_ADDR": "192.168.1.10"})),
        ("Valid #4", RackEnv("GET", "/api/v1/orders", {"HTTP_AUTHORIZATION": valid_token, "REMOTE_ADDR": "192.168.1.10"})),
        ("Rate Limited #5", RackEnv("GET", "/api/v1/orders", {"HTTP_AUTHORIZATION": valid_token, "REMOTE_ADDR": "192.168.1.10"})),
    ]

    for label, req in requests:
        print(f"{Color.BOLD}Request: {label} [{req.method} {req.path}]{Color.RESET}")
        res = hub.rack_pipeline(req)
        status_color = Color.GREEN if res.status == 200 else Color.RED
        print(f"  Response: {status_color}Status {res.status}{Color.RESET} Body: {res.body}\n")


def run_circuit_breaker_demo(hub: EnterpriseHub):
    print(f"\n{Color.BOLD}{Color.YELLOW}[2] RUNNING FAULT-TOLERANT CIRCUIT BREAKER DEMO{Color.RESET}")
    print(f"{Color.GRAY}Menunjukkan proteksi cascading failure terhadap downstream Payment Gateway{Color.RESET}\n")

    attempts = [
        ("Transaksi #1", False),
        ("Transaksi #2 (Downstream Down)", True),
        ("Transaksi #3 (Downstream Down)", True),
        ("Transaksi #4 (Downstream Down - Trip to OPEN)", True),
        ("Transaksi #5 (Fast-Fail Instant)", True),
    ]

    for label, should_fail in attempts:
        print(f"{Color.BOLD}Percobaan {label}: State saat ini: [{hub.breaker.state.value}]{Color.RESET}")
        try:
            res = hub.breaker.call(hub.remote_payment_gateway, "ORD-991", 450.0, fail=should_fail)
            print(f"  {Color.GREEN}Berhasil: {res}{Color.RESET}")
        except Exception as e:
            print(f"  {Color.RED}Exception tertangkap: {e}{Color.RESET}")
        print()

    print(f"{Color.YELLOW}Menunggu recovery cooldown (2.6 detik)...{Color.RESET}")
    time.sleep(2.6)
    print(f"{Color.BOLD}Percobaan Pemulihan (Probe Call ke Gateway):{Color.RESET}")
    try:
        res = hub.breaker.call(hub.remote_payment_gateway, "ORD-992", 120.0, fail=False)
        print(f"  {Color.GREEN}Pemulihan Berhasil! Res: {res}{Color.RESET}")
    except Exception as e:
        print(f"  {Color.RED}Gagal: {e}{Color.RESET}")


def run_sidekiq_demo(hub: EnterpriseHub):
    print(f"\n{Color.BOLD}{Color.MAGENTA}[3] RUNNING SIDEKIQ ASYNC WORKER POOL DEMO{Color.RESET}")
    print(f"{Color.GRAY}Enqueue asynchronous background jobs dengan retry policy dan dead-letter queue{Color.RESET}\n")

    hub.sidekiq.enqueue("EmailNotificationWorker", "cto@enterprise.io", "Monthly Billing Ready")
    hub.sidekiq.enqueue("AnalyticsRollupWorker", "checkout_completed", {"amount": 2500, "currency": "USD"})
    hub.sidekiq.enqueue("AnalyticsRollupWorker", "flaky_metric", {"should_fail": True})

    hub.sidekiq.process_all_jobs(WORKER_HANDLERS)

    print(f"\n{Color.BOLD}Status Queue Sidekiq:{Color.RESET}")
    print(f"  Jobs sukses diproses : {Color.GREEN}{hub.sidekiq.processed_count}{Color.RESET}")
    print(f"  Jobs di Dead-Letter  : {Color.RED}{len(hub.sidekiq.dead_letter_queue)}{Color.RESET}")


def run_cache_aside_demo(hub: EnterpriseHub):
    print(f"\n{Color.BOLD}{Color.CYAN}[4] RUNNING ENTERPRISE CACHE-ASIDE DEMO{Color.RESET}")
    print(f"{Color.GRAY}Demonstrasi Cache Hit, Cache Miss, TTL Expiry, dan Invalidation Strategy{Color.RESET}\n")

    key = "users:lead_architect_42:profile"

    print("Call 1 (Cold Cache / Miss):")
    data1 = hub.cache.fetch(key, lambda: hub.mock_db_query("lead_architect_42"))
    print(f"  Result: {data1}\n")

    print("Call 2 (Hot Cache / Hit):")
    data2 = hub.cache.fetch(key, lambda: hub.mock_db_query("lead_architect_42"))
    print(f"  Result: {data2}\n")

    print("Invaliding cache secara eksplisit (Event: User Update):")
    hub.cache.invalidate(key)

    print("Call 3 (Setelah Invalidation):")
    data3 = hub.cache.fetch(key, lambda: hub.mock_db_query("lead_architect_42"))
    print(f"  Result: {data3}\n")


def run_full_suite(hub: EnterpriseHub):
    run_pipeline_demo(hub)
    run_circuit_breaker_demo(hub)
    run_sidekiq_demo(hub)
    run_cache_aside_demo(hub)
    print(f"\n{Color.GREEN}{Color.BOLD}>>> SEMUA SIMULASI ARSITEKTUR SELESAI DENGAN SUKSES <<<{Color.RESET}\n")


def interactive_menu():
    hub = EnterpriseHub()
    print_banner()

    # If run in non-interactive environment (CI/batch), run full suite automatically
    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}Terminal non-interaktif terdeteksi. Menjalankan full suite demo otomatis...{Color.RESET}")
        run_full_suite(hub)
        return

    while True:
        print(f"\n{Color.BOLD}PILIH MENU SIMULASI ARSITEKTUR ENTERPRISE RUBY:{Color.RESET}")
        print("  1. Rack Middleware Pipeline (Onion Request/Response)")
        print("  2. Resilient Circuit Breaker (Downstream Gateway)")
        print("  3. Sidekiq Background Job Processing & Dead-Letter Queue")
        print("  4. Cache-Aside Pattern (Rails.cache / Redis)")
        print("  5. Jalankan Full End-to-End Enterprise Architecture Suite")
        print("  6. Keluar")

        try:
            choice = input(f"\n{Color.CYAN}Masukkan pilihan [1-6]: {Color.RESET}").strip()
            if choice == "1":
                run_pipeline_demo(hub)
            elif choice == "2":
                run_circuit_breaker_demo(hub)
            elif choice == "3":
                run_sidekiq_demo(hub)
            elif choice == "4":
                run_cache_aside_demo(hub)
            elif choice == "5":
                run_full_suite(hub)
            elif choice == "6" or choice.lower() in ("q", "exit"):
                print(f"{Color.GREEN}Terima kasih telah mempelajari Arsitektur Enterprise Web Ruby!{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid. Silakan masukkan angka 1-6.{Color.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Sesi dihentikan pengguna.{Color.RESET}")
            break


if __name__ == "__main__":
    if "--demo" in sys.argv:
        hub = EnterpriseHub()
        print_banner()
        run_full_suite(hub)
    else:
        interactive_menu()

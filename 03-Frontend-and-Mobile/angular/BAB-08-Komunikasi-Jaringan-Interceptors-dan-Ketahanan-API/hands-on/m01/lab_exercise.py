#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur HTTP Client, Interceptors & Resilience di Angular
BAB-08: Komunikasi Jaringan, Interceptors, dan Ketahanan API

Modul ini mendemonstrasikan secara interaktif pola interceptor berantai (HttpInterceptorFn),
imunisasi request cloning, retry logic dengan exponential backoff, caching layer, serta
pola Circuit Breaker untuk menjaga ketahanan API aplikasi web modern.
"""

from __future__ import annotations
import dataclasses
import enum
import random
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple, Any

# ==========================================
# Terminal ANSI Formatting Helpers
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[48;5;236m"

def print_banner():
    banner = f"""
{Style.CYAN}{Style.BOLD}======================================================================
  ANGULAR HTTP ARCHITECTURE & RESILIENCE SIMULATOR (CLI LAB)
  BAB 08: Interceptors, Caching, Retry Backoff & Circuit Breaker
======================================================================{Style.RESET}
"""
    print(banner)

# ==========================================
# HTTP Request / Response Modeling (Immutable)
# ==========================================
@dataclasses.dataclass(frozen=True)
class HttpRequest:
    url: str
    method: str = "GET"
    headers: Dict[str, str] = dataclasses.field(default_factory=dict)
    body: Optional[Any] = None
    params: Dict[str, str] = dataclasses.field(default_factory=dict)

    def clone(
        self,
        url: Optional[str] = None,
        method: Optional[str] = None,
        set_headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
    ) -> HttpRequest:
        """Meniru method req.clone() standar Angular HttpClient."""
        new_headers = dict(self.headers)
        if set_headers:
            new_headers.update(set_headers)
        return HttpRequest(
            url=url if url is not None else self.url,
            method=method if method is not None else self.method,
            headers=new_headers,
            body=body if body is not None else self.body,
            params=dict(self.params),
        )

@dataclasses.dataclass
class HttpResponse:
    status: int
    status_text: str
    body: Any
    headers: Dict[str, str] = dataclasses.field(default_factory=dict)
    from_cache: bool = False

class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message

# ==========================================
# Core Interceptor Type Definitions
# ==========================================
HttpHandlerFn = Callable[[HttpRequest], HttpResponse]
HttpInterceptorFn = Callable[[HttpRequest, HttpHandlerFn], HttpResponse]

# ==========================================
# Circuit Breaker Implementation
# ==========================================
class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 3.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_state_change >= self.recovery_time_sec:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True

# ==========================================
# Interceptors Catalog
# ==========================================
class InterceptorSuite:
    def __init__(self, circuit_breaker: CircuitBreaker):
        self.token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.angular_student_lab"
        self.cache: Dict[str, Tuple[float, HttpResponse]] = {}
        self.cache_ttl_sec = 4.0
        self.breaker = circuit_breaker

    def auth_interceptor(self, req: HttpRequest, next_fn: HttpHandlerFn) -> HttpResponse:
        print(f"  {Style.MAGENTA}[AuthInterceptor]{Style.RESET} Injecting Authorization header")
        cloned_req = req.clone(
            set_headers={
                "Authorization": f"Bearer {self.token}",
                "X-Client-Version": "Angular-17.x",
            }
        )
        return next_fn(cloned_req)

    def logging_interceptor(self, req: HttpRequest, next_fn: HttpHandlerFn) -> HttpResponse:
        start_ts = time.time()
        print(f"  {Style.CYAN}[LoggingInterceptor]{Style.RESET} --> {req.method} {req.url}")
        try:
            res = next_fn(req)
            elapsed_ms = (time.time() - start_ts) * 1000
            print(
                f"  {Style.CYAN}[LoggingInterceptor]{Style.RESET} <-- {res.status} {res.status_text} "
                f"({elapsed_ms:.1f}ms) [Cached: {res.from_cache}]"
            )
            return res
        except Exception as err:
            elapsed_ms = (time.time() - start_ts) * 1000
            print(
                f"  {Style.RED}[LoggingInterceptor]{Style.RESET} <-- FAILED after {elapsed_ms:.1f}ms: {err}"
            )
            raise

    def caching_interceptor(self, req: HttpRequest, next_fn: HttpHandlerFn) -> HttpResponse:
        if req.method.upper() != "GET":
            return next_fn(req)

        now = time.time()
        if req.url in self.cache:
            cached_at, cached_res = self.cache[req.url]
            if now - cached_at <= self.cache_ttl_sec:
                print(f"  {Style.GREEN}[CachingInterceptor]{Style.RESET} Cache HIT for '{req.url}'")
                return dataclasses.replace(cached_res, from_cache=True)
            else:
                print(f"  {Style.YELLOW}[CachingInterceptor]{Style.RESET} Cache EXPIRED for '{req.url}'")

        res = next_fn(req)
        if res.status == 200:
            self.cache[req.url] = (now, res)
            print(f"  {Style.GREEN}[CachingInterceptor]{Style.RESET} Response cached for '{req.url}'")
        return res

    def resilience_interceptor(self, req: HttpRequest, next_fn: HttpHandlerFn) -> HttpResponse:
        if not self.breaker.can_execute():
            state_desc = self.breaker.state.value
            raise HttpError(
                503,
                f"Circuit Breaker is {state_desc}. Request immediately fast-failed."
            )

        max_retries = 3
        backoff = 0.4

        for attempt in range(1, max_retries + 1):
            try:
                res = next_fn(req)
                self.breaker.record_success()
                return res
            except HttpError as ex:
                is_transient = ex.status in (500, 502, 503, 504)
                if not is_transient or attempt == max_retries:
                    self.breaker.record_failure()
                    raise

                sleep_time = backoff * (2 ** (attempt - 1)) + random.uniform(0.05, 0.15)
                print(
                    f"  {Style.YELLOW}[ResilienceInterceptor]{Style.RESET} Attempt {attempt} failed ({ex.status}). "
                    f"Retrying in {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)

        raise HttpError(500, "Unexpected termination in resilience pipeline.")

# ==========================================
# Mock Network Backend (HttpBackend)
# ==========================================
class MockHttpBackend:
    def __init__(self):
        self.failure_counter = 0

    def handle(self, req: HttpRequest) -> HttpResponse:
        # Simulate Network Latency
        time.sleep(0.15)

        # Check Authentication
        auth = req.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            raise HttpError(401, "Unauthorized: Bearer token missing")

        # Route matching
        if "/api/products" in req.url:
            return HttpResponse(
                status=200,
                status_text="OK",
                body=[{"id": 1, "name": "NgRx Course"}, {"id": 2, "name": "Signals Mastery"}],
                headers={"Content-Type": "application/json"},
            )

        if "/api/unstable-feed" in req.url:
            self.failure_counter += 1
            if self.failure_counter <= 2:
                raise HttpError(503, "Service Unavailable (Transient Server Spike)")
            return HttpResponse(
                status=200,
                status_text="OK",
                body={"feed": "Live stock ticks", "status": "reconnected"},
            )

        if "/api/failing-service" in req.url:
            raise HttpError(500, "Internal Server Outage")

        raise HttpError(404, "Endpoint Not Found")

# ==========================================
# Angular Pipeline Builder
# ==========================================
class AngularHttpClient:
    def __init__(self, backend: MockHttpBackend, interceptors: List[HttpInterceptorFn]):
        self.backend = backend
        self.interceptors = interceptors

    def send(self, req: HttpRequest) -> HttpResponse:
        """Membangun rantai eksekusi onion-model persis Angular HttpHandler."""
        def build_chain(index: int) -> HttpHandlerFn:
            if index >= len(self.interceptors):
                return self.backend.handle
            interceptor = self.interceptors[index]
            return lambda r: interceptor(r, build_chain(index + 1))

        chain = build_chain(0)
        return chain(req)

# ==========================================
# Interactive Scenario Runner
# ==========================================
def run_interactive_lab():
    breaker = CircuitBreaker(failure_threshold=2, recovery_time_sec=2.5)
    suite = InterceptorSuite(breaker)
    backend = MockHttpBackend()

    # Pipeline: Logging -> Caching -> Resilience -> Auth -> Backend
    pipeline: List[HttpInterceptorFn] = [
        suite.logging_interceptor,
        suite.caching_interceptor,
        suite.resilience_interceptor,
        suite.auth_interceptor,
    ]
    client = AngularHttpClient(backend, pipeline)

    print_banner()

    options = {
        "1": "Scenario 1: Standard GET Request (Auth Token Injection & Logging)",
        "2": "Scenario 2: Caching Interceptor & TTL Expiration Demonstration",
        "3": "Scenario 3: Transient Failure Auto-Recovery (Exponential Backoff)",
        "4": "Scenario 4: Hard Outage & Circuit Breaker Trip (State Transition)",
        "5": "Scenario 5: Run Full Automated Verification Suite",
        "0": "Exit",
    }

    while True:
        print(f"\n{Style.BOLD}PILIH SCENARIO INTERAKTIF:{Style.RESET}")
        for key, desc in options.items():
            print(f"  {Style.WHITE}[{key}]{Style.RESET} {desc}")

        choice = input(f"\n{Style.CYAN}Masukkan nomor skenario [0-5]: {Style.RESET}").strip()

        if choice == "0":
            print(f"\n{Style.GREEN}Terima kasih telah mempelajari arsitektur ketahanan API Angular!{Style.RESET}\n")
            break

        elif choice == "1":
            print(f"\n{Style.BOLD}--- [1] REQUEST DENGAN AUTH & LOGGING ---{Style.RESET}")
            req = HttpRequest(url="https://api.example.com/api/products", method="GET")
            res = client.send(req)
            print(f"{Style.GREEN}Hasil Payload:{Style.RESET} {res.body}")

        elif choice == "2":
            print(f"\n{Style.BOLD}--- [2] CACHING INTERCEPTOR DEMO ---{Style.RESET}")
            req = HttpRequest(url="https://api.example.com/api/products", method="GET")
            print(f"{Style.DIM}Panggilan Pertama (Miss):{Style.RESET}")
            client.send(req)

            print(f"\n{Style.DIM}Panggilan Kedua Segera (Hit):{Style.RESET}")
            client.send(req)

            print(f"\n{Style.DIM}Menunggu 4.2 detik agar cache expire...{Style.RESET}")
            time.sleep(4.2)
            print(f"{Style.DIM}Panggilan Ketiga setelah TTL (Expired -> Refetch):{Style.RESET}")
            client.send(req)

        elif choice == "3":
            print(f"\n{Style.BOLD}--- [3] TRANSIENT FAILURE & EXPONENTIAL BACKOFF ---{Style.RESET}")
            backend.failure_counter = 0
            req = HttpRequest(url="https://api.example.com/api/unstable-feed", method="GET")
            res = client.send(req)
            print(f"{Style.GREEN}Akhir Hasil Berhasil Dipulihkan:{Style.RESET} {res.body}")

        elif choice == "4":
            print(f"\n{Style.BOLD}--- [4] CIRCUIT BREAKER TRIP DEMO ---{Style.RESET}")
            req = HttpRequest(url="https://api.example.com/api/failing-service", method="GET")

            for attempt in range(1, 4):
                print(f"\n{Style.WHITE}Trigger Request #{attempt} (Breaker State: {breaker.state.value}){Style.RESET}")
                try:
                    client.send(req)
                except HttpError as e:
                    print(f"{Style.RED}Ditangkap di Component:{Style.RESET} {e}")

            print(f"\n{Style.DIM}Menunggu masa recovery breaker (3.0 detik)...{Style.RESET}")
            time.sleep(3.0)
            print(f"{Style.WHITE}Status Breaker sekarang saat probe: {breaker.state.value}{Style.RESET}")

        elif choice == "5":
            print(f"\n{Style.BOLD}--- [5] FULL AUTOMATED INTEGRITY TESTS ---{Style.RESET}")
            test_pipeline_integrity()

        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 0-5.{Style.RESET}")

def test_pipeline_integrity():
    """Unit test verifikasi otomatis tanpa interaksi."""
    print(f"{Style.CYAN}Menjalankan uji verifikasi struktur...{Style.RESET}")
    breaker = CircuitBreaker(failure_threshold=2, recovery_time_sec=1.5)
    suite = InterceptorSuite(breaker)
    backend = MockHttpBackend()
    client = AngularHttpClient(
        backend,
        [suite.logging_interceptor, suite.caching_interceptor, suite.resilience_interceptor, suite.auth_interceptor]
    )

    # Test 1: Auth injected
    req1 = HttpRequest(url="https://api.example.com/api/products")
    res1 = client.send(req1)
    assert res1.status == 200, "Test 1 Gagal: Status harus 200"

    # Test 2: Cache Hit
    res2 = client.send(req1)
    assert res2.from_cache is True, "Test 2 Gagal: Harus dari cache"

    # Test 3: Unstable endpoint recovery
    backend.failure_counter = 0
    req3 = HttpRequest(url="https://api.example.com/api/unstable-feed")
    res3 = client.send(req3)
    assert res3.status == 200, "Test 3 Gagal: Recovery retry gagal"

    print(f"{Style.GREEN}{Style.BOLD}SEMUA PENGUJIAN INTEGRITAS 100% SUKSES DIVERIFIKASI!{Style.RESET}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_pipeline_integrity()
    else:
        try:
            run_interactive_lab()
        except KeyboardInterrupt:
            print(f"\n{Style.YELLOW}Sesi lab dihentikan oleh user.{Style.RESET}\n")

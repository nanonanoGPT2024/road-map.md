#!/usr/bin/env python3
"""
Lab Hands-on: Angular Network Pipeline, Interceptor Chain & API Resilience Simulator
Bab 08: Komunikasi Jaringan, Interceptors, dan Ketahanan API - Modul 02 Deep Dive

Simulasi arsitektur HttpClient Angular:
- HttpHandler & HttpInterceptor Onion/Pipeline Pattern
- Auth & Context Tracing Interceptor
- In-Memory Response Caching Interceptor (TTL-based)
- Resilient Retry with Exponential Backoff & Jitter Interceptor
- Mock HttpBackend dengan simulasi Flaky Server (Transient 503 & 401 Auth Refresh)
"""

import time
import random
import uuid
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List

# --- ANSI Styling Constants ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_DIM     = "\033[2m"

# --- HTTP Model Abstractions (Mirrors Angular @angular/common/http) ---

@dataclass
class HttpRequest:
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    params: Dict[str, str] = field(default_factory=dict)

    def clone(self, **changes) -> 'HttpRequest':
        """Meniru method req.clone() Angular untuk modifikasi immutable."""
        new_headers = self.headers.copy()
        if "headers" in changes:
            new_headers.update(changes.pop("headers"))
        new_params = self.params.copy()
        if "params" in changes:
            new_params.update(changes.pop("params"))
        
        merged = {
            "url": self.url,
            "method": self.method,
            "headers": new_headers,
            "body": self.body,
            "params": new_params
        }
        merged.update(changes)
        return HttpRequest(**merged)


@dataclass
class HttpResponse:
    status: int
    status_text: str
    body: Any
    headers: Dict[str, str] = field(default_factory=dict)
    from_cache: bool = False


class HttpErrorResponse(Exception):
    def __init__(self, status: int, status_text: str, error: Any):
        super().__init__(f"HTTP {status} {status_text}: {error}")
        self.status = status
        self.status_text = status_text
        self.error = error


# --- Interceptor Architecture Interfaces ---

class HttpHandler:
    """Kontrak handler Angular untuk memproses request ke middleware berikutnya."""
    def handle(self, req: HttpRequest) -> HttpResponse:
        raise NotImplementedError


class HttpInterceptor:
    """Kontrak interceptor Angular untuk intersepsi request dan response."""
    def intercept(self, req: HttpRequest, next_handler: HttpHandler) -> HttpResponse:
        raise NotImplementedError


class InterceptorChainHandler(HttpHandler):
    """Menyusun rantai interceptor secara rekursif (Onion Architecture)."""
    def __init__(self, interceptor: HttpInterceptor, next_handler: HttpHandler):
        self.interceptor = interceptor
        self.next_handler = next_handler

    def handle(self, req: HttpRequest) -> HttpResponse:
        return self.interceptor.intercept(req, self.next_handler)


# --- Concrete Interceptors ---

class CorrelationAndAuthInterceptor(HttpInterceptor):
    """
    Menyuntikkan Correlation-ID (tracing terdistribusi) dan Bearer Token.
    Mensimulasikan regenerasi token jika status 401 terdeteksi.
    """
    def __init__(self):
        self.token = "initial-expired-jwt-token"

    def intercept(self, req: HttpRequest, next_handler: HttpHandler) -> HttpResponse:
        trace_id = str(uuid.uuid4())[:8]
        modified_req = req.clone(headers={
            "X-Correlation-ID": trace_id,
            "Authorization": f"Bearer {self.token}"
        })
        print(f"  {CLR_CYAN}[AuthInterceptor]{CLR_RESET} Injected Trace-ID: {trace_id}, Auth Bearer...")
        
        try:
            return next_handler.handle(modified_req)
        except HttpErrorResponse as err:
            if err.status == 401:
                print(f"  {CLR_YELLOW}[AuthInterceptor] HTTP 401 terdeteksi! Memperbarui refresh token...{CLR_RESET}")
                time.sleep(0.1)  # Simulasi async token refresh
                self.token = f"refreshed-jwt-valid-{random.randint(100, 999)}"
                retry_req = modified_req.clone(headers={"Authorization": f"Bearer {self.token}"})
                print(f"  {CLR_YELLOW}[AuthInterceptor] Mengulangi request dengan Token baru: {self.token}{CLR_RESET}")
                return next_handler.handle(retry_req)
            raise err


class LoggingInterceptor(HttpInterceptor):
    """Mencatat metrik waktu latensi dan alur siklus request/response."""
    def intercept(self, req: HttpRequest, next_handler: HttpHandler) -> HttpResponse:
        start_time = time.perf_counter()
        print(f"  {CLR_BLUE}[LoggingInterceptor]{CLR_RESET} --> {req.method} {req.url}")
        
        try:
            resp = next_handler.handle(req)
            duration_ms = (time.perf_counter() - start_time) * 1000
            cache_flag = f"{CLR_MAGENTA}[FROM CACHE]{CLR_RESET}" if resp.from_cache else ""
            print(f"  {CLR_BLUE}[LoggingInterceptor]{CLR_RESET} <-- {resp.status} {resp.status_text} "
                  f"({duration_ms:.2f}ms) {cache_flag}")
            return resp
        except HttpErrorResponse as err:
            duration_ms = (time.perf_counter() - start_time) * 1000
            print(f"  {CLR_RED}[LoggingInterceptor]{CLR_RESET} <-- ERROR {err.status} ({duration_ms:.2f}ms)")
            raise err


class CachingInterceptor(HttpInterceptor):
    """
    Caching interceptor berbasis TTL (Time To Live).
    Hanya meng-cache request idempotensial (GET).
    """
    def __init__(self, ttl_seconds: float = 3.0):
        self.ttl = ttl_seconds
        self.cache: Dict[str, tuple[float, HttpResponse]] = {}

    def intercept(self, req: HttpRequest, next_handler: HttpHandler) -> HttpResponse:
        if req.method != "GET":
            return next_handler.handle(req)

        now = time.time()
        if req.url in self.cache:
            timestamp, cached_resp = self.cache[req.url]
            if now - timestamp < self.ttl:
                print(f"  {CLR_MAGENTA}[CachingInterceptor]{CLR_RESET} Cache Hit untuk {req.url}")
                return HttpResponse(
                    status=cached_resp.status,
                    status_text=cached_resp.status_text,
                    body=cached_resp.body,
                    headers=cached_resp.headers,
                    from_cache=True
                )
            else:
                print(f"  {CLR_DIM}[CachingInterceptor] Cache Expired untuk {req.url}{CLR_RESET}")
                del self.cache[req.url]

        response = next_handler.handle(req)
        if response.status == 200:
            self.cache[req.url] = (now, response)
            print(f"  {CLR_MAGENTA}[CachingInterceptor]{CLR_RESET} Disimpan ke cache: {req.url}")
        return response


class RetryWithBackoffInterceptor(HttpInterceptor):
    """
    Ketahanan API: Menangani kegagalan transien (503 Service Unavailable, Network Blip)
    menggunakan algoritma Exponential Backoff dengan penambahan Random Jitter.
    """
    def __init__(self, max_retries: int = 3, initial_delay: float = 0.2):
        self.max_retries = max_retries
        self.initial_delay = initial_delay

    def intercept(self, req: HttpRequest, next_handler: HttpHandler) -> HttpResponse:
        attempts = 0
        while True:
            try:
                return next_handler.handle(req)
            except HttpErrorResponse as err:
                # Hanya retry kode status transien
                if err.status in (503, 504) and attempts < self.max_retries:
                    attempts += 1
                    # Formula: initial_delay * 2^(attempts-1) + jitter
                    delay = (self.initial_delay * (2 ** (attempts - 1))) + random.uniform(0.01, 0.05)
                    print(f"  {CLR_YELLOW}[RetryInterceptor]{CLR_RESET} Transient Error {err.status}! "
                          f"Percobaan retry {attempts}/{self.max_retries} dalam {delay:.3f}s...")
                    time.sleep(delay)
                else:
                    raise err


# --- Mock HttpBackend (Terminal Handler) ---

class MockHttpBackend(HttpHandler):
    """
    Mensimulasikan server backend nyata dengan latensi sintetis dan perilaku flaky.
    """
    def __init__(self):
        self.flaky_counter = 0

    def handle(self, req: HttpRequest) -> HttpResponse:
        # Simulasi latensi jaringan standar (20-60ms)
        time.sleep(random.uniform(0.02, 0.06))

        # 1. Endpoint Otentikasi: Simulasi token kedaluwarsa pertama kali
        if "/api/secure-profile" in req.url:
            auth_header = req.headers.get("Authorization", "")
            if "refreshed-jwt-valid" not in auth_header:
                raise HttpErrorResponse(401, "Unauthorized", {"message": "JWT Token Expired"})
            return HttpResponse(200, "OK", {"user": "lead_engineer", "role": "admin"})

        # 2. Endpoint Flaky: Gagal 2x dengan 503 sebelum berhasil pulih
        if "/api/flaky-telemetry" in req.url:
            self.flaky_counter += 1
            if self.flaky_counter <= 2:
                raise HttpErrorResponse(503, "Service Unavailable", {"error": "Server Overload Temporary"})
            return HttpResponse(200, "OK", {"status": "healthy", "metrics_logged": 42})

        # 3. Endpoint Data Statis / Cache Target
        if "/api/catalog/products" in req.url:
            return HttpResponse(200, "OK", [
                {"id": 101, "name": "Enterprise Angular Suite", "price": 499},
                {"id": 102, "name": "Reactive Systems Kit", "price": 299}
            ])

        return HttpResponse(404, "Not Found", {"error": f"Route {req.url} does not exist"})


# --- Angular HttpClient Emulation ---

class HttpClient:
    """Engine HttpClient yang merangkai interceptor ke dalam bentuk pipeline terpadu."""
    def __init__(self, backend: HttpHandler, interceptors: List[HttpInterceptor]):
        self.pipeline: HttpHandler = backend
        # Rantai dibalik agar interceptor pertama dieksekusi terluar (outermost)
        for interceptor in reversed(interceptors):
            self.pipeline = InterceptorChainHandler(interceptor, self.pipeline)

    def get(self, url: str) -> HttpResponse:
        return self.pipeline.handle(HttpRequest(url=url, method="GET"))

    def post(self, url: str, body: Any) -> HttpResponse:
        return self.pipeline.handle(HttpRequest(url=url, method="POST", body=body))


# --- Main Demonstration Runner ---

def main():
    print(f"\n{CLR_BOLD}{CLR_GREEN}=== LAB HANDS-ON: ANGULAR HTTP CLIENT, INTERCEPTORS & RESILIENCE ==={CLR_RESET}\n")

    # Inisialisasi Backend dan Interceptor Stack
    backend = MockHttpBackend()
    interceptors: List[HttpInterceptor] = [
        LoggingInterceptor(),           # Outer: Mencatat durasi total
        CorrelationAndAuthInterceptor(),# Middle: Injeksi header & refresh handler
        CachingInterceptor(ttl_seconds=1.5), # Middle: Cache interceptor
        RetryWithBackoffInterceptor(max_retries=3, initial_delay=0.1) # Inner: Resilience
    ]

    http = HttpClient(backend=backend, interceptors=interceptors)

    # TEST SCENARIO 1: Cache Miss vs Cache Hit (Response Caching)
    print(f"{CLR_BOLD}--- SKENARIO 1: In-Memory Caching Interceptor & Cache Expiration ---{CLR_RESET}")
    url_catalog = "https://internal.api.enterprise/api/catalog/products"
    
    print(f"{CLR_DIM}Panggilan Pertama (Harus Cache Miss & Simpan ke Memory):{CLR_RESET}")
    res1 = http.get(url_catalog)
    print(f"Data Diterima: {len(res1.body)} item.")

    print(f"\n{CLR_DIM}Panggilan Kedua Segera (Harus Cache Hit langsung tanpa request jaringan):{CLR_RESET}")
    res2 = http.get(url_catalog)
    print(f"Data Diterima: {len(res2.body)} item (From Cache: {res2.from_cache}).")

    print(f"\n{CLR_DIM}Menunggu 1.6 detik hingga TTL kedaluwarsa...{CLR_RESET}")
    time.sleep(1.6)
    print(f"{CLR_DIM}Panggilan Ketiga setelah TTL Habis (Harus Cache Miss lagi):{CLR_RESET}")
    res3 = http.get(url_catalog)
    print(f"Data Diterima: {len(res3.body)} item (From Cache: {res3.from_cache}).\n")

    # TEST SCENARIO 2: Ketahanan API (Transient Failure & Exponential Backoff)
    print(f"{CLR_BOLD}--- SKENARIO 2: Retry with Exponential Backoff & Jitter (HTTP 503 Recovery) ---{CLR_RESET}")
    url_flaky = "https://internal.api.enterprise/api/flaky-telemetry"
    res_flaky = http.get(url_flaky)
    print(f"Hasil Akhir Resilien: {CLR_GREEN}{json.dumps(res_flaky.body)}{CLR_RESET}\n")

    # TEST SCENARIO 3: Autentikasi Otomatis & Seamless Re-auth Pipeline
    print(f"{CLR_BOLD}--- SKENARIO 3: Automatic Token Refresh Interception (HTTP 401 Recovery) ---{CLR_RESET}")
    url_auth = "https://internal.api.enterprise/api/secure-profile"
    res_auth = http.get(url_auth)
    print(f"Hasil Akhir Profil: {CLR_GREEN}{json.dumps(res_auth.body)}{CLR_RESET}\n")

    print(f"{CLR_BOLD}{CLR_GREEN}Pipeline verifikasi sukses! Seluruh siklus interceptor Angular tervalidasi.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
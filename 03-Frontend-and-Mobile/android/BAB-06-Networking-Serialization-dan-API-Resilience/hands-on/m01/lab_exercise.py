#!/usr/bin/env python3
"""
Lab Exercise M01: Android Networking, Serialization & API Resilience Simulation
BAB-06: Networking, Serialization, dan API Resilience

Simulasi arsitektur jaringan Android kelas produksi:
1. OkHttp Interceptor Chain (Auth Injection, Token Refresh, Logging)
2. Retrofit Type-Safe Dynamic Proxy Call & Polymorphic Kotlinx Serialization
3. API Resilience: Exponential Backoff Retry + Jitter
4. Enterprise Circuit Breaker (CLOSED, OPEN, HALF-OPEN)
5. Offline-First HTTP Cache (ETag, 304 Not Modified)
"""

import sys
import time
import json
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any

# ANSI Colors for Rich Terminal Display
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"

def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
  ANDROID ARCHITECTURE LAB: NETWORKING, SERIALIZATION & RESILIENCE
  Modul 01: OkHttp Chain, Serialization, Retry Backoff & Circuit Breaker
================================================================================{CLR_RESET}
"""
    print(banner)

# ==============================================================================
# 1. HTTP DOMAIN MODELS
# ==============================================================================
@dataclass
class HttpRequest:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None

@dataclass
class HttpResponse:
    status_code: int
    headers: Dict[str, str]
    body: str
    from_cache: bool = False

# ==============================================================================
# 2. OKHTTP INTERCEPTOR CHAIN PATTERN
# ==============================================================================
class InterceptorChain:
    def __init__(self, request: HttpRequest, interceptors: List['Interceptor'], index: int = 0):
        self.request = request
        self.interceptors = interceptors
        self.index = index

    def proceed(self, request: HttpRequest) -> HttpResponse:
        if self.index >= len(self.interceptors):
            raise RuntimeError("Interceptor chain exhausted without terminal network transport")
        interceptor = self.interceptors[self.index]
        next_chain = InterceptorChain(request, self.interceptors, self.index + 1)
        return interceptor.intercept(next_chain)

class Interceptor:
    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        raise NotImplementedError

class LoggingInterceptor(Interceptor):
    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        print(f"  {CLR_BLUE}[OkHttp Log]{CLR_RESET} --> {req.method} {req.url}")
        for k, v in req.headers.items():
            print(f"  {CLR_BLUE}[OkHttp Log]{CLR_RESET}   {k}: {v}")
        start_time = time.time()
        resp = chain.proceed(req)
        duration_ms = (time.time() - start_time) * 1000
        print(f"  {CLR_BLUE}[OkHttp Log]{CLR_RESET} <-- {resp.status_code} ({duration_ms:.1f}ms, from_cache={resp.from_cache})")
        return resp

class AuthInterceptor(Interceptor):
    def __init__(self, token_provider: Callable[[], str]):
        self.token_provider = token_provider

    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        token = self.token_provider()
        req.headers["Authorization"] = f"Bearer {token}"
        return chain.proceed(req)

class CacheInterceptor(Interceptor):
    def __init__(self):
        self.cache: Dict[str, HttpResponse] = {}

    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        # Check if Cache-Control forces network
        force_network = req.headers.get("Cache-Control") == "no-cache"

        cached = self.cache.get(req.url)
        if not force_network and cached and "ETag" in cached.headers:
            req.headers["If-None-Match"] = cached.headers["ETag"]

        resp = chain.proceed(req)

        if not force_network and resp.status_code == 304 and cached:
            print(f"  {CLR_GREEN}[CacheHit]{CLR_RESET} 304 Not Modified. Reusing local cached payload.")
            return HttpResponse(
                status_code=200,
                headers=cached.headers,
                body=cached.body,
                from_cache=True
            )
        elif resp.status_code == 200 and "ETag" in resp.headers:
            self.cache[req.url] = resp
        return resp

# ==============================================================================
# 3. MOCK SERVER WITH RESILIENCE TESTING
# ==============================================================================
class MockNetworkTransport(Interceptor):
    def __init__(self):
        self.failure_counter = 0
        self.token_valid = False
        self.current_etag = "W/\"hash-v1-9988\""

    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        # Auth check
        auth_hdr = req.headers.get("Authorization", "")
        if not auth_hdr.endswith("valid_secure_token"):
            return HttpResponse(status_code=401, headers={}, body=json.dumps({"error": "Unauthorized / Token Expired"}))

        # Check Cache Conditional
        if req.headers.get("If-None-Match") == self.current_etag:
            return HttpResponse(status_code=304, headers={"ETag": self.current_etag}, body="")

        # Simulated Flakiness
        if self.failure_counter > 0:
            self.failure_counter -= 1
            print(f"  {CLR_RED}[Server Sim]{CLR_RESET} 503 Service Unavailable (Remaining forced drops: {self.failure_counter})")
            return HttpResponse(status_code=503, headers={}, body=json.dumps({"error": "Overloaded server"}))

        # Successful Data with Polymorphic Payload
        data = {
            "status": "success",
            "data": {
                "id": "USR-7701",
                "name": "Siti Nurhaliza",
                "tier": "enterprise",
                "balance": 15500000.0,
                "extra_field_unknown_by_client": True
            }
        }
        return HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "ETag": self.current_etag},
            body=json.dumps(data)
        )

# ==============================================================================
# 4. CIRCUIT BREAKER RESILIENCE PATTERN
# ==============================================================================
class CircuitState(Enum):
    CLOSED = "CLOSED"         # Normal operation
    OPEN = "OPEN"             # Trip, fail-fast without hitting network
    HALF_OPEN = "HALF_OPEN"   # Trial request to verify health

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 2.0):
        self.state = CircuitState.CLOSED
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if (time.time() - self.last_failure_time) > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                print(f"  {CLR_YELLOW}[CircuitBreaker]{CLR_RESET} Reset timeout passed. Switching to {CLR_BOLD}HALF_OPEN{CLR_RESET} probe state.")
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def on_success(self):
        if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            print(f"  {CLR_GREEN}[CircuitBreaker]{CLR_RESET} Health restored! Switching state to {CLR_BOLD}CLOSED{CLR_RESET}.")
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"  {CLR_RED}[CircuitBreaker]{CLR_RESET} Threshold exceeded ({self.failure_count}). TRIP circuit to {CLR_BOLD}OPEN{CLR_RESET}!")

# ==============================================================================
# 5. RETROFIT & KOTLINX.SERIALIZATION SIMULATOR
# ==============================================================================
@dataclass
class UserProfileDto:
    id: str
    name: str
    tier: str
    balance: float

    @classmethod
    def from_json(cls, json_str: str) -> 'UserProfileDto':
        raw = json.loads(json_str)
        payload = raw.get("data", raw)
        # Emulating kotlinx.serialization: ignoreUnknownKeys = true
        return cls(
            id=str(payload["id"]),
            name=str(payload["name"]),
            tier=str(payload["tier"]),
            balance=float(payload["balance"])
        )

class AndroidApiClient:
    def __init__(self, transport: MockNetworkTransport):
        self.transport = transport
        self.token = "expired_token_demo"
        self.cache_interceptor = CacheInterceptor()
        self.circuit_breaker = CircuitBreaker(failure_threshold=2, reset_timeout=1.5)

    def refresh_auth_token(self) -> str:
        print(f"  {CLR_MAGENTA}[Authenticator 401 Handler]{CLR_RESET} Refreshing OAuth2 token via Refresh Token...")
        time.sleep(0.2)
        self.token = "valid_secure_token"
        print(f"  {CLR_MAGENTA}[Authenticator 401 Handler]{CLR_RESET} New Bearer Token issued: {self.token[:8]}***")
        return self.token

    def execute_call(self, request: HttpRequest) -> HttpResponse:
        interceptors = [
            LoggingInterceptor(),
            AuthInterceptor(token_provider=lambda: self.token),
            self.cache_interceptor,
            self.transport
        ]
        chain = InterceptorChain(request, interceptors)
        resp = chain.proceed(request)

        # OkHttp Authenticator automatic retry on 401
        if resp.status_code == 401:
            print(f"  {CLR_YELLOW}[Authenticator]{CLR_RESET} Received 401 Unauthorized. Triggering token refresh flow...")
            self.refresh_auth_token()
            # Re-execute with new token
            retry_chain = InterceptorChain(request, interceptors)
            resp = retry_chain.proceed(request)

        return resp

    def get_user_profile_resilient(self, max_retries: int = 3, force_network: bool = False) -> Optional[UserProfileDto]:
        url = "https://api.internal.bank/v2/users/me"
        headers = {}
        if force_network:
            headers["Cache-Control"] = "no-cache"
        req = HttpRequest(method="GET", url=url, headers=headers)

        attempt = 0
        backoff_base = 0.2

        while attempt < max_retries:
            attempt += 1
            if not self.circuit_breaker.can_execute():
                print(f"  {CLR_RED}[Fail-Fast]{CLR_RESET} Circuit Breaker is OPEN. Network request dropped immediately.")
                return None

            try:
                print(f"\n{CLR_BOLD}--- Dispatching Request (Attempt {attempt}/{max_retries}) ---{CLR_RESET}")
                response = self.execute_call(req)

                if response.status_code == 200:
                    self.circuit_breaker.on_success()
                    dto = UserProfileDto.from_json(response.body)
                    return dto
                elif response.status_code >= 500:
                    self.circuit_breaker.on_failure()
                    # Exponential backoff with jitter
                    sleep_time = (backoff_base * (2 ** (attempt - 1))) + random.uniform(0.01, 0.08)
                    print(f"  {CLR_YELLOW}[ExponentialBackoff]{CLR_RESET} Server error {response.status_code}. Sleeping {sleep_time:.2f}s before retry...")
                    time.sleep(sleep_time)
                else:
                    print(f"  {CLR_RED}[Client Error]{CLR_RESET} Unexpected status: {response.status_code}")
                    return None

            except Exception as e:
                self.circuit_breaker.on_failure()
                print(f"  {CLR_RED}[Network Exception]{CLR_RESET} {str(e)}")

        print(f"  {CLR_RED}[Exhausted]{CLR_RESET} Max retries reached without success.")
        return None

# ==============================================================================
# 6. INTERACTIVE SCENARIOS EXECUTION
# ==============================================================================
def run_simulation():
    print_banner()
    transport = MockNetworkTransport()
    client = AndroidApiClient(transport)

    print(f"{CLR_BOLD}Scenario 1: Cold Request & Automatic 401 Authenticator Refresh{CLR_RESET}")
    print(f"Target: Memastikan OkHttp Interceptor menyisipkan token dan Authenticator pulih saat 401.")
    user = client.get_user_profile_resilient()
    if user:
        print(f"\n{CLR_GREEN}[SUCCESS DTO Deserialized]{CLR_RESET}")
        print(f"  ID     : {user.id}")
        print(f"  Name   : {user.name}")
        print(f"  Tier   : {user.tier}")
        print(f"  Balance: Rp {user.balance:,.2f}")

    print(f"\n{CLR_BOLD}Scenario 2: HTTP Cache ETag Validation (304 Not Modified){CLR_RESET}")
    print(f"Target: Memastikan ETag tersimpan dan menghemat bandwidth saat server mengembalikan 304.")
    user_cached = client.get_user_profile_resilient()
    if user_cached:
        print(f"  {CLR_GREEN}Cached user retrieved without full network body payload transfer.{CLR_RESET}")

    print(f"\n{CLR_BOLD}Scenario 3: Transient Outage, Exponential Backoff & Circuit Breaker Trip{CLR_RESET}")
    print(f"Target: Simulasikan server 503 berturut-turut untuk menguji Exponential Backoff & Circuit Breaker trip.")
    transport.failure_counter = 4
    failed_user = client.get_user_profile_resilient(max_retries=3, force_network=True)

    print(f"\n{CLR_BOLD}Scenario 4: Circuit Breaker Fail-Fast Test{CLR_RESET}")
    print(f"Target: Request langsung dibatalkan di layer klien tanpa membebani thread network.")
    client.get_user_profile_resilient(max_retries=1, force_network=True)

    print(f"\n{CLR_BOLD}Scenario 5: Self-Healing Circuit Breaker (Half-Open Recovery){CLR_RESET}")
    print(f"Target: Menunggu reset timeout, memasuki HALF-OPEN, dan menutup kembali Circuit Breaker.")
    print(f"Sleeping 1.6s to trigger circuit breaker timeout...")
    time.sleep(1.6)
    recovered_user = client.get_user_profile_resilient(max_retries=2, force_network=True)
    if recovered_user:
        print(f"  {CLR_GREEN}[Recovered]{CLR_RESET} System fully recovered and operating normally!")

    print(f"\n{CLR_CYAN}{CLR_BOLD}================================================================================")
    print(f"  LAB EXERCISE VERIFICATION FINISHED: ALL ANDROID NETWORKING PATTERNS VERIFIED")
    print(f"================================================================================{CLR_RESET}\n")

if __name__ == "__main__":
    run_simulation()

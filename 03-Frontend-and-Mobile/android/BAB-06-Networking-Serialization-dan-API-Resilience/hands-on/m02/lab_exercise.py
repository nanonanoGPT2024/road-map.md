#!/usr/bin/env python3
"""
Lab Hands-on: Android Networking, Serialization & API Resilience Deep Dive
Topic: OkHttp-style Interceptor Chain, Resilience Patterns (Circuit Breaker & Backoff),
       and ETag/Conditional Cache Engine.

Simulates modern Android network stack mechanisms (OkHttp + Retrofit + Moshi).
"""

import time
import json
import random
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

# --- ANSI Formatting Helper ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"

# --- Models & DTOs (Moshi/Kotlinx Serialization Layer) ---
@dataclass
class UserProfile:
    user_id: str
    username: str
    tier: str
    token: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str: str) -> "UserProfile":
        try:
            data = json.loads(json_str)
            # Strict schema validation simulation
            return cls(
                user_id=data["user_id"],
                username=data["username"],
                tier=data["tier"],
                token=data["token"]
            )
        except (KeyError, json.JSONDecodeError) as e:
            raise ValueError(f"Serialization parsing error: {e}")

# --- HTTP Primitives ---
@dataclass
class HttpRequest:
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None

@dataclass
class HttpResponse:
    status_code: int
    headers: Dict[str, str]
    body: str
    network_time_ms: float = 0.0
    from_cache: bool = False

# --- Resilience: Circuit Breaker Pattern ---
class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operational state; traffic passes through
    OPEN = "OPEN"          # Error threshold breached; immediate fail-fast
    HALF_OPEN = "HALF_OPEN"# Trial state: testing upstream availability

class CircuitBreaker:
    """Simulates Resilience4j/Android resilience engine to avoid network thrashing."""
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 2.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def allow_execution(self) -> bool:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                print(f"  {Style.MAGENTA}[CircuitBreaker] Transition: OPEN -> HALF_OPEN (Trialing probe request){Style.RESET}")
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        if self.state != CircuitState.CLOSED:
            print(f"  {Style.GREEN}[CircuitBreaker] Upstream healthy. Transition: {self.state.value} -> CLOSED{Style.RESET}")
            self.state = CircuitState.CLOSED
            self.last_state_change = time.time()

    def record_failure(self):
        self.failure_count += 1
        now = time.time()
        print(f"  {Style.YELLOW}[CircuitBreaker] Failure recorded ({self.failure_count}/{self.failure_threshold}){Style.RESET}")
        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN) and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = now
            print(f"  {Style.RED}[CircuitBreaker] Threshold reached! Transition -> OPEN (Failing Fast for {self.reset_timeout}s){Style.RESET}")

# --- OkHttp Architecture: Interceptors ---
class InterceptorChain:
    """Mirrors RealInterceptorChain in OkHttp."""
    def __init__(self, interceptors: List["Interceptor"], index: int, request: HttpRequest):
        self.interceptors = interceptors
        self.index = index
        self.request = request

    def proceed(self, request: HttpRequest) -> HttpResponse:
        if self.index >= len(self.interceptors):
            raise RuntimeError("Interceptor chain reached end without terminal dispatcher")
        next_chain = InterceptorChain(self.interceptors, self.index + 1, request)
        return self.interceptors[self.index].intercept(next_chain)

class Interceptor:
    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        raise NotImplementedError

class LoggingInterceptor(Interceptor):
    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        print(f"  {Style.GRAY}[--> HTTP {req.method} {req.url}]{Style.RESET}")
        start = time.time()
        response = chain.proceed(req)
        elapsed = (time.time() - start) * 1000.0
        cache_indicator = f"{Style.CYAN}[CACHE]{Style.RESET}" if response.from_cache else f"{Style.MAGENTA}[NET]{Style.RESET}"
        print(f"  {Style.GRAY}[<-- HTTP {response.status_code} {cache_indicator} in {elapsed:.1f}ms]{Style.RESET}")
        return response

class HttpCacheInterceptor(Interceptor):
    """Simulates Android HTTP Cache with RFC 7234 ETag validation."""
    def __init__(self):
        self.cache_store: Dict[str, HttpResponse] = {}

    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        cached = self.cache_store.get(req.url)

        # Inject conditional validation headers if cached entry has an ETag
        if cached and "ETag" in cached.headers:
            req.headers["If-None-Match"] = cached.headers["ETag"]

        response = chain.proceed(req)

        # 304 Not Modified -> return cached body
        if response.status_code == 304 and cached:
            print(f"  {Style.CYAN}[CacheInterceptor] 304 Not Modified. Revalidating local cache entry.{Style.RESET}")
            cached.from_cache = True
            return cached

        # Cache successful GET requests
        if req.method == "GET" and response.status_code == 200:
            if "ETag" in response.headers:
                self.cache_store[req.url] = response
                print(f"  {Style.CYAN}[CacheInterceptor] Cache-Control: Updated cache with ETag {response.headers['ETag']}{Style.RESET}")

        return response

class RetryAndResilienceInterceptor(Interceptor):
    """Implements Exponential Backoff + Jitter & Circuit Breaker."""
    def __init__(self, breaker: CircuitBreaker, max_retries: int = 3):
        self.breaker = breaker
        self.max_retries = max_retries

    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        if not self.breaker.allow_execution():
            # Fast-fail locally without touching radio hardware
            return HttpResponse(
                status_code=503,
                headers={"X-Client-Error": "Circuit-Breaker-Open"},
                body=json.dumps({"error": "Fast-fail: Circuit breaker open"}),
                from_cache=False
            )

        attempts = 0
        backoff = 0.2  # Base backoff 200ms

        while True:
            attempts += 1
            try:
                response = chain.proceed(chain.request)
                if response.status_code >= 500:
                    raise IOError(f"Server error: {response.status_code}")
                
                self.breaker.record_success()
                return response
            except (IOError, TimeoutError) as exc:
                self.breaker.record_failure()
                if attempts > self.max_retries:
                    print(f"  {Style.RED}[Resilience] Exhausted retries ({self.max_retries}/{self.max_retries}). Aborting.{Style.RESET}")
                    return HttpResponse(
                        status_code=504,
                        headers={"X-Client-Error": "Max-Retries-Exceeded"},
                        body=json.dumps({"error": str(exc)}),
                        from_cache=False
                    )

                # Full jitter backoff formula: sleep = rand(0, min(max_backoff, base * 2^attempt))
                sleep_duration = random.uniform(0, backoff * (2 ** (attempts - 1)))
                print(f"  {Style.YELLOW}[Resilience] Request failed ({exc}). Retrying in {sleep_duration:.3f}s (Attempt {attempts})...{Style.RESET}")
                time.sleep(sleep_duration)

class MockNetworkDispatcher(Interceptor):
    """Terminal Interceptor: Mock remote backend with controllable failure & validation."""
    def __init__(self):
        self.server_db = {
            "/api/v1/user/101": {
                "user_id": "101",
                "username": "octane_dev",
                "tier": "enterprise",
                "token": "bearer-secret-7718"
            }
        }
        self.flaky_counter = 0

    def intercept(self, chain: InterceptorChain) -> HttpResponse:
        req = chain.request
        time.sleep(0.05)  # Simulate network latency (50ms)

        # Flaky route triggering temporary crashes
        if req.url.endswith("/flaky"):
            self.flaky_counter += 1
            if self.flaky_counter <= 2:
                raise IOError("Connection reset by remote peer (simulated dropping)")
            return HttpResponse(200, {}, json.dumps({"status": "recovered"}))

        # Outage route triggering sustained 503
        if req.url.endswith("/outage"):
            return HttpResponse(503, {}, json.dumps({"error": "Database unavailable"}))

        # Standard Resource route
        path = req.url.replace("https://api.mobile.internal", "")
        if path in self.server_db:
            body = json.dumps(self.server_db[path])
            etag = f'"{hashlib.md5(body.encode()).hexdigest()[:8]}"'
            
            # Check conditional header
            if req.headers.get("If-None-Match") == etag:
                return HttpResponse(status_code=304, headers={"ETag": etag}, body="")

            return HttpResponse(
                status_code=200,
                headers={"ETag": etag, "Content-Type": "application/json"},
                body=body
            )

        return HttpResponse(status_code=404, headers={}, body=json.dumps({"error": "Not Found"}))

# --- Android Networking Client Facade ---
class OkHttpClient:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(failure_threshold=2, reset_timeout=1.0)
        self.cache_interceptor = HttpCacheInterceptor()
        self.dispatcher = MockNetworkDispatcher()

    def new_call(self, request: HttpRequest) -> HttpResponse:
        interceptors: List[Interceptor] = [
            LoggingInterceptor(),
            self.cache_interceptor,
            RetryAndResilienceInterceptor(self.circuit_breaker, max_retries=3),
            self.dispatcher
        ]
        chain = InterceptorChain(interceptors, 0, request)
        return chain.proceed(request)

# --- Demonstration & Diagnostic Test Runner ---
def print_banner(text: str):
    print(f"\n{Style.BOLD}{'=' * 65}\n  {text}\n{'=' * 65}{Style.RESET}")

def main():
    client = OkHttpClient()
    base_url = "https://api.mobile.internal"

    # SCENARIO 1: Cold Fetch, Moshi Deserialization & Cache Population
    print_banner("SCENARIO 1: Cold Fetch & Strict Deserialization")
    req1 = HttpRequest(url=f"{base_url}/api/v1/user/101")
    res1 = client.new_call(req1)
    
    user = UserProfile.from_json(res1.body)
    print(f"  {Style.GREEN}Parsed User Model via Moshi Engine:{Style.RESET} ID={user.user_id}, Name={user.username}")

    # SCENARIO 2: Conditional Revalidation (HTTP 304 Not Modified)
    print_banner("SCENARIO 2: Conditional GET (304 Cache Revalidation)")
    req2 = HttpRequest(url=f"{base_url}/api/v1/user/101")
    res2 = client.new_call(req2)
    print(f"  Payload retrieved seamlessly from cache: {res2.body}")

    # SCENARIO 3: Transient Fault Recovery with Exponential Backoff
    print_banner("SCENARIO 3: Transient Fault -> Exponential Backoff Recovery")
    req3 = HttpRequest(url=f"{base_url}/flaky")
    res3 = client.new_call(req3)
    print(f"  Result of Flaky Request: Status {res3.status_code}, Body: {res3.body}")

    # SCENARIO 4: Catastrophic Outage & Circuit Breaker Tripping
    print_banner("SCENARIO 4: Persistent 503 -> Circuit Breaker Fast-Fail")
    outage_req = HttpRequest(url=f"{base_url}/outage")
    
    print(f"{Style.BOLD}[Step 1] Triggering repeated server errors...{Style.RESET}")
    client.new_call(outage_req)
    
    print(f"\n{Style.BOLD}[Step 2] Sending subsequent request while Circuit is OPEN...{Style.RESET}")
    res_tripped = client.new_call(outage_req)
    print(f"  Fast-Fail Response: HTTP {res_tripped.status_code} ({res_tripped.body})")

    print(f"\n{Style.BOLD}[Step 3] Waiting out reset timeout to verify HALF_OPEN probe...{Style.RESET}")
    time.sleep(1.1)
    res_half_open = client.new_call(outage_req)
    print(f"  Probe evaluated: HTTP {res_half_open.status_code}")

    print(f"\n{Style.GREEN}{Style.BOLD}All Android API Resilience & Networking scenarios completed successfully.{Style.RESET}\n")

if __name__ == "__main__":
    main()
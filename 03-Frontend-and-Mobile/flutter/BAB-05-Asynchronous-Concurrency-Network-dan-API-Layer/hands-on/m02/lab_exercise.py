#!/usr/bin/env python3
"""
Lab Hands-on: Flutter Concurrency, Event Loop & Network Layer Deep Dive
Simulates:
  1. Flutter/Dart Event Loop mechanics: Priority Microtask Queue vs Event Queue.
  2. Isolate Concurrency: Memory-isolated background worker simulating `compute()`
     preventing UI jank (60 FPS / 16.6ms frame budget budget monitoring).
  3. Resilient Network API Layer: Interceptor pipeline (logging/auth),
     TTL-based Cache Manager, and Exponential Backoff Retries.
"""

import time
import json
import queue
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Optional
from collections import deque

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"

def log_info(module: str, msg: str):
    print(f"{CYAN}[{time.strftime('%H:%M:%S.%f')[:12]}]{RESET} {BOLD}{BLUE}[{module:^12}]{RESET} {msg}")

def log_success(module: str, msg: str):
    print(f"{CYAN}[{time.strftime('%H:%M:%S.%f')[:12]}]{RESET} {BOLD}{GREEN}[{module:^12}]{RESET} {msg}")

def log_warn(module: str, msg: str):
    print(f"{CYAN}[{time.strftime('%H:%M:%S.%f')[:12]}]{RESET} {BOLD}{YELLOW}[{module:^12}]{RESET} {msg}")

def log_error(module: str, msg: str):
    print(f"{CYAN}[{time.strftime('%H:%M:%S.%f')[:12]}]{RESET} {BOLD}{RED}[{module:^12}]{RESET} {msg}")


# ==============================================================================
# 1. DART/FLUTTER EVENT LOOP ENGINE (Microtasks vs Event Queue)
# ==============================================================================

class DartEventLoop:
    """
    Simulates Dart's single-threaded event loop.
    Crucial Rule: All pending Microtasks are completely drained before the next
    item in the Event Queue (Timers, I/O, gesture events) is processed.
    """
    def __init__(self):
        self.microtask_queue: deque = deque()
        self.event_queue: deque = deque()
        self._running = False

    def schedule_microtask(self, name: str, callback: Callable[[], None]):
        """Schedules a high-priority microtask (e.g., Future.microtask)."""
        self.microtask_queue.append((name, callback))

    def post_event(self, name: str, callback: Callable[[], None]):
        """Schedules a standard event (e.g., Timer, I/O, Stream events)."""
        self.event_queue.append((name, callback))

    def run(self):
        """Runs the loop until both queues are exhausted."""
        log_info("EVENT_LOOP", f"Spinning up Dart Event Loop execution engine...")
        cycle = 0
        while self.microtask_queue or self.event_queue:
            cycle += 1
            # Step 1: Drain all microtasks first
            while self.microtask_queue:
                name, task = self.microtask_queue.popleft()
                log_warn("MICROTASK", f"Executing microtask: {name}")
                task()

            # Step 2: Process exactly ONE standard event, then check microtasks again
            if self.event_queue:
                name, event = self.event_queue.popleft()
                log_info("EVENT_QUEUE", f"Processing event: {name}")
                event()

        log_success("EVENT_LOOP", f"Execution cycles finished. Queues clean.")


# ==============================================================================
# 2. ISOLATE ENGINE (Memory Isolation & UI Jank Prevention)
# ==============================================================================

@dataclass
class IsolateMessage:
    port_id: str
    payload: Any
    is_response: bool = False


class FlutterIsolate:
    """
    Simulates a Dart Isolate (`compute()` or `Isolate.spawn()`).
    Memory is NOT shared. Data is serialized/copied across ports via deep copy.
    """
    def __init__(self, name: str):
        self.name = name
        self._send_queue: queue.Queue = queue.Queue()
        self._reply_queue: queue.Queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._isolate_entrypoint, daemon=True)
        self._worker_thread.start()

    def _isolate_entrypoint(self):
        """Dedicated thread executing an independent worker loop."""
        while True:
            msg: IsolateMessage = self._send_queue.get()
            if msg.payload == "__KILL__":
                break

            # Deep copy / de-serialization simulation (Dart structured cloning)
            raw_data = json.loads(msg.payload)
            
            # Heavy CPU-bound task simulation (JSON serialization + cryptographic hashing)
            hashed_results = []
            for item in raw_data:
                encoded = json.dumps(item).encode('utf-8')
                item_digest = hashlib.sha256(encoded).hexdigest()
                hashed_results.append({"id": item["id"], "sha256": item_digest})

            # Simulate heavy processing delay
            time.sleep(0.08)

            response = IsolateMessage(
                port_id=msg.port_id,
                payload=json.dumps(hashed_results),
                is_response=True
            )
            self._reply_queue.put(response)

    def compute(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Offload work to isolate; blocks calling isolate/thread waiting on port."""
        serialized = json.dumps(data)
        self._send_queue.put(IsolateMessage(port_id="isolate_rx_1", payload=serialized))
        response: IsolateMessage = self._reply_queue.get()
        return json.loads(response.payload)

    def terminate(self):
        self._send_queue.put(IsolateMessage(port_id="", payload="__KILL__"))
        self._worker_thread.join()


# ==============================================================================
# 3. NETWORK & API LAYER (Interceptors, Caching, Retry Mechanism)
# ==============================================================================

@dataclass
class HttpRequest:
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


@dataclass
class HttpResponse:
    status_code: int
    data: Dict[str, Any]
    from_cache: bool = False


class NetworkCacheManager:
    """Simulates an In-Memory / Secure Storage Cache with Time-To-Live (TTL)."""
    def __init__(self, ttl_seconds: float = 3.0):
        self._cache: Dict[str, tuple[float, HttpResponse]] = {}
        self._ttl = ttl_seconds

    def _get_key(self, request: HttpRequest) -> str:
        return f"{request.method}:{request.url}"

    def get(self, request: HttpRequest) -> Optional[HttpResponse]:
        key = self._get_key(request)
        if key in self._cache:
            timestamp, response = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return HttpResponse(
                    status_code=response.status_code,
                    data=response.data,
                    from_cache=True
                )
            else:
                del self._cache[key]
        return None

    def put(self, request: HttpRequest, response: HttpResponse):
        key = self._get_key(request)
        self._cache[key] = (time.time(), response)


class DioStyleApiClient:
    """
    Flutter API Client supporting Interceptors, Exponential Backoff, and Cache.
    """
    def __init__(self, cache_manager: NetworkCacheManager):
        self.cache = cache_manager
        self.interceptors: List[Callable[[HttpRequest], None]] = []
        self._mock_server_failures = 2  # Simulates transient errors before success

    def add_interceptor(self, interceptor: Callable[[HttpRequest], None]):
        self.interceptors.append(interceptor)

    def _simulate_network_transport(self, req: HttpRequest) -> HttpResponse:
        """Simulates physical HTTP roundtrip with network failure simulation."""
        time.sleep(0.04) # Network latency
        if self._mock_server_failures > 0:
            self._mock_server_failures -= 1
            raise ConnectionResetError("503 Service Unavailable (Transient Failure)")

        return HttpResponse(
            status_code=200,
            data={"status": "OK", "items": [{"id": i, "val": f"data_{i}"} for i in range(5)]}
        )

    def execute_request(self, request: HttpRequest, max_retries: int = 3) -> HttpResponse:
        # Run interceptors
        for interceptor in self.interceptors:
            interceptor(request)

        # Check Cache
        cached_res = self.cache.get(request)
        if cached_res:
            log_success("CACHE_HIT", f"Returning cached response for {request.url}")
            return cached_res

        # Execute with Exponential Backoff
        attempt = 0
        backoff_delay = 0.05

        while attempt <= max_retries:
            try:
                attempt += 1
                log_info("HTTP_CLIENT", f"Dispatching [{request.method}] {request.url} (Attempt {attempt})")
                res = self._simulate_network_transport(request)
                # Store in cache
                self.cache.put(request, res)
                return res
            except ConnectionResetError as e:
                log_warn("RETRY_POLICY", f"Attempt {attempt} failed: {e}")
                if attempt > max_retries:
                    log_error("HTTP_CLIENT", f"All {max_retries} retries exhausted.")
                    raise
                time.sleep(backoff_delay)
                backoff_delay *= 2  # Exponential backoff


# ==============================================================================
# 4. HANDS-ON DEMONSTRATION WORKFLOW
# ==============================================================================

def main():
    print(f"\n{BOLD}{MAGENTA}{'='*78}{RESET}")
    print(f"{BOLD}{MAGENTA}   FLUTTER DEEP DIVE: EVENT LOOP, ISOLATES & NETWORK ARCHITECTURE   {RESET}")
    print(f"{BOLD}{MAGENTA}{'='*78}{RESET}\n")

    # --- PART 1: Dart Event Loop vs Microtasks Execution Order ---
    print(f"{BOLD}--- 1. Dart Event Loop & Microtask Priority Simulation ---{RESET}")
    loop = DartEventLoop()

    # Schedule items out of sync to test Dart queue prioritization rules
    loop.post_event("Timer-1", lambda: print("   ↳ [Event] Timer 1 executed"))
    loop.schedule_microtask("Microtask-A", lambda: print("   ↳ [Microtask] Future.microtask A completed"))
    loop.post_event("I/O-Socket-Read", lambda: print("   ↳ [Event] Network I/O handled"))
    
    # Nested microtask scheduled inside another microtask
    def nested_microtask_trigger():
        print("   ↳ [Microtask] Future.microtask B executing. Spawning Microtask B.1...")
        loop.schedule_microtask("Microtask-B.1", lambda: print("   ↳ [Microtask] Microtask B.1 resolved"))
    
    loop.schedule_microtask("Microtask-B", nested_microtask_trigger)
    loop.run()

    print(f"\n{BOLD}--- 2. Isolate Concurrency & Frame Budget Guard (UI Thread Jank Prevention) ---{RESET}")
    payload = [{"id": f"rec_{i}", "payload": f"secret_chunk_{i*7}"} for i in range(1500)]

    # UI Frame budget: 60 FPS = 16.66ms per frame
    FRAME_BUDGET_MS = 16.66

    log_info("UI_THREAD", f"Processing {len(payload)} objects on Main Thread (Simulating bad practice)...")
    start_time = time.perf_counter()
    # Synchronous processing blocking the thread
    _ = [hashlib.sha256(json.dumps(x).encode()).hexdigest() for x in payload]
    time.sleep(0.04) # Simulate serialization overhead
    main_thread_duration = (time.perf_counter() - start_time) * 1000

    if main_thread_duration > FRAME_BUDGET_MS:
        dropped_frames = int(main_thread_duration // FRAME_BUDGET_MS)
        log_error("V-SYNC", f"JANK DETECTED! Work took {main_thread_duration:.2f}ms (>16.6ms). Dropped ~{dropped_frames} frames!")

    log_info("UI_THREAD", "Offloading heavy workload to Flutter Background Isolate via compute()...")
    isolate = FlutterIsolate("ParserIsolate")
    start_time = time.perf_counter()
    
    # Delegating to isolate
    results = isolate.compute(payload)
    isolate_duration = (time.perf_counter() - start_time) * 1000

    log_success("ISOLATE", f"Worker resolved {len(results)} items in {isolate_duration:.2f}ms off main thread.")
    log_info("UI_THREAD", f"Main thread remained free to render frames without dropping V-Sync ticks.")
    isolate.terminate()

    print(f"\n{BOLD}--- 3. Network/API Layer: Interceptors, Resilient Retry, & Cache ---{RESET}")
    cache_manager = NetworkCacheManager(ttl_seconds=1.5)
    api_client = DioStyleApiClient(cache_manager)

    # Attach Auth & Logging Interceptor
    def auth_interceptor(req: HttpRequest):
        req.headers["Authorization"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        req.headers["X-Client-Platform"] = "Flutter-Engine-3.x"
        log_info("INTERCEPTOR", f"Injected Bearer Token & metadata headers into {req.url}")

    api_client.add_interceptor(auth_interceptor)

    test_request = HttpRequest(url="https://api.internal.service/v1/feed")

    # Request 1: Should fail twice with transient errors, retry with exponential backoff, then succeed and cache
    log_info("DEMO", "Executing Request #1 (Transient Errors with Auto-Retry):")
    res1 = api_client.execute_request(test_request)
    log_success("RESPONSE", f"HTTP {res1.status_code} | Cache={res1.from_cache} | Data count: {len(res1.data['items'])}")

    # Request 2: Should immediately hit cache
    log_info("DEMO", "Executing Request #2 immediately (Testing In-Memory Cache):")
    res2 = api_client.execute_request(test_request)
    log_success("RESPONSE", f"HTTP {res2.status_code} | Cache={res2.from_cache} | Data count: {len(res2.data['items'])}")

    # Request 3: Expire TTL and verify fresh fetch
    log_info("DEMO", "Waiting for Cache TTL to expire (1.6s)...")
    time.sleep(1.6)
    res3 = api_client.execute_request(test_request)
    log_success("RESPONSE", f"HTTP {res3.status_code} | Cache={res3.from_cache} (Cache expired, refetched)")

    print(f"\n{BOLD}{GREEN}✔ All Dart/Flutter Concurrency & Network architectural simulations executed successfully.{RESET}\n")

if __name__ == "__main__":
    main()
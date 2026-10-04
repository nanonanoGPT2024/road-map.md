#!/usr/bin/env python3
"""
Lab Hands-on: JS Concurrency Deep Dive
Topic: Concurrency Models, Web Workers & Parallel Computing
Simulates:
  1. The V8 Event Loop: Call Stack, Microtask Queue (Promises), Macrotask Queue (setTimeout/IO).
  2. Main Thread Blocking vs Non-Blocking Asynchronous Offloading.
  3. Web Worker Architecture: Dedicated thread execution with serialized structured cloning.
  4. SharedArrayBuffer & Atomics: Multi-worker shared memory synchronization without race conditions.
"""

import sys
import time
import queue
import threading
from collections import deque
from dataclasses import dataclass
from typing import Callable, Any, List

# ============================================================================
# ANSI Color Formatting for Terminal Visualization
# ============================================================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"      # Main Thread / Call Stack
    YELLOW = "\033[93m"    # Macrotask Queue (Timers/IO)
    GREEN = "\033[92m"     # Microtask Queue (Promises/queueMicrotask)
    MAGENTA = "\033[95m"   # Web Workers
    RED = "\033[91m"       # Blocking / Contention warnings
    BLUE = "\033[94m"      # Shared Memory / Atomics

def log_event(domain: str, color: str, msg: str):
    timestamp = time.strftime("%H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    print(f"{Colors.DIM}[{timestamp}.{millis:03d}]{Colors.RESET} {color}{Colors.BOLD}[{domain:<14}]{Colors.RESET} {msg}")


# ============================================================================
# 1. Event Loop Simulation: Call Stack, Microtasks & Macrotasks
# ============================================================================
@dataclass
class Task:
    name: str
    callback: Callable[[], None]

class EventLoop:
    """
    Accurately models JavaScript's Turn-of-Event-Loop:
    1. Execute synchronous script (Call Stack).
    2. Completely drain the Microtask Queue (Promises, queueMicrotask).
    3. Take ONE Macrotask from the Macrotask Queue (setTimeout, I/O).
    4. Repeat step 2 (Drain microtasks created by the macrotask).
    """
    def __init__(self):
        self.microtask_queue: deque[Task] = deque()
        self.macrotask_queue: deque[Task] = deque()
        self.is_running = False

    def queue_microtask(self, name: str, callback: Callable[[], None]):
        """Equivalent to Promise.resolve().then(...) or queueMicrotask(...)"""
        self.microtask_queue.append(Task(name, callback))

    def set_timeout(self, name: str, callback: Callable[[], None], delay_ms: float = 0):
        """Simulates Web APIs timer subsystem enqueuing into the Macrotask Queue."""
        def timer_thread():
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            self.macrotask_queue.append(Task(name, callback))
        threading.Thread(target=timer_thread, daemon=True).start()

    def run(self):
        log_event("EVENT_LOOP", Colors.CYAN, "Event Loop initialized and monitoring queues...")
        self.is_running = True

        while self.is_running:
            # Drain ALL Microtasks completely before processing next Macrotask
            while self.microtask_queue:
                micro = self.microtask_queue.popleft()
                log_event("MICROTASK", Colors.GREEN, f"Executing: {micro.name}")
                micro.callback()

            # Process exactly ONE Macrotask
            if self.macrotask_queue:
                macro = self.macrotask_queue.popleft()
                log_event("MACROTASK", Colors.YELLOW, f"Executing: {macro.name}")
                macro.callback()
                # Yield briefly to simulate V8 host environment ticks
                time.sleep(0.01)
                continue

            # Break if no queues have items left and background timers settle
            time.sleep(0.05)
            if not self.microtask_queue and not self.macrotask_queue:
                break

        log_event("EVENT_LOOP", Colors.CYAN, "Event Loop drained. No tasks pending.\n")


# ============================================================================
# 2. Web Worker Simulation (Isolated Threads + postMessage Channel)
# ============================================================================
class WebWorker:
    """
    Simulates a Dedicated Web Worker running in a separate operating system thread.
    Memory is completely isolated. Data transfer occurs via structured cloning (serialization).
    """
    def __init__(self, name: str, script_handler: Callable[['WebWorker', Any], None]):
        self.name = name
        self.script_handler = script_handler
        self._inbox: queue.Queue = queue.Queue()
        self.onmessage: Callable[[Any], None] = lambda data: None
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._alive = True
        self._thread.start()

    def post_message(self, data: Any):
        """Main thread posts data into Worker message queue."""
        log_event(self.name, Colors.MAGENTA, f"Main Thread -> Worker: Dispatching payload: {data}")
        self._inbox.put(data)

    def _worker_loop(self):
        while self._alive:
            try:
                message = self._inbox.get(timeout=0.1)
                # Worker executes its heavy computational script
                self.script_handler(self, message)
            except queue.Empty:
                continue

    def post_message_to_host(self, result: Any):
        """Worker posts calculated results back to host."""
        if self.onmessage:
            self.onmessage(result)

    def terminate(self):
        self._alive = False


# ============================================================================
# 3. SharedArrayBuffer & Atomics Simulation
# ============================================================================
class SharedArrayBuffer:
    """Simulates a raw fixed-length binary memory buffer accessible by multiple threads."""
    def __init__(self, size: int):
        self.buffer = bytearray(size)
        self._lock = threading.Lock()

class Atomics:
    """Simulates JavaScript Atomics methods ensuring low-level thread-safe operations."""
    @staticmethod
    def add(sab: SharedArrayBuffer, index: int, value: int) -> int:
        with sab._lock:
            old_val = sab.buffer[index]
            sab.buffer[index] = (old_val + value) & 0xFF  # Keep within Uint8 range
            return old_val

    @staticmethod
    def load(sab: SharedArrayBuffer, index: int) -> int:
        with sab._lock:
            return sab.buffer[index]


# ============================================================================
# Execution Scenarios
# ============================================================================
def demo_event_loop_priority():
    print(f"\n{Colors.BOLD}=== 1. EVENT LOOP EXECUTION ORDER BENCHMARK ==={Colors.RESET}")
    loop = EventLoop()

    def run_main():
        log_event("CALL_STACK", Colors.CYAN, "1. Synchronous main() executing")

        # Scheduling a Macrotask (setTimeout 0ms)
        loop.set_timeout("setTimeout(() => {}, 0)", lambda: (
            log_event("TIMER", Colors.YELLOW, "Timer Callback running inside Macrotask!"),
            loop.queue_microtask("Nested Promise in Timer", lambda: (
                log_event("MICROTASK", Colors.GREEN, "Resolved Nested Promise inside Macrotask")
            ))
        ), delay_ms=0)

        # Scheduling Microtasks (Promises)
        loop.queue_microtask("Promise.resolve().then(Task 1)", lambda: (
            log_event("PROMISE", Colors.GREEN, "Promise.then 1 executed")
        ))
        loop.queue_microtask("Promise.resolve().then(Task 2)", lambda: (
            log_event("PROMISE", Colors.GREEN, "Promise.then 2 executed")
        ))

        log_event("CALL_STACK", Colors.CYAN, "2. Synchronous main() completed (Stack cleared)")

    run_main()
    loop.run()


def demo_worker_parallelism():
    print(f"{Colors.BOLD}=== 2. WEB WORKER PARALLEL COMPUTING & MESSAGE PASSING ==={Colors.RESET}")

    def heavy_prime_factorization_worker(worker: WebWorker, n: int):
        log_event(worker.name, Colors.MAGENTA, f"Received task: Compute prime factors of {n}")
        start_t = time.perf_counter()
        
        # CPU-intensive calculation
        factors: List[int] = []
        d = 2
        temp = n
        while d * d <= temp:
            while (temp % d) == 0:
                factors.append(d)
                temp //= d
            d += 1
        if temp > 1:
            factors.append(temp)

        elapsed = (time.perf_counter() - start_t) * 1000
        log_event(worker.name, Colors.MAGENTA, f"Computation finished in {elapsed:.2f}ms: {factors}")
        worker.post_message_to_host({"input": n, "factors": factors, "elapsed_ms": elapsed})

    worker = WebWorker("WorkerThread-1", heavy_prime_factorization_worker)
    completion_flag = threading.Event()

    def handle_worker_message(result):
        log_event("MAIN_THREAD", Colors.CYAN, f"Worker returned result: {result}")
        completion_flag.set()

    worker.onmessage = handle_worker_message

    log_event("MAIN_THREAD", Colors.CYAN, "Offloading heavy CPU workload to Web Worker...")
    worker.post_message(294747177721)

    log_event("MAIN_THREAD", Colors.CYAN, "Main thread is completely NON-BLOCKED! Processing UI frames...")
    for frame in range(1, 4):
        log_event("MAIN_THREAD_UI", Colors.CYAN, f"Rendering UI Animation Frame #{frame}")
        time.sleep(0.04)

    completion_flag.wait(timeout=3.0)
    worker.terminate()
    print()


def demo_shared_memory_atomics():
    print(f"{Colors.BOLD}=== 3. SHAREDARRAYBUFFER & ATOMICS MUTEX BENCHMARK ==={Colors.RESET}")
    # Allocate a buffer of 1 byte (counter) shared across 4 worker threads
    sab = SharedArrayBuffer(1)
    sab.buffer[0] = 0
    num_workers = 4
    iterations_per_worker = 50

    log_event("SHARED_MEM", Colors.BLUE, f"Initialized SharedArrayBuffer[1] at index 0 = {sab.buffer[0]}")
    log_event("SHARED_MEM", Colors.BLUE, f"Spawning {num_workers} parallel workers. Target total increments: {num_workers * iterations_per_worker}")

    def atomic_worker(worker_id: int):
        for _ in range(iterations_per_worker):
            # Atomic add ensures no two threads interleave and overwrite values incorrectly
            Atomics.add(sab, 0, 1)
            time.sleep(0.001)

    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=atomic_worker, args=(i + 1,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    final_counter = Atomics.load(sab, 0)
    expected = num_workers * iterations_per_worker

    if final_counter == expected:
        status_color = Colors.GREEN
        status_text = "PASSED (Zero Race Conditions)"
    else:
        status_color = Colors.RED
        status_text = f"FAILED: Race condition detected! Expected {expected}, got {final_counter}"

    log_event("SHARED_MEM", status_color, f"Final Counter Value: {final_counter} -> {status_text}\n")


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    print(f"{Colors.BOLD}{Colors.CYAN}================================================================={Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  JAVASCRIPT CONCURRENCY MODEL & PARALLEL COMPUTING SIMULATOR    {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}================================================================={Colors.RESET}")
    
    demo_event_loop_priority()
    demo_worker_parallelism()
    demo_shared_memory_atomics()

    print(f"{Colors.BOLD}{Colors.GREEN}All lab simulations finished successfully.{Colors.RESET}")
#!/usr/bin/env python3
"""
BAB-06: Concurrency Models, Web Workers & Parallel Computing
Hands-on Technical Simulation of JavaScript Concurrency Architecture in Python 3.

Features Simulated:
1. JS Engine Event Loop (Call Stack, Web APIs, Microtask Queue vs Macrotask Queue)
2. Dedicated Web Workers (Isolated V8 contexts communicating via postMessage / structured clone)
3. Shared Memory & Atomics (SharedArrayBuffer simulation with race condition vs atomic synchronization)
"""

import sys
import time
import threading
import queue
from collections import deque
from enum import Enum
from typing import Callable, Any, Dict, List, Optional

# --- ANSI Color Palette ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


class TaskPriority(Enum):
    MICROTASK = 1  # Promise.then, queueMicrotask, process.nextTick
    MACROTASK = 2  # setTimeout, setInterval, setImmediate, I/O


class JSEventLoopSimulator:
    """
    Simulates the single-threaded V8 execution context with:
    - Synchronous Call Stack (LIFO)
    - Web APIs background container
    - Microtask Queue (FIFO - higher priority drain before next macrotask)
    - Macrotask Queue (FIFO - one per tick after draining microtasks)
    """

    def __init__(self):
        self.call_stack: List[str] = []
        self.microtask_queue: deque = deque()
        self.macrotask_queue: deque = deque()
        self.execution_log: List[str] = []

    def log(self, tag: str, message: str, color: str = WHITE) -> None:
        entry = f"{color}[{tag:^14}] {message}{RESET}"
        self.execution_log.append(entry)
        print(entry)

    def push_call_stack(self, frame_name: str) -> None:
        self.call_stack.append(frame_name)
        self.log("CALL STACK", f"-> Push: {BOLD}{frame_name}{RESET} (Depth: {len(self.call_stack)})", CYAN)

    def pop_call_stack(self) -> Optional[str]:
        if self.call_stack:
            frame = self.call_stack.pop()
            self.log("CALL STACK", f"<- Pop:  {frame} (Depth: {len(self.call_stack)})", DIM)
            return frame
        return None

    def queue_microtask(self, name: str, callback: Callable[[], None]) -> None:
        self.microtask_queue.append((name, callback))
        self.log("MICROTASK-Q", f"Enqueued microtask: {MAGENTA}{name}{RESET} (Promise/queueMicrotask)", MAGENTA)

    def queue_macrotask(self, name: str, callback: Callable[[], None]) -> None:
        self.macrotask_queue.append((name, callback))
        self.log("MACROTASK-Q", f"Enqueued macrotask: {YELLOW}{name}{RESET} (setTimeout/I/O)", YELLOW)

    def trigger_web_api_timer(self, name: str, delay_ms: int, callback: Callable[[], None]) -> None:
        self.log("WEB API", f"Handing off timer for {YELLOW}'{name}'{RESET} ({delay_ms}ms) to browser thread pool", BLUE)

        def timer_worker():
            time.sleep(delay_ms / 1000.0)
            self.queue_macrotask(name, callback)

        t = threading.Thread(target=timer_worker, daemon=True)
        t.start()

    def run_event_loop(self) -> None:
        """
        Executes ticks following the HTML5 Event Loop Specification:
        1. Drain synchronous Call Stack.
        2. Drain ALL microtasks until microtask queue is completely empty.
        3. Dequeue and execute exactly ONE macrotask.
        4. Repeat until all queues are empty.
        """
        print(f"\n{BOLD}{BG_BLUE} === STARTING EVENT LOOP TICK ENGINE === {RESET}\n")
        tick_count = 0

        while self.call_stack or self.microtask_queue or self.macrotask_queue:
            tick_count += 1
            self.log("LOOP ENGINE", f"--- Loop Iteration #{tick_count} ---", WHITE)

            # 1. Drain Microtasks thoroughly
            while self.microtask_queue:
                name, cb = self.microtask_queue.popleft()
                self.push_call_stack(f"microtask:{name}")
                cb()
                self.pop_call_stack()

            # 2. Pick ONE Macrotask if available
            if self.macrotask_queue:
                name, cb = self.macrotask_queue.popleft()
                self.push_call_stack(f"macrotask:{name}")
                cb()
                self.pop_call_stack()

                # Re-drain microtasks that might have been queued by this macrotask
                while self.microtask_queue:
                    m_name, m_cb = self.microtask_queue.popleft()
                    self.push_call_stack(f"microtask:{m_name}")
                    m_cb()
                    self.pop_call_stack()

            # Give brief yield for asynchronous Web API timers to complete if needed
            if not self.microtask_queue and not self.macrotask_queue and not self.call_stack:
                time.sleep(0.05)

        print(f"\n{BOLD}{GREEN}✔ Event Loop idle: All call stacks, microtasks, and macrotasks resolved.{RESET}\n")


class DedicatedWorkerSimulator:
    """
    Simulates a Web Worker (`new Worker('worker.js')`).
    - Separate thread & separate execution memory.
    - Inter-thread communication via postMessage (serialized copy).
    """

    def __init__(self, name: str, task_handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self.name = name
        self.inbox: queue.Queue = queue.Queue()
        self.outbox: queue.Queue = queue.Queue()
        self.task_handler = task_handler
        self.is_running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def _worker_loop(self):
        while self.is_running:
            try:
                msg = self.inbox.get(timeout=0.1)
                # Simulate Structured Clone serialization delay
                time.sleep(0.01)
                result = self.task_handler(msg)
                self.outbox.put(result)
                self.inbox.task_done()
            except queue.Empty:
                continue

    def post_message(self, data: Dict[str, Any]) -> None:
        self.inbox.put(data)

    def receive_message(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        try:
            return self.outbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def terminate(self) -> None:
        self.is_running = False
        self.thread.join(timeout=0.5)


class SharedMemoryAtomicsSimulator:
    """
    Simulates JavaScript SharedArrayBuffer and Atomics API.
    Demonstrates race conditions under parallel writes and resolution via Atomics.
    """

    def __init__(self, buffer_size: int = 1):
        self.raw_buffer: List[int] = [0] * buffer_size
        self._atomic_lock = threading.Lock()

    def non_atomic_increment(self, iterations: int) -> None:
        """Simulates raw unsynchronized read-modify-write on SharedArrayBuffer."""
        for _ in range(iterations):
            val = self.raw_buffer[0]
            time.sleep(0.000001)  # Context switch trigger
            self.raw_buffer[0] = val + 1

    def atomic_increment(self, iterations: int) -> None:
        """Simulates Atomics.add(typedArray, index, value)."""
        for _ in range(iterations):
            with self._atomic_lock:
                self.raw_buffer[0] += 1


# --- Interactive Scenarios ---

def scenario_event_loop_priority():
    print(f"\n{BOLD}{CYAN}=== SCENARIO 1: Event Loop Microtask vs Macrotask Priority ==={RESET}")
    print("Code Equivalent in JavaScript:")
    print(f"{DIM}console.log('Script Start');{RESET}")
    print(f"{DIM}setTimeout(() => console.log('setTimeout 0ms'), 0);{RESET}")
    print(f"{DIM}Promise.resolve().then(() => console.log('Promise 1'));{RESET}")
    print(f"{DIM}queueMicrotask(() => console.log('queueMicrotask'));{RESET}")
    print(f"{DIM}console.log('Script End');{RESET}\n")

    sim = JSEventLoopSimulator()

    # Synchronous Execution
    sim.push_call_stack("main()")
    sim.log("EXECUTION", "1. Synchronous: console.log('Script Start')", GREEN)

    # setTimeout (Macrotask)
    sim.queue_macrotask("setTimeout-0ms", lambda: sim.log("CALLBACK", "setTimeout callback executed", YELLOW))

    # Promise.then (Microtask)
    sim.queue_microtask("Promise-1", lambda: sim.log("CALLBACK", "Promise 1 callback executed", MAGENTA))

    # queueMicrotask (Microtask)
    sim.queue_microtask("queueMicrotask-1", lambda: sim.log("CALLBACK", "queueMicrotask callback executed", MAGENTA))

    sim.log("EXECUTION", "2. Synchronous: console.log('Script End')", GREEN)
    sim.pop_call_stack()

    # Run Loop
    sim.run_event_loop()


def scenario_web_worker():
    print(f"\n{BOLD}{CYAN}=== SCENARIO 2: Dedicated Web Worker & Off-Main-Thread Processing ==={RESET}")
    print("Offloading heavy CPU computation from Main UI Thread to Web Worker via structured clone message passing.\n")

    def heavy_math_worker(payload: Dict[str, Any]) -> Dict[str, Any]:
        num = payload.get("calculate_primes_up_to", 100)
        # Prime calculation
        primes = []
        for x in range(2, num):
            if all(x % d != 0 for d in range(2, int(x ** 0.5) + 1)):
                primes.append(x)
        return {"worker_id": payload.get("id"), "primes_found": len(primes), "largest_prime": primes[-1] if primes else None}

    worker = DedicatedWorkerSimulator("Worker-PrimeCalculator", heavy_math_worker)
    print(f"[{BOLD}MAIN THREAD{RESET}] Spawning Worker and posting compute payload...")
    worker.post_message({"id": "TASK_001", "calculate_primes_up_to": 15000})

    print(f"[{BOLD}MAIN THREAD{RESET}] Main UI remains responsive! (Simulating UI frame rendering...)")
    for frame in range(1, 4):
        print(f"  {DIM}[UI Render] Frame #{frame} rendered at 60 FPS...{RESET}")
        time.sleep(0.04)

    response = worker.receive_message()
    print(f"[{BOLD}{GREEN}MAIN THREAD{RESET}] onmessage received from Worker: {response}")
    worker.terminate()
    print(f"[{BOLD}MAIN THREAD{RESET}] Worker terminated successfully.\n")


def scenario_shared_array_buffer_atomics():
    print(f"\n{BOLD}{CYAN}=== SCENARIO 3: SharedArrayBuffer Race Condition vs Atomics.add ==={RESET}")
    iterations = 2000
    num_threads = 4
    expected_sum = iterations * num_threads

    print(f"Running parallel workers: {num_threads} threads × {iterations} increments.")
    print(f"Expected final count in SharedArrayBuffer: {BOLD}{expected_sum}{RESET}\n")

    # Part A: Unsynchronized (Race Condition)
    race_sim = SharedMemoryAtomicsSimulator()
    threads = [threading.Thread(target=race_sim.non_atomic_increment, args=(iterations,)) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    race_val = race_sim.raw_buffer[0]
    loss = expected_sum - race_val
    print(f"1. Without Atomics (Raw Memory Access):")
    print(f"   Actual Result: {RED}{race_val}{RESET} / {expected_sum} ({loss} updates lost due to race condition!)")

    # Part B: Synchronized with Atomics
    atomic_sim = SharedMemoryAtomicsSimulator()
    threads_atomic = [threading.Thread(target=atomic_sim.atomic_increment, args=(iterations,)) for _ in range(num_threads)]
    for t in threads_atomic:
        t.start()
    for t in threads_atomic:
        t.join()

    atomic_val = atomic_sim.raw_buffer[0]
    print(f"2. With Atomics (Atomics.add Simulation):")
    print(f"   Actual Result: {GREEN}{atomic_val}{RESET} / {expected_sum} (100% thread-safe atomic synchronization!)\n")


def run_all_checks() -> bool:
    print(f"{BOLD}{MAGENTA}Running self-diagnostic integration tests...{RESET}")
    # 1. Event Loop Test
    sim = JSEventLoopSimulator()
    test_order = []
    sim.queue_macrotask("macro", lambda: test_order.append("macro"))
    sim.queue_microtask("micro", lambda: test_order.append("micro"))
    sim.run_event_loop()
    assert test_order == ["micro", "macro"], f"Order mismatch: {test_order}"

    # 2. Worker Test
    w = DedicatedWorkerSimulator("test", lambda p: {"result": p["v"] * 2})
    w.post_message({"v": 21})
    res = w.receive_message()
    assert res and res["result"] == 42, "Worker returned wrong result"
    w.terminate()

    # 3. Atomics Test
    atm = SharedMemoryAtomicsSimulator()
    t1 = threading.Thread(target=atm.atomic_increment, args=(100,))
    t2 = threading.Thread(target=atm.atomic_increment, args=(100,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert atm.raw_buffer[0] == 200, "Atomic increment failed"

    print(f"{BOLD}{GREEN}✔ All internal test assertions PASSED!{RESET}\n")
    return True


def display_menu():
    print(f"{BOLD}╔═══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║   JAVASCRIPT CONCURRENCY & PARALLEL COMPUTING SIMULATOR (CLI)         ║{RESET}")
    print(f"{BOLD}╚═══════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f" [1] Simulasikan Event Loop Priority (Microtask vs Macrotask)")
    print(f" [2] Simulasikan Dedicated Web Worker (Message Passing & Off-Main-Thread)")
    print(f" [3] Simulasikan SharedArrayBuffer & Atomics (Race Condition vs Atomics.add)")
    print(f" [4] Jalankan Semua Skenario Berurutan (Full Test Suite)")
    print(f" [5] Keluar")
    print("-------------------------------------------------------------------------")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_all_checks()
        scenario_event_loop_priority()
        scenario_web_worker()
        scenario_shared_array_buffer_atomics()
        return

    # If run in non-interactive environment (CI/batch), execute full test suite
    if not sys.stdin.isatty():
        run_all_checks()
        scenario_event_loop_priority()
        scenario_web_worker()
        scenario_shared_array_buffer_atomics()
        return

    while True:
        display_menu()
        choice = input(f"{BOLD}Pilih opsi (1-5): {RESET}").strip()
        if choice == "1":
            scenario_event_loop_priority()
        elif choice == "2":
            scenario_web_worker()
        elif choice == "3":
            scenario_shared_array_buffer_atomics()
        elif choice == "4":
            run_all_checks()
            scenario_event_loop_priority()
            scenario_web_worker()
            scenario_shared_array_buffer_atomics()
        elif choice == "5" or choice.lower() == "q":
            print(f"{GREEN}Keluar dari simulator. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1-5.{RESET}\n")


if __name__ == "__main__":
    main()

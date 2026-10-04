#!/usr/bin/env python3
"""
Lab Hands-on: Ruby Concurrency, Parallelism, & Multi-Threading Deep Dive
Topic: Ruby Architecture Simulation (MRI GVL, Fibers, and Ruby 3 Ractors)

This script simulates the internal concurrency models of Ruby:
1. Matz's Ruby Interpreter (MRI) Global VM Lock (GVL) dynamics.
2. Cooperative Fiber & Fiber Scheduler execution (Ruby 3.0 lightweight concurrency).
3. Ractor-based shared-nothing actor model enabling multi-core parallelism.
"""

import time
import threading
import queue
import hashlib
from typing import Callable, Any, List, Dict

# --- ANSI Terminal Color Palette ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[96m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED    = "\033[91m"
CLR_MAG    = "\033[95m"
CLR_DIM    = "\033[2m"


def print_banner(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [RUBY RUNTIME LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")


# ============================================================================
# 1. MRI GVL (Global VM Lock) Engine Simulation
# ============================================================================
class RubyMRIRuntime:
    """
    Simulates MRI Ruby's Thread execution pipeline constrained by the GVL.
    In MRI Ruby, Native Threads exist, but only one thread can execute Ruby VM
    bytecode at a time due to the GVL. The GVL is released during blocking I/O.
    """
    def __init__(self):
        self._gvl = threading.Lock()

    def run_cpu_work(self, thread_id: int, iterations: int) -> float:
        """
        Simulates CPU-bound Ruby computation.
        Requires acquisition and retention of GVL during computation steps.
        """
        start = time.perf_counter()
        with self._gvl:
            # Thread executes bytecode strictly serialized by GVL
            state = f"seed-{thread_id}".encode()
            for _ in range(iterations):
                state = hashlib.sha256(state).digest()
        elapsed = time.perf_counter() - start
        return elapsed

    def run_io_work(self, thread_id: int, io_duration: float) -> float:
        """
        Simulates I/O bound Ruby operation.
        MRI releases the GVL before invoking underlying OS blocking system calls.
        """
        start = time.perf_counter()
        # 1. Thread prepares I/O inside GVL
        with self._gvl:
            pass  # Prep work done in VM

        # 2. GVL RELEASED during blocking I/O operation
        time.sleep(io_duration)

        # 3. Thread re-acquires GVL to handle result in VM
        with self._gvl:
            pass

        return time.perf_counter() - start


# ============================================================================
# 2. Fiber & Fiber::Scheduler Simulator (Cooperative Multitasking)
# ============================================================================
class FiberScheduler:
    """
    Simulates Ruby 3.0 Fiber Scheduler interface.
    Fibers represent user-space cooperative execution contexts with
    extremely low memory footprints (~4KB overhead vs ~1MB native threads).
    """
    def __init__(self):
        self._ready_queue: queue.Queue = queue.Queue()
        self._sleeping: List[Dict[str, Any]] = []

    def schedule(self, fiber_gen):
        """Pushes a fiber into the execution queue."""
        self._ready_queue.put(fiber_gen)

    def fiber_sleep(self, duration: float):
        """Cooperative yield: marks current fiber as waiting."""
        wake_at = time.perf_counter() + duration
        return ("sleep", wake_at)

    def run_loop(self):
        """Event loop resuming yielded fibers when events/timeouts clear."""
        active_fibers = self._ready_queue.qsize() + len(self._sleeping)
        while active_fibers > 0:
            now = time.perf_counter()

            # Check sleeping fibers
            for item in self._sleeping[:]:
                if now >= item["wake_at"]:
                    self._ready_queue.put(item["fiber"])
                    self._sleeping.remove(item)

            # Process ready fibers
            try:
                fiber = self._ready_queue.get_nowait()
                try:
                    action, payload = next(fiber)
                    if action == "sleep":
                        self._sleeping.append({"fiber": fiber, "wake_at": payload})
                except StopIteration:
                    pass  # Fiber completed
            except queue.Empty:
                time.sleep(0.002)

            active_fibers = self._ready_queue.qsize() + len(self._sleeping)


# ============================================================================
# 3. Ruby 3 Ractor Engine (Actor-model true parallelism)
# ============================================================================
class Ractor:
    """
    Simulates Ruby 3 Ractors (Ruby's Actor Model).
    Ractors have separate VM locks, enabling true multi-core parallelism.
    Data is isolated: objects must be deep-copied or moved (frozen).
    """
    def __init__(self, target: Callable[['Ractor'], None], name: str = "Ractor"):
        self.name = name
        self._mailbox: queue.Queue = queue.Queue()
        self._outbox: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, args=(target,), daemon=True)
        self._worker.start()

    def _run(self, target: Callable[['Ractor'], None]):
        target(self)

    def send(self, message: Any) -> None:
        """Ractor.send: Pushes message to Ractor inbox."""
        self._mailbox.put(message)

    def receive(self) -> Any:
        """Ractor.receive: Blocking call on inward mailbox."""
        return self._mailbox.get()

    def yield_result(self, value: Any) -> None:
        """Ractor.yield: Yields result to consumers."""
        self._outbox.put(value)

    def take(self) -> Any:
        """Ractor#take: Consumes yielded values from outside."""
        return self._outbox.get()


# ============================================================================
# Lab Experiments and Instrumentation
# ============================================================================
def experiment_mri_gvl_bottleneck():
    print_banner("1. MRI Global VM Lock (GVL) Serialization Benchmark")
    mri = RubyMRIRuntime()
    iterations = 350000

    print(f"{CLR_DIM}Testing 4 concurrent CPU-bound tasks under GVL (serialized execution)...{CLR_RESET}")
    start_cpu = time.perf_counter()
    threads = []
    for tid in range(4):
        t = threading.Thread(target=mri.run_cpu_work, args=(tid, iterations))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    cpu_duration = time.perf_counter() - start_cpu
    print(f"[{CLR_RED}GVL CPU-BOUND{CLR_RESET}] Total wall time (4 threads): {CLR_BOLD}{cpu_duration:.4f}s{CLR_RESET}")

    print(f"\n{CLR_DIM}Testing 4 concurrent I/O-bound tasks under GVL (lock released during I/O)...{CLR_RESET}")
    start_io = time.perf_counter()
    threads.clear()
    for tid in range(4):
        t = threading.Thread(target=mri.run_io_work, args=(tid, 0.15))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    io_duration = time.perf_counter() - start_io
    print(f"[{CLR_GREEN}GVL I/O-BOUND{CLR_RESET}] Total wall time (4 threads, 150ms sleep each): {CLR_BOLD}{io_duration:.4f}s{CLR_RESET}")
    print(f"{CLR_YELLOW}Insight:{CLR_RESET} MRI Threads do not scale CPU workloads due to GVL, but provide true concurrency for I/O.")


def fiber_worker(scheduler: FiberScheduler, name: str, steps: int, delay: float):
    """Coroutines simulating cooperative Fiber execution without thread stacks."""
    for i in range(1, steps + 1):
        yield scheduler.fiber_sleep(delay)
        print(f"  {CLR_MAG}↳ Fiber [{name}]{CLR_RESET} resumed step {i}/{steps}")


def experiment_fiber_cooperative():
    print_banner("2. Ruby 3.0 Fibers & Non-Blocking Cooperative Scheduler")
    scheduler = FiberScheduler()

    print(f"{CLR_DIM}Spawning lightweight Fibers interleaved cooperatively on a single native thread...{CLR_RESET}")
    scheduler.schedule(fiber_worker(scheduler, "Worker-A", 3, 0.05))
    scheduler.schedule(fiber_worker(scheduler, "Worker-B", 3, 0.03))
    scheduler.schedule(fiber_worker(scheduler, "Worker-C", 3, 0.02))

    start = time.perf_counter()
    scheduler.run_loop()
    elapsed = time.perf_counter() - start
    print(f"[{CLR_GREEN}FIBER SCHEDULER{CLR_RESET}] Completed execution in {CLR_BOLD}{elapsed:.4f}s{CLR_RESET} using single-thread yielding.")


def ractor_worker_routine(r: Ractor):
    """Logic executed by isolated Ractor worker bypassing global locks."""
    while True:
        task = r.receive()
        if task == "STOP":
            break
        # Isolated CPU-bound computation
        state = f"ractor-{task}".encode()
        for _ in range(350000):
            state = hashlib.sha256(state).digest()
        r.yield_result((task, hashlib.md5(state).hexdigest()[:8]))


def experiment_ractor_parallelism():
    print_banner("3. Ruby 3 Ractor Model (True Multi-Core Parallelism)")
    print(f"{CLR_DIM}Initializing Ractor pool with message-passing memory isolation...{CLR_RESET}")

    num_ractors = 4
    ractors = [Ractor(target=ractor_worker_routine, name=f"Ractor-{i}") for i in range(num_ractors)]

    start = time.perf_counter()
    tasks = [101, 102, 103, 104]

    # Dispatch tasks concurrently across Ractors
    for i, t in enumerate(tasks):
        ractors[i].send(t)

    # Collect isolated results
    for i in range(num_ractors):
        task_id, digest = ractors[i].take()
        print(f"  {CLR_CYAN}✔ [Ractor-{i}]{CLR_RESET} Task {task_id} computed hash: {CLR_BOLD}{digest}{CLR_RESET}")
        ractors[i].send("STOP")

    duration = time.perf_counter() - start
    print(f"[{CLR_GREEN}RACTOR PARALLEL{CLR_RESET}] Wall clock time for 4 CPU jobs: {CLR_BOLD}{duration:.4f}s{CLR_RESET}")
    print(f"{CLR_YELLOW}Verification:{CLR_RESET} Ractors eliminate GVL constraints by ensuring shared-nothing isolation.")


def main():
    print(f"{CLR_BOLD}{CLR_MAG}=== RUBY CONCURRENCY INTERNALS BENCHMARK LAB ==={CLR_RESET}")
    print("Demonstrating MRI GVL Bottlenecks, Fibers, and Ruby 3 Ractors.")
    
    experiment_mri_gvl_bottleneck()
    experiment_fiber_cooperative()
    experiment_ractor_parallelism()
    
    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ All Ruby concurrency architecture simulations completed successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
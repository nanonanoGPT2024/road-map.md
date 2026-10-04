#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Coroutines Core Internals Simulation
Topic: Kotlin (02-Programming-Languages)
Chapter: 05 (Asynchronous Programming: Coroutines Core) - Modul 02 Deep Dive

Simulates the foundational mechanics of Kotlin Coroutines in pure Python:
1. Job State Machine (NEW, ACTIVE, CANCELLING, CANCELLED, COMPLETED)
2. Structured Concurrency (Hierarchical Job trees, Parent-Child cancellation)
3. Dispatchers & Thread Confinement (Dispatchers.Default simulated via ThreadPool)
4. Builders: launch (Job) and async/await (Deferred<T>)
5. Cooperative Cancellation via yield/cancellation checks
"""

import sys
import time
import threading
import queue
from enum import Enum, auto
from typing import Callable, Any, Optional, List

# --- ANSI Color Utilities for Terminal Diagnostics ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def log(tag: str, msg: str, color: str = Colors.RESET):
    thread_name = threading.current_thread().name
    print(f"{Colors.DIM}[{time.strftime('%H:%M:%S.%SS')}] [{thread_name:<16}]{Colors.RESET} {color}[{tag:<12}] {msg}{Colors.RESET}")

# --- Core Kotlin Coroutine Primitives ---

class JobState(Enum):
    ACTIVE = auto()
    CANCELLING = auto()
    CANCELLED = auto()
    COMPLETING = auto()
    COMPLETED = auto()

class CancellationException(Exception):
    """Thrown to cooperatively terminate coroutine execution."""
    pass

class Job:
    """
    Models Kotlin's Job life-cycle, hierarchy, and cancellation propagation.
    Parent jobs track active children; cancelling a parent cancels all descendants.
    """
    def __init__(self, name: str, parent: Optional['Job'] = None):
        self.name = name
        self.parent = parent
        self.children: List['Job'] = []
        self._state = JobState.ACTIVE
        self._lock = threading.Lock()
        self._completion_event = threading.Event()
        self.exception: Optional[Exception] = None

        if parent:
            parent._attach_child(self)

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._state == JobState.ACTIVE

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._state in (JobState.CANCELLING, JobState.CANCELLED)

    def _attach_child(self, child: 'Job'):
        with self._lock:
            if self._state != JobState.ACTIVE:
                child.cancel(CancellationException("Parent is already inactive"))
            else:
                self.children.append(child)

    def cancel(self, cause: Optional[Exception] = None):
        """Cancels this job and recursively cancels all active children."""
        with self._lock:
            if self._state in (JobState.CANCELLING, JobState.CANCELLED, JobState.COMPLETED):
                return
            self._state = JobState.CANCELLING
            self.exception = cause or CancellationException(f"Job '{self.name}' was cancelled")
            log("JOB_CANCEL", f"Cancelling '{self.name}' | Reason: {self.exception}", Colors.YELLOW)

        # Propagate downwards to all children
        for child in list(self.children):
            child.cancel(self.exception)

        with self._lock:
            self._state = JobState.CANCELLED
            self._completion_event.set()

    def complete(self):
        """Transitions job to COMPLETED once all child jobs finish."""
        # Wait for all children to complete (Structured Concurrency rule)
        for child in list(self.children):
            child.join()

        with self._lock:
            if self._state == JobState.ACTIVE:
                self._state = JobState.COMPLETED
                self._completion_event.set()
                log("JOB_COMPLETE", f"Job '{self.name}' reached COMPLETED state", Colors.GREEN)

    def join(self, timeout: Optional[float] = None) -> bool:
        """Blocks caller until this job finishes or is cancelled."""
        return self._completion_event.wait(timeout)

    def check_active(self):
        """Cooperative cancellation checkpoint (equivalent to Kotlin's ensureActive())."""
        if not self.is_active:
            raise CancellationException(f"Coroutine '{self.name}' cooperative abort triggered")

class Deferred(Job):
    """
    Models Kotlin's Deferred<T>, extending Job to return a computed value via await().
    """
    def __init__(self, name: str, parent: Optional[Job] = None):
        super().__init__(name, parent)
        self._result: Any = None
        self._has_result = False

    def complete_with_value(self, value: Any):
        with self._lock:
            self._result = value
            self._has_result = True
        self.complete()

    def complete_with_exception(self, exc: Exception):
        with self._lock:
            self.exception = exc
            self._state = JobState.CANCELLED
            self._completion_event.set()
        if self.parent and self.parent.is_active:
            # Failure propagation up to parent
            self.parent.cancel(exc)

    def await_result(self, timeout: Optional[float] = None) -> Any:
        """Suspends/blocks until result is ready or raises failure/cancellation."""
        self.join(timeout)
        with self._lock:
            if self.exception:
                raise self.exception
            if self._has_result:
                return self._result
            raise RuntimeError(f"Deferred '{self.name}' completed without a result or timed out")

# --- Dispatcher & Scope Infrastructure ---

class CoroutineDispatcher:
    """Simulates Dispatchers.Default using an internal thread worker pool."""
    def __init__(self, pool_size: int = 4):
        self.work_queue = queue.Queue()
        self.workers = []
        self.running = True
        for i in range(pool_size):
            t = threading.Thread(target=self._worker_loop, name=f"DefaultPool-w{i+1}", daemon=True)
            t.start()
            self.workers.append(t)

    def dispatch(self, runnable: Callable):
        if self.running:
            self.work_queue.put(runnable)

    def _worker_loop(self):
        while self.running:
            try:
                task = self.work_queue.get(timeout=0.2)
                task()
                self.work_queue.task_done()
            except queue.Empty:
                continue

    def shutdown(self):
        self.running = False

# Global Dispatchers
Dispatchers_Default = CoroutineDispatcher(pool_size=3)

class CoroutineScope:
    """Encapsulates context (Root Job + Dispatcher) for Structured Concurrency."""
    def __init__(self, name: str, dispatcher: CoroutineDispatcher = Dispatchers_Default):
        self.dispatcher = dispatcher
        self.coroutine_context_job = Job(f"ScopeRoot:{name}")

    def launch(self, block: Callable[['Job'], None], name: str = "launch") -> Job:
        """Spawns a fire-and-forget coroutine child job."""
        job = Job(name, parent=self.coroutine_context_job)

        def runner():
            log("COROUTINE", f"Started '{name}'", Colors.CYAN)
            try:
                job.check_active()
                block(job)
                job.complete()
            except CancellationException as ce:
                log("SUSPEND/CANCEL", f"Coroutine '{name}' gracefully cancelled: {ce}", Colors.YELLOW)
            except Exception as ex:
                log("FAILURE", f"Coroutine '{name}' crashed: {ex}", Colors.RED)
                job.cancel(ex)
                if self.coroutine_context_job.is_active:
                    self.coroutine_context_job.cancel(ex)

        self.dispatcher.dispatch(runner)
        return job

    def async_builder(self, block: Callable[['Deferred'], Any], name: str = "async") -> Deferred:
        """Spawns an asynchronous coroutine returning a Deferred<T>."""
        deferred = Deferred(name, parent=self.coroutine_context_job)

        def runner():
            log("DEFERRED", f"Started compute '{name}'", Colors.BLUE)
            try:
                deferred.check_active()
                result = block(deferred)
                deferred.complete_with_value(result)
            except CancellationException as ce:
                deferred.cancel(ce)
            except Exception as ex:
                log("FAILURE", f"Deferred '{name}' exception caught: {ex}", Colors.RED)
                deferred.complete_with_exception(ex)

        self.dispatcher.dispatch(runner)
        return deferred

def delay(duration_sec: float, job: Optional[Job] = None):
    """
    Simulates Kotlin's non-blocking delay() by breaking sleep into intervals
    and checking for cooperative cancellation at suspension boundaries.
    """
    step = 0.05
    elapsed = 0.0
    while elapsed < duration_sec:
        if job:
            job.check_active()
        time.sleep(min(step, duration_sec - elapsed))
        elapsed += step
    if job:
        job.check_active()

# --- Execution Demonstrations ---

def test_async_await_pattern():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== TEST 1: Structured Concurrency with async/await ==={Colors.RESET}")
    scope = CoroutineScope("ParallelDataLoader")

    def fetch_user_data(deferred: Deferred):
        delay(0.2, deferred)
        return {"userId": 1042, "role": "Engineer"}

    def fetch_account_balance(deferred: Deferred):
        delay(0.3, deferred)
        return {"balance": 15420.50, "currency": "USD"}

    d1 = scope.async_builder(fetch_user_data, name="FetchUser")
    d2 = scope.async_builder(fetch_account_balance, name="FetchBalance")

    # Await results concurrently computed on worker pool
    user = d1.await_result()
    balance = d2.await_result()

    log("RESULT", f"Combined Payload: User={user['userId']} Balance={balance['balance']} {balance['currency']}", Colors.GREEN)
    scope.coroutine_context_job.complete()

def test_cooperative_cancellation():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== TEST 2: Cooperative Cancellation via delay/isActive ==={Colors.RESET}")
    scope = CoroutineScope("StreamProcessor")

    def telemetry_loop(job: Job):
        iteration = 0
        while True:
            # Suspension point check
            job.check_active()
            iteration += 1
            log("STREAM", f"Emitted telemetry tick #{iteration}", Colors.DIM)
            delay(0.08, job)

    worker_job = scope.launch(telemetry_loop, name="TelemetryWorker")
    
    # Let it run for 200ms then cancel
    time.sleep(0.25)
    log("MAIN", "Triggering worker_job.cancel()...", Colors.YELLOW)
    worker_job.cancel()
    worker_job.join()
    log("MAIN", f"Worker State after join: {worker_job._state.name}", Colors.GREEN)
    scope.coroutine_context_job.complete()

def test_parent_child_failure_propagation():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== TEST 3: Structural Failure Propagation (Crash Child 2) ==={Colors.RESET}")
    scope = CoroutineScope("BatchPipeline")

    def stable_worker(job: Job):
        for i in range(5):
            delay(0.1, job)
            log("STABLE_WORKER", f"Step {i+1}/5 completed", Colors.BLUE)
        return "OK"

    def crashing_worker(job: Job):
        delay(0.15, job)
        raise ValueError("Fatal payload corruption in pipeline worker!")

    scope.launch(stable_worker, name="Worker-A")
    scope.launch(crashing_worker, name="Worker-B-Faulty")

    # The failure in Worker-B must automatically cancel ScopeRoot and Worker-A
    scope.coroutine_context_job.join(timeout=1.0)
    log("SUPERVISION", f"Parent scope state: {scope.coroutine_context_job._state.name}", Colors.YELLOW)
    log("SUPERVISION", f"Parent error: {scope.coroutine_context_job.exception}", Colors.RED)

def main():
    print(f"{Colors.BOLD}{Colors.GREEN}==============================================================")
    print("  KOTLIN ASYNCHRONOUS PROGRAMMING: COROUTINES CORE RUNTIME LAB")
    print(f"=============================================================={Colors.RESET}")
    
    try:
        test_async_await_pattern()
        test_cooperative_cancellation()
        test_parent_child_failure_propagation()
    finally:
        Dispatchers_Default.shutdown()
        print(f"\n{Colors.BOLD}{Colors.GREEN}[✓] Coroutine Runtime teardown clean. All tasks finalized.{Colors.RESET}")

if __name__ == "__main__":
    main()

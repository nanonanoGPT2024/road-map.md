#!/usr/bin/env python3
"""
Lab: Deep Dive into Modern Android Internals - Kotlin Coroutines & Flow Engine
Simulates:
  1. CPS (Continuation Passing Style) & Structured Concurrency (Job Tree & Cancellation)
  2. Dispatchers (Main Looper vs IO ThreadPool)
  3. Cold Flow execution engine with operators (map, filter)
  4. Hot StateFlow with conflation and replay mechanics
"""

import sys
import time
import threading
import queue
from typing import Callable, Any, List, Optional
from enum import Enum

# ANSI Color Codes for terminal UI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def log(tag: str, msg: str, color: str = RESET):
    t_name = threading.current_thread().name
    print(f"{color}[{t_name}] [{tag}] {msg}{RESET}")


class JobState(Enum):
    ACTIVE = "ACTIVE"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Job:
    """Simulates Kotlin Coroutine Job with Parent-Child Cancellation Hierarchy."""
    def __init__(self, parent: Optional['Job'] = None):
        self.state = JobState.ACTIVE
        self.parent = parent
        self.children: List['Job'] = []
        self._lock = threading.Lock()
        if parent:
            parent.add_child(self)

    def add_child(self, child: 'Job'):
        with self._lock:
            if self.state in (JobState.CANCELLING, JobState.CANCELLED):
                child.cancel()
            else:
                self.children.append(child)

    def cancel(self):
        """Structured Concurrency: Cancelling a parent cancels all its children."""
        with self._lock:
            if self.state in (JobState.CANCELLED, JobState.CANCELLING):
                return
            self.state = JobState.CANCELLING
            log("Job", f"Job {id(self)} marked CANCELLING. Cascading to {len(self.children)} children.", RED)
            for child in self.children:
                child.cancel()
            self.state = JobState.CANCELLED

    def complete(self):
        with self._lock:
            if self.state == JobState.ACTIVE:
                self.state = JobState.COMPLETED

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self.state == JobState.ACTIVE


class Dispatchers:
    """Simulates Android Coroutine Dispatchers (Main Looper vs IO Worker Pool)."""
    class _MainDispatcher:
        def __init__(self):
            self.queue = queue.Queue()
            self.running = True
            self.thread = threading.Thread(target=self._loop, name="Android-MainThread", daemon=True)
            self.thread.start()

        def _loop(self):
            while self.running:
                try:
                    task = self.queue.get(timeout=0.1)
                    task()
                    self.queue.task_done()
                except queue.Empty:
                    continue

        def dispatch(self, block: Callable[[], None]):
            self.queue.put(block)

    class _IODispatcher:
        def __init__(self, pool_size=4):
            self.pool_size = pool_size
            self.queue = queue.Queue()
            self.workers = []
            for i in range(pool_size):
                t = threading.Thread(target=self._worker, name=f"DefaultDispatcher-worker-{i+1}", daemon=True)
                t.start()
                self.workers.append(t)

        def _worker(self):
            while True:
                task = self.queue.get()
                if task is None:
                    break
                task()
                self.queue.task_done()

        def dispatch(self, block: Callable[[], None]):
            self.queue.put(block)

    Main = _MainDispatcher()
    IO = _IODispatcher()


class Flow:
    """Simulates Kotlin Cold Flow: declarative, lazy, emits on collector demand."""
    def __init__(self, block: Callable[['FlowCollector'], None]):
        self._block = block

    def collect(self, collector_fn: Callable[[Any], None], job: Optional[Job] = None):
        c = FlowCollector(collector_fn, job)
        self._block(c)

    def map(self, transform: Callable[[Any], Any]) -> 'Flow':
        def downstream_block(collector: 'FlowCollector'):
            def intercept(value):
                transformed = transform(value)
                collector.emit(transformed)
            self.collect(intercept, collector.job)
        return Flow(downstream_block)

    def filter(self, predicate: Callable[[Any], bool]) -> 'Flow':
        def downstream_block(collector: 'FlowCollector'):
            def intercept(value):
                if predicate(value):
                    collector.emit(value)
            self.collect(intercept, collector.job)
        return Flow(downstream_block)


class FlowCollector:
    def __init__(self, collector_fn: Callable[[Any], None], job: Optional[Job] = None):
        self._collector_fn = collector_fn
        self.job = job

    def emit(self, value: Any):
        if self.job and not self.job.is_active:
            raise InterruptedError("Flow emission cancelled by Job cancellation.")
        self._collector_fn(value)


class StateFlow:
    """
    Simulates Kotlin StateFlow: Hot stream, state-holder, thread-safe,
    reflates last value to new collectors, conflates intermediate updates.
    """
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._lock = threading.Lock()
        self._subscribers: List[queue.Queue] = []

    @property
    def value(self) -> Any:
        with self._lock:
            return self._value

    @value.setter
    def value(self, new_value: Any):
        with self._lock:
            self._value = new_value
            # Conflate and broadcast to all active subscribers
            for sub in self._subscribers:
                # Conflation: if subscriber is slow, drop outdated pending values
                while not sub.empty():
                    try:
                        sub.get_nowait()
                    except queue.Empty:
                        break
                sub.put(new_value)

    def collect(self, collector_fn: Callable[[Any], None], job: Job):
        sub_queue = queue.Queue(maxsize=1)
        with self._lock:
            # Replay cache: Immediately emit current state
            sub_queue.put(self._value)
            self._subscribers.append(sub_queue)

        try:
            while job.is_active:
                try:
                    val = sub_queue.get(timeout=0.1)
                    collector_fn(val)
                except queue.Empty:
                    continue
        finally:
            with self._lock:
                if sub_queue in self._subscribers:
                    self._subscribers.remove(sub_queue)


def run_lab():
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}  LAB: SIMULATING KOTLIN COROUTINES & FLOW ARCHITECTURE IN PYTHON    {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}\n")

    # 1. Dispatchers & Thread Hopping
    print(f"{BOLD}{CYAN}--- Step 1: Thread Hopping (withContext Dispatcher simulation) ---{RESET}")
    parent_job = Job()
    
    def simulate_ui_operation():
        log("UI", "Rendering View on Android Main Looper...", GREEN)
        
        # Switch to IO Coroutine Context
        def io_task():
            child_job = Job(parent=parent_job)
            log("IO", "Fetching network payload (Retrofit simulation)...", YELLOW)
            time.sleep(0.3)
            data = {"id": 101, "status": "200_OK", "payload": "UserPreferences"}
            log("IO", f"Fetched: {data}. Switching back to Main Looper...", YELLOW)
            child_job.complete()
            
            # Switch back to Main
            Dispatchers.Main.dispatch(lambda: log("UI", f"MainThread updated UI with: {data['payload']}", GREEN))

        Dispatchers.IO.dispatch(io_task)

    Dispatchers.Main.dispatch(simulate_ui_operation)
    time.sleep(0.6)

    # 2. Cold Flow Mechanics with Operators
    print(f"\n{BOLD}{CYAN}--- Step 2: Cold Flow Declaration, Pipelines, and Demand-Driven Exec ---{RESET}")
    
    def sensor_data_flow() -> Flow:
        def flow_builder(collector: FlowCollector):
            for i in range(1, 6):
                time.sleep(0.1)
                log("SensorFlow", f"Producing raw hardware sample: {i}", CYAN)
                collector.emit(i)
        return Flow(flow_builder)

    pipeline = sensor_data_flow() \
        .filter(lambda x: x % 2 != 0) \
        .map(lambda x: f"Processed_Metric_#{x * 10}")

    log("FlowObserver", "Cold Flow defined. No emissions happen until collect() is triggered!", MAGENTA)
    time.sleep(0.2)
    log("FlowObserver", "Calling collect() now...", MAGENTA)
    
    collector_job = Job(parent=parent_job)
    pipeline.collect(lambda emitted: log("UI_Collector", f"Received: {emitted}", GREEN), job=collector_job)

    # 3. Hot StateFlow, Replay & Conflation Mechanism
    print(f"\n{BOLD}{CYAN}--- Step 3: Hot StateFlow Conflation & Replay Semantics ---{RESET}")
    ui_state = StateFlow(initial_value="UI_STATE: IDLE")
    vm_job = Job(parent=parent_job)

    # Start observer on a simulated background UI Lifecycle collector
    def start_ui_collection():
        log("UI_Observer", f"Subscribing to StateFlow. Initial read: {ui_state.value}", GREEN)
        ui_state.collect(lambda s: log("UI_Observer", f"Observed State: {s}", GREEN), job=vm_job)

    observer_thread = threading.Thread(target=start_ui_collection, name="UI-Collector-Thread", daemon=True)
    observer_thread.start()

    time.sleep(0.2)
    log("ViewModel", "Rapidly updating UI state (Emulating fast business events)...", YELLOW)
    # Fast mutations should be conflated if observer is busy
    for state_id in ["LOADING", "SUCCESS_CHUNK_1", "SUCCESS_CHUNK_2", "FINAL_RENDER_READY"]:
        ui_state.value = f"UI_STATE: {state_id}"
        time.sleep(0.05)

    time.sleep(0.3)

    # 4. Structured Concurrency & Cascading Cancellation
    print(f"\n{BOLD}{CYAN}--- Step 4: Structured Concurrency & Cascade Cancellation ---{RESET}")
    log("Lifecycle", "Android Activity/Fragment destroyed -> ViewModelScope cancelled!", RED)
    parent_job.cancel()
    time.sleep(0.2)

    log("Diagnostics", f"Parent Job status: {parent_job.state.value}", RED)
    log("Diagnostics", f"Collector Job active status: {vm_job.is_active}", RED)
    
    print(f"\n{BOLD}{GREEN}✔ All Coroutine & Flow internal patterns successfully simulated.{RESET}")


if __name__ == "__main__":
    run_lab()
    time.sleep(0.1)
    sys.exit(0)
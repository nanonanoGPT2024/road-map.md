#!/usr/bin/env python3
"""
Lab Hands-on: C# Asynchronous, Concurrency & Multithreading Internals
Focus: CLR Work-Stealing ThreadPool & Async State Machine (IAsyncStateMachine) Lowering

This lab simulates:
1. The .NET CLR ThreadPool architecture:
   - Global Injection Queue (FIFO) for thread-external work (e.g., ThreadPool.QueueUserWorkItem).
   - Local Work-Stealing Queues (LIFO for cache locality on owner, FIFO for peer work-stealing).
2. The Roslyn Compiler Lowering of `async` / `await`:
   - State machine generation (`IAsyncStateMachine` implementation).
   - `MoveNext()` dispatching, state transitions (-1, 0, 1, -2), and continuation wiring.
   - Context switches across worker threads during awaiter resumptions.
"""

import sys
import time
import random
import threading
from enum import Enum, auto
from collections import deque
from typing import Callable, Any, Optional, List, Dict

# --- ANSI Formatting Constants ---
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    GRAY    = "\033[90m"

# Thread-local storage to identify current worker thread
thread_context = threading.local()

# --- Section 1: Task and State Management ---

class TaskState(Enum):
    CREATED   = auto()
    RUNNING   = auto()
    COMPLETED = auto()
    FAULTED   = auto()

class Task:
    """
    Simulates System.Threading.Tasks.Task<T>.
    Encapsulates completion state, result, and continuation callbacks.
    """
    _id_counter = 0
    _counter_lock = threading.Lock()

    def __init__(self, name: str = "Task"):
        with Task._counter_lock:
            Task._id_counter += 1
            self.task_id = Task._id_counter
        
        self.name = f"{name}#{self.task_id}"
        self.state = TaskState.CREATED
        self.result: Any = None
        self.exception: Optional[Exception] = None
        self._continuations: List[Callable[['Task'], None]] = []
        self._lock = threading.Lock()

    @property
    def is_completed(self) -> bool:
        with self._lock:
            return self.state in (TaskState.COMPLETED, TaskState.FAULTED)

    def set_result(self, result: Any) -> None:
        """Transitions task to COMPLETED and fires registered continuations."""
        continuations_to_fire = []
        with self._lock:
            if self.state in (TaskState.COMPLETED, TaskState.FAULTED):
                raise RuntimeError(f"Task {self.task_id} already completed.")
            self.result = result
            self.state = TaskState.COMPLETED
            continuations_to_fire = list(self._continuations)
            self._continuations.clear()

        # Fire continuations outside lock to avoid deadlocks
        for callback in continuations_to_fire:
            callback(self)

    def continue_with(self, callback: Callable[['Task'], None]) -> None:
        """Registers an action to invoke when the task completes."""
        fire_immediately = False
        with self._lock:
            if self.state in (TaskState.COMPLETED, TaskState.FAULTED):
                fire_immediately = True
            else:
                self._continuations.append(callback)
        
        if fire_immediately:
            callback(self)

# --- Section 2: CLR Work-Stealing ThreadPool Engine ---

class WorkItem:
    """Represents an executable delegate dispatched to the ThreadPool."""
    def __init__(self, action: Callable[[], None], origin: str):
        self.action = action
        self.origin = origin

class CLRThreadPool:
    """
    Simulates the .NET CLR ThreadPool:
    - Global FIFO queue for thread-external work.
    - Local thread-specific deque (push/pop LIFO for owner; popleft FIFO for thieves).
    - Cooperative work-stealing algorithm.
    """
    def __init__(self, worker_count: int = 4):
        self.worker_count = worker_count
        self.global_queue: deque[WorkItem] = deque()
        self.global_lock = threading.Lock()
        
        self.local_queues: Dict[int, deque[WorkItem]] = {}
        self.local_locks: Dict[int, threading.Lock] = {}
        
        self.workers: List[threading.Thread] = []
        self.running = True
        self.work_available = threading.Condition()
        
        # Telemetry metrics
        self.stats_lock = threading.Lock()
        self.stats = {
            "global_execs": 0,
            "local_execs": 0,
            "steals": 0
        }

        # Initialize per-worker queues
        for i in range(worker_count):
            self.local_queues[i] = deque()
            self.local_locks[i] = threading.Lock()

    def start(self) -> None:
        for i in range(self.worker_count):
            t = threading.Thread(target=self._worker_loop, args=(i,), name=f".NET-ThreadPoolWorker-{i}")
            t.daemon = True
            self.workers.append(t)
            t.start()

    def queue_user_work_item(self, action: Callable[[], None], origin: str = "External") -> None:
        """External dispatch: Always goes to the Global FIFO Queue."""
        with self.global_lock:
            self.global_queue.append(WorkItem(action, origin))
        with self.work_available:
            self.work_available.notify()

    def queue_local_or_global(self, action: Callable[[], None], origin: str = "Internal") -> None:
        """
        Internal dispatch (e.g. from within a running Task):
        If caller is a ThreadPool worker, pushes to local deque (LIFO).
        Otherwise pushes to Global Queue.
        """
        worker_id = getattr(thread_context, "worker_id", None)
        if worker_id is not None:
            with self.local_locks[worker_id]:
                self.local_queues[worker_id].append(WorkItem(action, origin))
            with self.work_available:
                self.work_available.notify()
        else:
            self.queue_user_work_item(action, origin)

    def _worker_loop(self, worker_id: int) -> None:
        thread_context.worker_id = worker_id
        while self.running:
            item = None
            source_type = None

            # 1. Try local queue first (LIFO order: pop from right)
            with self.local_locks[worker_id]:
                if self.local_queues[worker_id]:
                    item = self.local_queues[worker_id].pop()
                    source_type = "local"

            # 2. Try global queue (FIFO order: popleft from global)
            if item is None:
                with self.global_lock:
                    if self.global_queue:
                        item = self.global_queue.popleft()
                        source_type = "global"

            # 3. Work-Stealing: Steal from another worker (FIFO order: popleft from victim)
            if item is None:
                victim_candidates = [i for i in range(self.worker_count) if i != worker_id]
                random.shuffle(victim_candidates)
                for victim_id in victim_candidates:
                    with self.local_locks[victim_id]:
                        if self.local_queues[victim_id]:
                            item = self.local_queues[victim_id].popleft()
                            source_type = "stolen"
                            break

            # Execute work item or wait
            if item is not None:
                with self.stats_lock:
                    if source_type == "local":
                        self.stats["local_execs"] += 1
                    elif source_type == "global":
                        self.stats["global_execs"] += 1
                    elif source_type == "stolen":
                        self.stats["steals"] += 1

                try:
                    item.action()
                except Exception as ex:
                    print(f"{Color.RED}[ThreadPool Error] Unhandled Exception: {ex}{Color.RESET}")
            else:
                with self.work_available:
                    self.work_available.wait(timeout=0.05)

    def shutdown(self) -> None:
        self.running = False
        with self.work_available:
            self.work_available.notify_all()
        for t in self.workers:
            t.join()

# --- Section 3: Roslyn Async State Machine Simulation ---

class AsyncPipelineStateMachine:
    """
    Simulates compiler-lowered `async Task<string> ProcessOrderAsync(int order_id)`.
    
    Equivalent C# Code:
    ```csharp
    async Task<string> ProcessOrderAsync(int orderId) {
        var inv = await ValidateInventoryAsync(orderId);
        var auth = await AuthorizePaymentAsync(inv);
        return $"Order {orderId} Completed with Auth: {auth}";
    }
    ```
    """
    def __init__(self, order_id: int, pool: CLRThreadPool):
        self.order_id = order_id
        self.pool = pool
        self.state = -1  # -1 = Not Started, 0 = Awaiting Validate, 1 = Awaiting Auth, -2 = Finished
        self.task = Task(name=f"ProcessOrderPipeline-{order_id}")
        
        # Lifted local variables (Compiler hoists these to heap struct/class fields)
        self._inv_result: Optional[str] = None
        self._auth_result: Optional[str] = None
        self._current_awaiter: Optional[Task] = None

    def move_next(self) -> None:
        """The core engine of C# async methods, called upon every resumption."""
        worker_id = getattr(thread_context, "worker_id", "MainThread")
        
        try:
            if self.state == -1:
                # State -1: Entry point -> Kick off first async operation
                print(f"  {Color.CYAN}[Thread-{worker_id}]{Color.RESET} StateMachine #{self.order_id}: Entry (State -1). Initiating Inventory Check...")
                self.state = 0
                self._current_awaiter = self._validate_inventory_async(self.order_id)
                
                # Check if completed synchronously (rare in I/O, but standard optimization path)
                if not self._current_awaiter.is_completed:
                    # Wire continuation to resume MoveNext on ThreadPool
                    self._current_awaiter.continue_with(lambda _: self.pool.queue_local_or_global(self.move_next, "Continuation-State0"))
                    return

            if self.state == 0:
                # State 0: Inventory check complete -> Resume, extract result, kick off payment
                self._inv_result = self._current_awaiter.result
                print(f"  {Color.MAGENTA}[Thread-{worker_id}]{Color.RESET} StateMachine #{self.order_id}: Resumed (State 0). Inventory result: '{self._inv_result}'. Authorizing Payment...")
                self.state = 1
                self._current_awaiter = self._authorize_payment_async(self._inv_result)
                
                if not self._current_awaiter.is_completed:
                    self._current_awaiter.continue_with(lambda _: self.pool.queue_local_or_global(self.move_next, "Continuation-State1"))
                    return

            if self.state == 1:
                # State 1: Payment complete -> Finish and transition to -2
                self._auth_result = self._current_awaiter.result
                print(f"  {Color.GREEN}[Thread-{worker_id}]{Color.RESET} StateMachine #{self.order_id}: Resumed (State 1). Auth token: '{self._auth_result}'. Finalizing.")
                self.state = -2
                final_output = f"SUCCESS [Order: {self.order_id}, Auth: {self._auth_result}]"
                self.task.set_result(final_output)

        except Exception as ex:
            self.state = -2
            self.task.exception = ex
            self.task.state = TaskState.FAULTED

    def _validate_inventory_async(self, order_id: int) -> Task:
        """Simulates asynchronous non-blocking I/O (e.g. database query)."""
        t = Task(name=f"ValidateInventory-{order_id}")
        
        def mock_io_completion():
            time.sleep(0.04)  # Simulate network latency
            t.set_result(f"INV_STOCK_RESERVED_FOR_{order_id}")

        # Spawn simulation on ThreadPool
        self.pool.queue_local_or_global(mock_io_completion, "I/O-Callback-1")
        return t

    def _authorize_payment_async(self, inv_token: str) -> Task:
        """Simulates external payment gateway HTTP call."""
        t = Task(name=f"AuthorizePayment")
        
        def mock_http_completion():
            time.sleep(0.03)  # Simulate gateway latency
            auth_token = f"AUTH_TX_{abs(hash(inv_token)) % 100000:05d}"
            t.set_result(auth_token)

        self.pool.queue_local_or_global(mock_http_completion, "I/O-Callback-2")
        return t

# --- Section 4: Lab Execution and Diagnostics ---

def print_header(title: str) -> None:
    border = "=" * 70
    print(f"\n{Color.BOLD}{Color.BLUE}{border}")
    print(f"  {title.center(66)}")
    print(f"{border}{Color.RESET}\n")

def main():
    print_header("LAB: C# CLR THREADPOOL & ASYNC STATE MACHINE INTERNALS")
    
    pool_size = 4
    total_orders = 8
    print(f"{Color.BOLD}Configuring Simulated CLR Environment:{Color.RESET}")
    print(f"  - Worker Threads        : {pool_size} (Dedicated pool workers)")
    print(f"  - Work Queuing Model    : Dual (Global FIFO + Worker Local LIFO/Stealing)")
    print(f"  - State Machine Engine  : Roslyn IAsyncStateMachine Lowering Pattern\n")

    pool = CLRThreadPool(worker_count=pool_size)
    pool.start()

    print(f"{Color.YELLOW}[System] ThreadPool workers online. Dispatching {total_orders} async pipelines...{Color.RESET}\n")
    
    state_machines: List[AsyncPipelineStateMachine] = []
    
    # Dispatch state machines
    for order_id in range(101, 101 + total_orders):
        sm = AsyncPipelineStateMachine(order_id, pool)
        state_machines.append(sm)
        # Entry point: Task.Run equivalent (External dispatch to global queue)
        pool.queue_user_work_item(sm.move_next, origin=f"OrderBootstrap-{order_id}")

    # Wait for all async pipelines to finish
    all_completed = False
    start_time = time.time()
    
    while not all_completed:
        all_completed = all(sm.task.is_completed for sm in state_machines)
        time.sleep(0.01)

    elapsed = time.time() - start_time

    # Display Results
    print(f"\n{Color.BOLD}{Color.GREEN}All Asynchronous Pipelines Completed Successfully!{Color.RESET}")
    print(f"Total Execution Time: {elapsed * 1000:.2f} ms\n")

    print_header("EXECUTION METRICS & CLR THREADPOOL TELEMETRY")
    print(f"{'Order ID':<10} | {'Status':<12} | {'Result Summary'}")
    print("-" * 65)
    for sm in state_machines:
        status_str = f"{Color.GREEN}COMPLETED{Color.RESET}" if sm.task.state == TaskState.COMPLETED else f"{Color.RED}FAILED{Color.RESET}"
        print(f"{sm.order_id:<10} | {status_str:<21} | {sm.task.result}")

    print(f"\n{Color.BOLD}ThreadPool Queue Scheduling Statistics:{Color.RESET}")
    print(f"  * Global Queue Dequeues (FIFO) : {pool.stats['global_execs']:>4}  (External entries & direct dispatches)")
    print(f"  * Local Queue Pops (LIFO)     : {pool.stats['local_execs']:>4}  (Locality-preserving continuation resumptions)")
    print(f"  * Cross-Thread Work Steals    : {pool.stats['steals']:>4}  (Load balancing via peer queue popleft)")

    pool.shutdown()
    print(f"\n{Color.GRAY}[System] ThreadPool torn down cleanly. Lab execution completed.{Color.RESET}")

if __name__ == "__main__":
    main()
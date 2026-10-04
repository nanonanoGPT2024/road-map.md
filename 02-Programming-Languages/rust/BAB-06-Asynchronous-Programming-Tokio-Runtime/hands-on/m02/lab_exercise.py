#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive into Rust Asynchronous Programming & Tokio Runtime
Simulating Rust's Poll-Based Future State Machine, Reactor Pattern, and Work-Stealing Runtime.
"""

import sys
import time
import threading
import collections
from typing import Any, Callable, Optional, Deque, List, Tuple
from dataclasses import dataclass

# --- Terminal ANSI Color Constants ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_CYAN    = "\033[36m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE    = "\033[34m"
CLR_RED     = "\033[31m"

def log_event(worker_id: str, tag: str, message: str, color: str = CLR_CYAN):
    now = time.strftime("%H:%M:%S")
    print(f"{CLR_BOLD}[{now}]{CLR_RESET} [{color}{worker_id:<10}{CLR_RESET}] [{tag:<12}] {message}")

# ============================================================================
# Section 1: Rust Future Trait & Polling Primitives
# ============================================================================

class Poll:
    """Represents Rust's core `std::task::Poll<T>` enum."""
    @dataclass
    class Ready:
        val: Any

    @dataclass
    class Pending:
        pass

@dataclass
class Waker:
    """
    Simulates Rust's `std::task::Waker`.
    Contains a handle back to the runtime to wake and re-enqueue a specific task.
    """
    wake_fn: Callable[[], None]

    def wake(self):
        self.wake_fn()

@dataclass
class Context:
    """Simulates Rust's `std::task::Context<'_>` holding a reference to the Waker."""
    waker: Waker

class Future:
    """
    Abstract interface modeling Rust's:
        pub trait Future {
            type Output;
            fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
        }
    """
    def poll(self, cx: Context) -> Any:
        raise NotImplementedError("Future must implement poll()")

# ============================================================================
# Section 2: Reactor Pattern (I/O & Timer Reactor)
# ============================================================================

class TimerReactor:
    """
    Simulates Tokio's background reactor (e.g., epoll/kqueue/timer wheel).
    Tracks external I/O/Timer readiness and fires task wakers when ready.
    """
    def __init__(self):
        self._timers: List[Tuple[float, Waker]] = []
        self._lock = threading.Lock()
        self._running = True
        self._reactor_thread = threading.Thread(target=self._run, name="TokioReactor", daemon=True)
        self._reactor_thread.start()

    def register_timer(self, deadline: float, waker: Waker):
        with self._lock:
            self._timers.append((deadline, waker))
            self._timers.sort(key=lambda x: x[0])

    def _run(self):
        while self._running:
            now = time.time()
            wakers_to_fire = []
            with self._lock:
                while self._timers and self._timers[0][0] <= now:
                    _, waker = self._timers.pop(0)
                    wakers_to_fire.append(waker)
            for w in wakers_to_fire:
                w.wake()
            time.sleep(0.005)

    def shutdown(self):
        self._running = False

# ============================================================================
# Section 3: Concrete Async Primitives (Leaf & Composite Futures)
# ============================================================================

class TokioSleepFuture(Future):
    """Leaf Future: Models `tokio::time::sleep(duration)`."""
    def __init__(self, duration_sec: float, reactor: TimerReactor):
        self.duration_sec = duration_sec
        self.reactor = reactor
        self.deadline: Optional[float] = None
        self.registered = False

    def poll(self, cx: Context) -> Any:
        now = time.time()
        if self.deadline is None:
            self.deadline = now + self.duration_sec
            self.reactor.register_timer(self.deadline, cx.waker)
            self.registered = True
            return Poll.Pending()
        
        if now >= self.deadline:
            return Poll.Ready(f"Slept {self.duration_sec:.2f}s")
        else:
            return Poll.Pending()

class MpscChannel:
    """Models Tokio's bounded channel: `tokio::sync::mpsc`."""
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.queue: Deque[Any] = collections.deque()
        self.recv_waker: Optional[Waker] = None
        self.lock = threading.Lock()

    def send(self, val: Any) -> bool:
        with self.lock:
            if len(self.queue) >= self.capacity:
                return False
            self.queue.append(val)
            if self.recv_waker:
                w = self.recv_waker
                self.recv_waker = None
                w.wake()
            return True

    def recv_future(self) -> Future:
        return MpscRecvFuture(self)

class MpscRecvFuture(Future):
    def __init__(self, channel: MpscChannel):
        self.channel = channel

    def poll(self, cx: Context) -> Any:
        with self.channel.lock:
            if self.channel.queue:
                val = self.channel.queue.popleft()
                return Poll.Ready(val)
            # Register waker so producer can notify
            self.channel.recv_waker = cx.waker
            return Poll.Pending()

# ============================================================================
# Section 4: Tokio Work-Stealing Runtime Simulation
# ============================================================================

class Task:
    """Wraps a Future into an executable Task managed by the Tokio Executor."""
    _id_counter = 1

    def __init__(self, future: Future, name: str):
        self.task_id = Task._id_counter
        Task._id_counter += 1
        self.name = name
        self.future = future
        self.poll_count = 0
        self.completed = False
        self.output: Any = None

class TokioRuntime:
    """
    Simulates Tokio's Multi-Threaded Scheduler with Work-Stealing:
    - Dedicated worker threads with individual double-ended queues (deque).
    - If a worker's local queue is empty, it attempts to steal tasks from peers.
    """
    def __init__(self, worker_count: int = 2):
        self.worker_count = worker_count
        self.reactor = TimerReactor()
        self.queues: List[Deque[Task]] = [collections.deque() for _ in range(worker_count)]
        self.locks: List[threading.Lock] = [threading.Lock() for _ in range(worker_count)]
        self.workers: List[threading.Thread] = []
        self.running = True
        self.metrics = {"polls": 0, "steals": 0, "completed": 0}
        self.metrics_lock = threading.Lock()

        for i in range(worker_count):
            t = threading.Thread(target=self._worker_loop, args=(i,), name=f"tokio-worker-{i}")
            self.workers.append(t)
            t.start()

    def spawn(self, future: Future, name: str) -> Task:
        task = Task(future, name)
        # Round-robin dispatch for initial placement
        target_idx = (task.task_id - 1) % self.worker_count
        with self.locks[target_idx]:
            self.queues[target_idx].append(task)
        log_event(f"spawn", "TASK_ENQUEUE", f"Task #{task.task_id} ('{name}') -> Worker {target_idx}", CLR_YELLOW)
        return task

    def _worker_loop(self, worker_idx: int):
        tag = f"Worker-{worker_idx}"
        while self.running:
            task = self._pop_task(worker_idx)
            if not task:
                time.sleep(0.002)
                continue

            # Create context with a closure Waker that re-enqueues into this worker's queue
            def make_wake(t: Task, w_idx: int):
                return lambda: self._re_enqueue(t, w_idx)

            waker = Waker(wake_fn=make_wake(task, worker_idx))
            cx = Context(waker=waker)

            task.poll_count += 1
            with self.metrics_lock:
                self.metrics["polls"] += 1

            # Cooperative polling step
            poll_result = task.future.poll(cx)

            if isinstance(poll_result, Poll.Ready):
                task.completed = True
                task.output = poll_result.val
                with self.metrics_lock:
                    self.metrics["completed"] += 1
                log_event(tag, "POLL_READY", f"Task #{task.task_id} completed in {task.poll_count} polls. Result: {poll_result.val}", CLR_GREEN)
            elif isinstance(poll_result, Poll.Pending):
                log_event(tag, "POLL_PENDING", f"Task #{task.task_id} yield -> Reactor parked (polls: {task.poll_count})", CLR_MAGENTA)
            else:
                raise ValueError("Invalid Poll variant returned from Future")

    def _pop_task(self, worker_idx: int) -> Optional[Task]:
        # 1. Local queue pop
        with self.locks[worker_idx]:
            if self.queues[worker_idx]:
                return self.queues[worker_idx].popleft()

        # 2. Work-stealing: steal from peers from the back of their queue
        for victim_idx in range(self.worker_count):
            if victim_idx == worker_idx:
                continue
            with self.locks[victim_idx]:
                if len(self.queues[victim_idx]) > 0:
                    stolen = self.queues[victim_idx].pop()
                    with self.metrics_lock:
                        self.metrics["steals"] += 1
                    log_event(f"Worker-{worker_idx}", "WORK_STEAL", f"Stole Task #{stolen.task_id} from Worker-{victim_idx}", CLR_BLUE)
                    return stolen
        return None

    def _re_enqueue(self, task: Task, preferred_worker: int):
        with self.locks[preferred_worker]:
            self.queues[preferred_worker].append(task)
        log_event(f"Waker", "WAKE_TRIGGER", f"Task #{task.task_id} woken -> Pushed to Worker-{preferred_worker}", CLR_CYAN)

    def shutdown(self):
        self.running = False
        for t in self.workers:
            t.join()
        self.reactor.shutdown()

# ============================================================================
# Section 5: Higher-Level State Machine Future Simulation
# ============================================================================

class ComputePipelineFuture(Future):
    """
    Emulates an `async fn` synthesized by rustc into a state machine:
    State 0: Initial
    State 1: Awaiting timer (I/O)
    State 2: Awaiting channel data
    State 3: Done
    """
    def __init__(self, name: str, reactor: TimerReactor, channel: MpscChannel):
        self.name = name
        self.state = 0
        self.sleep_fut = TokioSleepFuture(0.15, reactor)
        self.chan_fut = channel.recv_future()
        self.accumulated: List[str] = []

    def poll(self, cx: Context) -> Any:
        # State machine transition loop
        while True:
            if self.state == 0:
                # Transition to State 1: Poll sleep
                res = self.sleep_fut.poll(cx)
                if isinstance(res, Poll.Pending):
                    return Poll.Pending()
                self.accumulated.append(str(res.val))
                self.state = 1
                continue

            elif self.state == 1:
                # Transition to State 2: Poll channel
                res = self.chan_fut.poll(cx)
                if isinstance(res, Poll.Pending):
                    return Poll.Pending()
                self.accumulated.append(f"Payload: {res.val}")
                self.state = 2
                continue

            elif self.state == 2:
                # Final state: Return synthesized result
                return Poll.Ready(" -> ".join(self.accumulated))

# ============================================================================
# Section 6: Verification and Benchmark Harness
# ============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}=================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  LAB 06-02: TOKIO RUNTIME ARCHITECTURE & COOPERATIVE FUTURES    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}=================================================================={CLR_RESET}\n")

    runtime = TokioRuntime(worker_count=3)
    channel = MpscChannel(capacity=2)

    log_event("Main", "RUNTIME_INIT", "Multi-threaded Tokio scheduler running (3 workers + Reactor)", CLR_GREEN)

    # Spawn 3 pipeline futures that will wait on sleep and channel
    tasks: List[Task] = []
    for i in range(3):
        fut = ComputePipelineFuture(f"pipeline_{i+1}", runtime.reactor, channel)
        tasks.append(runtime.spawn(fut, f"pipeline_{i+1}"))

    # Spawn background producer after short delay
    def background_producer():
        payloads = ["Msg-Alpha", "Msg-Beta", "Msg-Gamma"]
        for p in payloads:
            time.sleep(0.08)
            channel.send(p)
            log_event("Producer", "CHAN_SEND", f"Sent: {p} into async channel", CLR_YELLOW)

    prod_thread = threading.Thread(target=background_producer, name="ProducerThread", daemon=True)
    prod_thread.start()

    # Block until all tasks finish (equivalent to runtime.block_on)
    start_time = time.time()
    while True:
        all_done = all(t.completed for t in tasks)
        if all_done:
            break
        time.sleep(0.01)
    duration = time.time() - start_time

    prod_thread.join()
    runtime.shutdown()

    # Print Post-Execution Report
    print(f"\n{CLR_BOLD}{CLR_GREEN}------------------------ RUNTIME EXECUTION REPORT ------------------------{CLR_RESET}")
    for t in tasks:
        print(f" Task ID: {CLR_BOLD}#{t.task_id:<2}{CLR_RESET} | Name: {CLR_CYAN}{t.name:<12}{CLR_RESET} | "
              f"Polls: {CLR_YELLOW}{t.poll_count:<3}{CLR_RESET} | Output: {CLR_GREEN}{t.output}{CLR_RESET}")

    print(f"\n{CLR_BOLD}Performance & Scheduling Metrics:{CLR_RESET}")
    print(f" - Wall Execution Time : {duration:.4f}s")
    print(f" - Total Poll Invocations: {runtime.metrics['polls']}")
    print(f" - Work-Steal Events    : {runtime.metrics['steals']}")
    print(f" - Completed Futures    : {runtime.metrics['completed']}")
    print(f"{CLR_BOLD}{CLR_GREEN}--------------------------------------------------------------------------{CLR_RESET}\n")
    print(f"{CLR_CYAN}[Rust Concept Check]{CLR_RESET}: Unlike JS/Python async/await which eagerly construct")
    print("promises/generators on invocation, Rust's Futures are completely inert (lazy)")
    print("until driven by poll(cx). Wakers guarantee zero-cost event notification without")
    print("thread contention, enabling Tokio to power ultra-low overhead network services.\n")

if __name__ == "__main__":
    main()
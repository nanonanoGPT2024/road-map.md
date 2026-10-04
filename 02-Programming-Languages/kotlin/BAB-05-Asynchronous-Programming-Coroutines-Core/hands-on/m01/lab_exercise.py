#!/usr/bin/env python3
"""
Lab Exercise: Kotlin Coroutines Core Simulator
BAB-05: Asynchronous Programming - Coroutines Core

Simulasi Teknis Mandiri Konsep Inti Kotlin Coroutines:
1. CoroutineScope & Structured Concurrency (Parent-Child Hierarchy)
2. Job Lifecycle & State Transitions (Active -> Completing -> Completed / Cancelled)
3. Dispatchers Architecture (Main/UI, Default/WorkerPool, IO/ElasticPool)
4. Coroutine Builders (launch vs async/await)
5. Suspend Function & CPS (Continuation-Passing Style) State Machine
"""

import sys
import time
import threading
import queue
import enum
from typing import Any, Callable, Dict, List, Optional


# ==============================================================================
# ANSI Color Codes & Formatting Helpers
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def log_event(tag: str, message: str, color: str = Color.CYAN) -> None:
    tname = threading.current_thread().name
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} {Color.BOLD}[{tname:^18}]{Color.RESET} {color}[{tag:<14}]{Color.RESET} {message}")


# ==============================================================================
# Core Concept 1: Job Lifecycle States & Hierarchy
# ==============================================================================
class JobState(enum.Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    COMPLETING = "COMPLETING"
    COMPLETED = "COMPLETED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"


class Job:
    _id_counter = 1

    def __init__(self, name: Optional[str] = None, parent: Optional["Job"] = None):
        self.id = Job._id_counter
        Job._id_counter += 1
        self.name = name or f"Job-{self.id}"
        self.state = JobState.ACTIVE
        self.parent = parent
        self.children: List["Job"] = []
        self._lock = threading.Lock()
        self._completion_event = threading.Event()
        self.exception: Optional[Exception] = None

        if parent:
            parent.attach_child(self)

    def attach_child(self, child: "Job") -> None:
        with self._lock:
            self.children.append(child)

    def is_active(self) -> bool:
        return self.state == JobState.ACTIVE

    def is_completed(self) -> bool:
        return self.state in (JobState.COMPLETED, JobState.CANCELLED)

    def is_cancelled(self) -> bool:
        return self.state == JobState.CANCELLED

    def cancel(self, reason: str = "Job cancelled explicitly") -> None:
        with self._lock:
            if self.is_completed() or self.state == JobState.CANCELLING:
                return
            self.state = JobState.CANCELLING
            log_event("JOB_CANCEL", f"{Color.RED}Cancelling {self.name} (Reason: {reason}){Color.RESET}")

            # Propagate cancellation downstream to all active child jobs
            for child in list(self.children):
                if child.is_active():
                    child.cancel(f"Parent {self.name} cancelled")

            self.state = JobState.CANCELLED
            self._completion_event.set()

    def complete(self) -> None:
        with self._lock:
            if self.state != JobState.ACTIVE:
                return
            self.state = JobState.COMPLETING
            # Structured concurrency: wait for all children to complete
            for child in self.children:
                child.join()

            if self.state == JobState.COMPLETING:
                self.state = JobState.COMPLETED
                log_event("JOB_COMPLETE", f"{Color.GREEN}{self.name} completed successfully{Color.RESET}")
                self._completion_event.set()

    def join(self, timeout: Optional[float] = None) -> bool:
        return self._completion_event.wait(timeout)


class Deferred(Job):
    """Simulasi Deferred<T> dari builder async { ... }"""
    def __init__(self, name: Optional[str] = None, parent: Optional[Job] = None):
        super().__init__(name, parent)
        self._result: Any = None

    def set_result(self, value: Any) -> None:
        self._result = value
        self.complete()

    def await_result(self) -> Any:
        self.join()
        if self.is_cancelled():
            raise RuntimeError(f"Deferred {self.name} was cancelled before completing!")
        if self.exception:
            raise self.exception
        return self._result


# ==============================================================================
# Core Concept 2: Dispatchers Architecture
# ==============================================================================
class Dispatcher:
    def dispatch(self, task: Callable[[], None]) -> None:
        raise NotImplementedError


class SingleThreadDispatcher(Dispatcher):
    """Simulasi Dispatchers.Main (UI Thread / Event Loop)"""
    def __init__(self, name: str = "MainDispatcher"):
        self.queue: queue.Queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, name=name, daemon=True)
        self.thread.start()

    def _run_loop(self) -> None:
        while self.running:
            try:
                task = self.queue.get(timeout=0.1)
                task()
                self.queue.task_done()
            except queue.Empty:
                continue

    def dispatch(self, task: Callable[[], None]) -> None:
        self.queue.put(task)


class ThreadPoolDispatcher(Dispatcher):
    """Simulasi Dispatchers.Default (CPU-bound) & Dispatchers.IO (IO-bound)"""
    def __init__(self, pool_size: int, name_prefix: str):
        self.queue: queue.Queue = queue.Queue()
        self.running = True
        self.workers = []
        for i in range(pool_size):
            t = threading.Thread(target=self._worker_loop, name=f"{name_prefix}-{i+1}", daemon=True)
            t.start()
            self.workers.append(t)

    def _worker_loop(self) -> None:
        while self.running:
            try:
                task = self.queue.get(timeout=0.1)
                task()
                self.queue.task_done()
            except queue.Empty:
                continue

    def dispatch(self, task: Callable[[], None]) -> None:
        self.queue.put(task)


class Dispatchers:
    Main = SingleThreadDispatcher(name="Dispatcher.Main")
    Default = ThreadPoolDispatcher(pool_size=4, name_prefix="DefaultWorker")
    IO = ThreadPoolDispatcher(pool_size=8, name_prefix="IOWorker")


# ==============================================================================
# Core Concept 3: CoroutineScope & Builders (launch, async)
# ==============================================================================
class CoroutineScope:
    def __init__(self, default_dispatcher: Dispatcher = Dispatchers.Default, parent_job: Optional[Job] = None):
        self.dispatcher = default_dispatcher
        self.job = parent_job or Job("RootScopeJob")

    def launch(self, block: Callable[["CoroutineScope"], None], dispatcher: Optional[Dispatcher] = None, name: Optional[str] = None) -> Job:
        active_dispatcher = dispatcher or self.dispatcher
        job = Job(name=name, parent=self.job)
        child_scope = CoroutineScope(default_dispatcher=active_dispatcher, parent_job=job)

        def runner():
            log_event("LAUNCH", f"{Color.MAGENTA}Start coroutine: {job.name}{Color.RESET}")
            try:
                block(child_scope)
                job.complete()
            except Exception as e:
                job.exception = e
                log_event("ERROR", f"{Color.RED}Exception in {job.name}: {e}{Color.RESET}")
                job.cancel(str(e))

        active_dispatcher.dispatch(runner)
        return job

    def async_builder(self, block: Callable[["CoroutineScope"], Any], dispatcher: Optional[Dispatcher] = None, name: Optional[str] = None) -> Deferred:
        active_dispatcher = dispatcher or self.dispatcher
        deferred = Deferred(name=name, parent=self.job)
        child_scope = CoroutineScope(default_dispatcher=active_dispatcher, parent_job=deferred)

        def runner():
            log_event("ASYNC", f"{Color.CYAN}Start deferred task: {deferred.name}{Color.RESET}")
            try:
                res = block(child_scope)
                deferred.set_result(res)
            except Exception as e:
                deferred.exception = e
                log_event("ERROR", f"{Color.RED}Async failed in {deferred.name}: {e}{Color.RESET}")
                deferred.cancel(str(e))

        active_dispatcher.dispatch(runner)
        return deferred


def non_blocking_delay(scope_or_job: Any, duration_sec: float) -> None:
    """
    Simulasi suspending function delay(duration).
    Mengecek pembatalan (cancellation check) secara kooperatif.
    """
    job = scope_or_job.job if isinstance(scope_or_job, CoroutineScope) else scope_or_job
    slices = int(duration_sec / 0.05)
    for _ in range(slices):
        if job.is_cancelled():
            log_event("SUSPEND", f"{Color.YELLOW}Delay suspended early: {job.name} detected cancellation!{Color.RESET}")
            raise RuntimeError(f"JobCancellationException: {job.name} was cancelled")
        time.sleep(0.05)


# ==============================================================================
# Core Concept 4: Continuation-Passing Style (CPS) State Machine Simulation
# ==============================================================================
class Continuation:
    """Simulasi Continuation<T> di Kotlin runtime"""
    def __init__(self, callback: Callable[[Any, Optional[Exception]], None]):
        self.callback = callback

    def resume_with(self, result: Any, exception: Optional[Exception] = None) -> None:
        self.callback(result, exception)


class SuspendStateMachine:
    """
    Simulasi de-sugaring compiler Kotlin:
    Fungsi suspend diubah menjadi state machine switch(label) berbasis continuation.
    """
    def __init__(self, user_id: int, continuation: Continuation):
        self.user_id = user_id
        self.continuation = continuation
        self.label = 0
        self.user_name: Optional[str] = None
        self.user_points: Optional[int] = None

    def proceed(self, result: Any = None, exc: Optional[Exception] = None) -> None:
        if exc:
            self.continuation.resume_with(None, exc)
            return

        if self.label == 0:
            log_event("CPS_MACHINE", f"{Color.BLUE}State 0: Fetching user profile (Async I/O){Color.RESET}")
            self.label = 1
            # Simulasi asynchronous suspension step 1
            def async_fetch_profile():
                time.sleep(0.3)
                self.proceed(result="Alice Developer")
            threading.Thread(target=async_fetch_profile, name="CPS-Worker-1", daemon=True).start()

        elif self.label == 1:
            self.user_name = result
            log_event("CPS_MACHINE", f"{Color.BLUE}State 1: Profile received '{self.user_name}'. Fetching points...{Color.RESET}")
            self.label = 2
            # Simulasi asynchronous suspension step 2
            def async_fetch_points():
                time.sleep(0.2)
                self.proceed(result=9500)
            threading.Thread(target=async_fetch_points, name="CPS-Worker-2", daemon=True).start()

        elif self.label == 2:
            self.user_points = result
            log_event("CPS_MACHINE", f"{Color.GREEN}State 2: Points received ({self.user_points}). Resuming caller continuation!{Color.RESET}")
            final_data = {"id": self.user_id, "name": self.user_name, "points": self.user_points}
            self.continuation.resume_with(final_data, None)


# ==============================================================================
# Interactive Demonstration Scenarios
# ==============================================================================
def demo_structured_concurrency() -> None:
    print(f"\n{Color.BOLD}{Color.BG_BLUE} SCENARIO 1: STRUCTURED CONCURRENCY & CANCELLATION PROPAGATION {Color.RESET}\n")
    scope = CoroutineScope(Dispatchers.Default)

    def parent_routine(p_scope: CoroutineScope):
        log_event("PARENT", f"{Color.WHITE}Parent started. Spawning 2 child coroutines...{Color.RESET}")
        p_scope.launch(
            lambda c1: (
                log_event("CHILD-1", "Child 1 doing ongoing task (1.0s)..."),
                non_blocking_delay(c1, 1.0),
                log_event("CHILD-1", f"{Color.GREEN}Child 1 done.{Color.RESET}")
            ),
            name="Child-1"
        )
        p_scope.launch(
            lambda c2: (
                log_event("CHILD-2", "Child 2 doing fast task (0.2s)..."),
                non_blocking_delay(c2, 0.2),
                log_event("CHILD-2", f"{Color.GREEN}Child 2 finished quickly!{Color.RESET}")
            ),
            name="Child-2"
        )
        time.sleep(0.3)
        log_event("PARENT", f"{Color.RED}Parent encountered issue! Cancelling self...{Color.RESET}")
        p_scope.job.cancel("Simulated Parent Failure")

    parent_job = scope.launch(parent_routine, name="Parent-Supervisor")
    parent_job.join(2.0)
    time.sleep(0.1)
    print(f"\n{Color.YELLOW}Final States: Parent={parent_job.state.value}{Color.RESET}")
    for ch in parent_job.children:
        print(f"  └── {ch.name}: {ch.state.value}")


def demo_async_await() -> None:
    print(f"\n{Color.BOLD}{Color.BG_MAGENTA} SCENARIO 2: ASYNC / AWAIT CONCURRENT COMPUTATION {Color.RESET}\n")
    scope = CoroutineScope(Dispatchers.IO)

    start_time = time.time()
    def fetch_user_data(s: CoroutineScope):
        log_event("FETCH_USER", "Requesting user profile from REST API (IO)...")
        time.sleep(0.5)
        return {"id": 101, "name": "Budi Santoso"}

    def fetch_user_orders(s: CoroutineScope):
        log_event("FETCH_ORDERS", "Requesting orders from Microservice (IO)...")
        time.sleep(0.5)
        return ["Order-A1", "Order-B2", "Order-C3"]

    deferred_user = scope.async_builder(fetch_user_data, name="AsyncUser")
    deferred_orders = scope.async_builder(fetch_user_orders, name="AsyncOrders")

    log_event("MAIN", "Waiting for both deferred tasks via await()...", Color.WHITE)
    user = deferred_user.await_result()
    orders = deferred_orders.await_result()
    elapsed = time.time() - start_time

    print(f"\n{Color.GREEN}Result Combined in {elapsed:.2f}s (Concurrent speedup):{Color.RESET}")
    print(f"  User   : {user}")
    print(f"  Orders : {orders}")


def demo_dispatchers() -> None:
    print(f"\n{Color.BOLD}{Color.BG_BLUE} SCENARIO 3: DISPATCHERS CONTEXT SWITCHING {Color.RESET}\n")
    scope = CoroutineScope()

    # Step 1: Background IO
    scope.launch(
        lambda job: (
            log_event("IO_TASK", f"Downloading payload using {Dispatchers.IO.__class__.__name__}", Color.YELLOW),
            time.sleep(0.4),
            # Step 2: Switch to Main Thread for UI update
            Dispatchers.Main.dispatch(
                lambda: log_event("UI_UPDATE", f"{Color.GREEN}Render data on Screen (Must run on Main!){Color.RESET}", Color.GREEN)
            )
        ),
        dispatcher=Dispatchers.IO,
        name="NetworkWorker"
    ).join(1.0)


def demo_cps_compiler_desugar() -> None:
    print(f"\n{Color.BOLD}{Color.BG_MAGENTA} SCENARIO 4: CONTINUATION STATE MACHINE (UNDER THE HOOD) {Color.RESET}\n")
    done_event = threading.Event()

    def on_complete(result: Any, err: Optional[Exception]):
        if err:
            log_event("CPS_CALLBACK", f"{Color.RED}Failed: {err}{Color.RESET}")
        else:
            log_event("CPS_CALLBACK", f"{Color.GREEN}Final Suspend Function Output: {result}{Color.RESET}")
        done_event.set()

    continuation = Continuation(callback=on_complete)
    sm = SuspendStateMachine(user_id=42, continuation=continuation)
    sm.proceed()  # Trigger state 0
    done_event.wait(2.0)


# ==============================================================================
# Interactive Menu Runner
# ==============================================================================
def display_header() -> None:
    banner = f"""{Color.CYAN}
================================================================================
   KOTLIN COROUTINES CORE - ARCHITECTURAL & TECHNICAL SIMULATOR
   BAB-05: Asynchronous Programming & Structured Concurrency
================================================================================{Color.RESET}
    """
    print(banner)


def run_all() -> None:
    demo_structured_concurrency()
    time.sleep(0.5)
    demo_async_await()
    time.sleep(0.5)
    demo_dispatchers()
    time.sleep(0.5)
    demo_cps_compiler_desugar()
    print(f"\n{Color.BOLD}{Color.GREEN}=== Seluruh Simulasi Konsep Inti Coroutines Selesai! ==={Color.RESET}\n")


def main() -> None:
    display_header()
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_all()
        return

    print("Pilih skenario simulasi:")
    print(" 1. Structured Concurrency & Job Cancellation Cascade")
    print(" 2. Async / Await Concurrent Processing")
    print(" 3. Dispatchers & Thread Hopping (IO -> Main)")
    print(" 4. Suspend Function CPS State Machine (Compiler De-sugaring)")
    print(" 5. Jalankan Semua Skenario Sekaligus")
    print(" 0. Keluar")

    choice = input(f"\n{Color.WHITE}Masukkan pilihan [1-5 / 0]: {Color.RESET}").strip()
    if choice == "1":
        demo_structured_concurrency()
    elif choice == "2":
        demo_async_await()
    elif choice == "3":
        demo_dispatchers()
    elif choice == "4":
        demo_cps_compiler_desugar()
    elif choice == "5" or choice == "":
        run_all()
    else:
        print("Keluar dari simulator.")


if __name__ == "__main__":
    main()

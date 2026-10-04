#!/usr/bin/env python3
"""
Lab: Asynchronous Runtime Internals & Event Loop Orchestration
Category: 02-Programming-Languages | Topic: JavaScript
Simulator: High-Fidelity Node.js / V8 Event Loop Engine with Libuv Phase Emulation
"""

import heapq
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any, List, Optional


# --- ANSI Formatting Helpers ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    RED = "\033[91m"
    GRAY = "\033[90m"


class Phase(Enum):
    SYNC_STACK = auto()
    MICROTASK_TICK = auto()
    MICROTASK_PROMISE = auto()
    TIMERS = auto()
    POLL_IO = auto()
    CHECK_IMMEDIATE = auto()
    CLOSE_CALLBACKS = auto()


@dataclass(order=True)
class TimerEntry:
    due_time_ms: float
    task_id: int
    callback: Callable = field(compare=False)
    name: str = field(compare=False)


@dataclass
class Microtask:
    name: str
    callback: Callable
    is_next_tick: bool = False


class JSRuntimeEngine:
    """
    Simulates a V8 / Libuv hybrid asynchronous JavaScript runtime.
    Features:
      - Call Stack execution
      - process.nextTick Priority Queue
      - Promise (V8 Microtask) Queue
      - Libuv Phases: Timers (min-heap), Poll/IO, Check (setImmediate)
      - Deterministic Virtual Clock
    """

    def __init__(self):
        self.virtual_time_ms: float = 0.0
        self.task_counter: int = 0

        # Queues & Stacks
        self.call_stack: List[str] = []
        self.next_tick_queue: deque[Microtask] = deque()
        self.microtask_queue: deque[Microtask] = deque()
        self.timer_heap: List[TimerEntry] = []
        self.poll_io_queue: deque[tuple[str, Callable]] = deque()
        self.check_queue: deque[tuple[str, Callable]] = deque()

        self.execution_log: List[str] = []

    def log(self, phase: Phase, message: str, color: str = TermColor.RESET):
        timestamp = f"[{self.virtual_time_ms:>6.1f}ms]"
        phase_label = f"[{phase.name:<18}]"
        print(f"{TermColor.GRAY}{timestamp}{TermColor.RESET} {color}{phase_label} {message}{TermColor.RESET}")
        self.execution_log.append(f"{timestamp} {phase.name}: {message}")

    # --- Public JavaScript API Simulators ---

    def sync_eval(self, label: str, fn: Callable):
        """Executes a synchronous script block directly on the Call Stack."""
        self.call_stack.append(label)
        self.log(Phase.SYNC_STACK, f"PUSH frame -> {label}", TermColor.BOLD + TermColor.RED)
        try:
            fn()
        finally:
            popped = self.call_stack.pop()
            self.log(Phase.SYNC_STACK, f"POP  frame <- {popped}", TermColor.DIM + TermColor.RED)

    def next_tick(self, name: str, callback: Callable):
        """Simulates Node.js process.nextTick() - Highest priority microtask."""
        self.task_counter += 1
        self.log(Phase.SYNC_STACK, f"Schedule nextTick: '{name}'", TermColor.MAGENTA)
        self.next_tick_queue.append(Microtask(name=name, callback=callback, is_next_tick=True))

    def promise_then(self, name: str, callback: Callable):
        """Simulates Promise.then() / queueMicrotask() - Standard microtask."""
        self.task_counter += 1
        self.log(Phase.SYNC_STACK, f"Schedule Promise microtask: '{name}'", TermColor.YELLOW)
        self.microtask_queue.append(Microtask(name=name, callback=callback, is_next_tick=False))

    def set_timeout(self, name: str, delay_ms: float, callback: Callable):
        """Simulates setTimeout(fn, delay) stored in Libuv min-heap."""
        self.task_counter += 1
        due = self.virtual_time_ms + max(1.0, delay_ms)  # Libuv minimum timer resolution is 1ms
        entry = TimerEntry(due_time_ms=due, task_id=self.task_counter, callback=callback, name=name)
        heapq.heappush(self.timer_heap, entry)
        self.log(Phase.SYNC_STACK, f"Schedule Timer: '{name}' (due in {delay_ms:.1f}ms)", TermColor.GREEN)

    def set_immediate(self, name: str, callback: Callable):
        """Simulates setImmediate() running in Libuv Check Phase."""
        self.task_counter += 1
        self.log(Phase.SYNC_STACK, f"Schedule setImmediate: '{name}'", TermColor.CYAN)
        self.check_queue.append((name, callback))

    def simulate_io_completion(self, name: str, callback: Callable):
        """Simulates an asynchronous I/O completion placing a callback in the Poll queue."""
        self.task_counter += 1
        self.log(Phase.SYNC_STACK, f"Queue I/O callback: '{name}'", TermColor.BLUE)
        self.poll_io_queue.append((name, callback))

    # --- Event Loop Processing Internals ---

    def _drain_microtasks(self) -> bool:
        """
        Drains the Microtask Queues completely before next phase.
        Node.js prioritizes process.nextTick over Promise microtasks.
        """
        executed_any = False

        while self.next_tick_queue or self.microtask_queue:
            executed_any = True
            # Step 1: Drain process.nextTick until exhausted
            while self.next_tick_queue:
                task = self.next_tick_queue.popleft()
                self.log(Phase.MICROTASK_TICK, f"Execute: {task.name}", TermColor.MAGENTA)
                task.callback()

            # Step 2: Process a Promise microtask
            if self.microtask_queue:
                task = self.microtask_queue.popleft()
                self.log(Phase.MICROTASK_PROMISE, f"Execute: {task.name}", TermColor.YELLOW)
                task.callback()
                # Microtask could have scheduled nextTick, loop back to handle high priority.

        return executed_any

    def _process_timers(self):
        """Phase 1: Expire all elapsed timers from the min-heap."""
        while self.timer_heap and self.timer_heap[0].due_time_ms <= self.virtual_time_ms:
            entry = heapq.heappop(self.timer_heap)
            self.log(Phase.TIMERS, f"Fire Timer: '{entry.name}'", TermColor.GREEN)
            entry.callback()
            # In modern Node.js (v11+), microtasks run between individual macrotask callbacks
            self._drain_microtasks()

    def _process_poll_io(self):
        """Phase 2: Poll I/O callbacks."""
        batch_size = len(self.poll_io_queue)
        for _ in range(batch_size):
            name, callback = self.poll_io_queue.popleft()
            self.log(Phase.POLL_IO, f"Process I/O: '{name}'", TermColor.BLUE)
            callback()
            self._drain_microtasks()

    def _process_check(self):
        """Phase 3: Check phase (setImmediate callbacks)."""
        batch_size = len(self.check_queue)
        for _ in range(batch_size):
            name, callback = self.check_queue.popleft()
            self.log(Phase.CHECK_IMMEDIATE, f"Process Immediate: '{name}'", TermColor.CYAN)
            callback()
            self._drain_microtasks()

    def has_pending_work(self) -> bool:
        """Determines if the event loop still has scheduled tasks to orchestrate."""
        return bool(
            self.timer_heap
            or self.poll_io_queue
            or self.check_queue
            or self.next_tick_queue
            or self.microtask_queue
        )

    def run_event_loop(self):
        """
        Executes the Libuv Event Loop orchestration ticks until all tasks are drained.
        """
        print(f"\n{TermColor.BOLD}{'='*60}")
        print("          ENTERING ASYNCHRONOUS EVENT LOOP TICK")
        print(f"{'='*60}{TermColor.RESET}\n")

        # Initial drain of microtasks registered during top-level sync execution
        self._drain_microtasks()

        loop_iteration = 0
        while self.has_pending_work():
            loop_iteration += 1

            # Phase 1: Timers
            self._process_timers()

            # Phase 2: Poll / I/O
            self._process_poll_io()

            # Phase 3: Check / setImmediate
            self._process_check()

            # Virtual Time Forwarding:
            # If no immediate/IO was processed and timers exist in future, warp clock to next timer.
            if not self.check_queue and not self.poll_io_queue and self.timer_heap:
                next_timer = self.timer_heap[0].due_time_ms
                if next_timer > self.virtual_time_ms:
                    advance_delta = next_timer - self.virtual_time_ms
                    self.virtual_time_ms = next_timer
                    self.log(Phase.TIMERS, f"Virtual clock fast-forwarded (+{advance_delta:.1f}ms)", TermColor.GRAY)

        print(f"\n{TermColor.BOLD}{'='*60}")
        print(f"  EVENT LOOP TERMINATED SAFELY: {loop_iteration} Iterations Completed")
        print(f"{'='*60}{TermColor.RESET}\n")


# --- Demonstration Scenario ---
def main():
    runtime = JSRuntimeEngine()

    def complex_scenario():
        print(f"{TermColor.BOLD}--- Step 1: Evaluating Main Script (Synchronous) ---{TermColor.RESET}")

        # Top-level sync code
        runtime.sync_eval(
            "main_script.js",
            lambda: [
                runtime.set_timeout("Timer-0ms (A)", 0.0, lambda: runtime.next_tick("Nested-Tick-in-TimerA", lambda: None)),
                runtime.set_timeout("Timer-50ms (B)", 50.0, lambda: None),
                runtime.set_immediate("Immediate (A)", lambda: [
                    runtime.promise_then("Promise-Inside-Immediate", lambda: None)
                ]),
                runtime.promise_then("Promise.resolve (1)", lambda: [
                    runtime.next_tick("Tick-Inside-Promise-1", lambda: None)
                ]),
                runtime.next_tick("process.nextTick (1)", lambda: [
                    runtime.promise_then("Promise-Inside-Tick-1", lambda: None)
                ]),
                runtime.simulate_io_completion("FS:ReadFileBuffer", lambda: [
                    runtime.set_immediate("Immediate-Inside-IO", lambda: None),
                    runtime.set_timeout("Timer-Inside-IO", 0.0, lambda: None)
                ]),
                runtime.promise_then("Promise.resolve (2)", lambda: None),
                runtime.next_tick("process.nextTick (2)", lambda: None)
            ]
        )

    complex_scenario()
    runtime.run_event_loop()


if __name__ == "__main__":
    main()
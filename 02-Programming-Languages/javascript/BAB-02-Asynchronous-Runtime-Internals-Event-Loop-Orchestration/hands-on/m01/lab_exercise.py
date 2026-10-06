#!/usr/bin/env python3
"""
JavaScript Asynchronous Runtime Internals & Event Loop Orchestrator
BAB-02: Asynchronous Runtime Internals & Event Loop Orchestration

Simulasi teknis interaktif Call Stack, Web APIs / Background Workers,
Microtask Queue (Jobs), dan Macrotask Queue (Tasks) dengan visualisasi ANSI.
"""

from __future__ import annotations
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Deque, Dict, List, Optional


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
    BG_CYAN = "\033[46m"


class TaskType(Enum):
    SYNC = auto()
    MICRO = auto()      # Promise.then, queueMicrotask, MutationObserver
    NEXT_TICK = auto()  # Node.js process.nextTick (higher microtask priority)
    MACRO = auto()      # setTimeout, setInterval, setImmediate, I/O


@dataclass
class RuntimeTask:
    task_id: str
    name: str
    task_type: TaskType
    action: Callable[[], Optional[str]]
    delay_ms: int = 0
    registered_at_tick: int = 0

    def __repr__(self) -> str:
        return f"{self.name} [{self.task_type.name}]"


class V8CallStack:
    """Simulasi Call Stack (LIFO) V8 Execution Context."""
    def __init__(self) -> None:
        self.frames: List[RuntimeTask] = []

    def push(self, frame: RuntimeTask) -> None:
        self.frames.append(frame)

    def pop(self) -> Optional[RuntimeTask]:
        return self.frames.pop() if self.frames else None

    def peek(self) -> Optional[RuntimeTask]:
        return self.frames[-1] if self.frames else None

    def is_empty(self) -> bool:
        return len(self.frames) == 0

    def render(self) -> str:
        if self.is_empty():
            return f"{Color.DIM}<Empty Stack>{Color.RESET}"
        return " | ".join(f"{Color.CYAN}[{f.name}]{Color.RESET}" for f in reversed(self.frames))


class WebApiTimerHost:
    """Simulasi Browser Web APIs / Libuv Threadpool Timer Resolution."""
    def __init__(self) -> None:
        self.active_timers: List[RuntimeTask] = []

    def register(self, task: RuntimeTask) -> None:
        self.active_timers.append(task)

    def tick(self, current_tick: int) -> List[RuntimeTask]:
        ready: List[RuntimeTask] = []
        remaining: List[RuntimeTask] = []
        for timer in self.active_timers:
            if current_tick - timer.registered_at_tick >= max(1, timer.delay_ms // 10):
                ready.append(timer)
            else:
                remaining.append(timer)
        self.active_timers = remaining
        return ready

    def render(self) -> str:
        if not self.active_timers:
            return f"{Color.DIM}<Idle APIs>{Color.RESET}"
        return ", ".join(f"{Color.YELLOW}{t.name}({t.delay_ms}ms){Color.RESET}" for t in self.active_timers)


class JSEventLoopEngine:
    """Event Loop Orchestrator dengan prioritas Microtask Checkpoint."""
    def __init__(self, step_delay: float = 0.25) -> None:
        self.stack = V8CallStack()
        self.next_tick_queue: Deque[RuntimeTask] = deque()
        self.microtask_queue: Deque[RuntimeTask] = deque()
        self.macrotask_queue: Deque[RuntimeTask] = deque()
        self.web_api = WebApiTimerHost()
        self.tick_count = 0
        self.logs: List[str] = []
        self.step_delay = step_delay

    def log(self, text: str) -> None:
        self.logs.append(text)

    def schedule_sync(self, name: str, output: str) -> None:
        self.stack.push(
            RuntimeTask(f"sync-{name}", name, TaskType.SYNC, lambda: self.log(output))
        )

    def schedule_next_tick(self, name: str, output: str) -> None:
        self.next_tick_queue.append(
            RuntimeTask(f"tick-{name}", name, TaskType.NEXT_TICK, lambda: self.log(output))
        )

    def schedule_microtask(self, name: str, output: str) -> None:
        self.microtask_queue.append(
            RuntimeTask(f"micro-{name}", name, TaskType.MICRO, lambda: self.log(output))
        )

    def schedule_timeout(self, name: str, output: str, delay_ms: int = 0) -> None:
        task = RuntimeTask(
            f"macro-{name}",
            name,
            TaskType.MACRO,
            lambda: self.log(output),
            delay_ms=delay_ms,
            registered_at_tick=self.tick_count,
        )
        self.web_api.register(task)

    def display_state(self, phase_name: str) -> None:
        print("\033[2J\033[H", end="")
        print(f"{Color.BOLD}{Color.BG_BLUE} === JS EVENT LOOP RUNTIME INTERNALS (Tick: {self.tick_count}) === {Color.RESET}")
        print(f"Phase       : {Color.BOLD}{Color.WHITE}{phase_name}{Color.RESET}")
        print(f"Call Stack  : {self.stack.render()}")
        print(f"NextTick Q  : {self._render_queue(self.next_tick_queue, Color.MAGENTA)}")
        print(f"Microtask Q : {self._render_queue(self.microtask_queue, Color.GREEN)}")
        print(f"Macrotask Q : {self._render_queue(self.macrotask_queue, Color.YELLOW)}")
        print(f"Web APIs    : {self.web_api.render()}")
        print(f"{Color.DIM}{'-' * 60}{Color.RESET}")
        print(f"{Color.BOLD}Console Stdout Logs:{Color.RESET}")
        if not self.logs:
            print(f"  {Color.DIM}(No output yet){Color.RESET}")
        else:
            for item in self.logs:
                print(f"  {Color.GREEN}➜ {item}{Color.RESET}")
        print(f"{Color.DIM}{'=' * 60}{Color.RESET}")
        if self.step_delay > 0:
            time.sleep(self.step_delay)

    def _render_queue(self, q: Deque[RuntimeTask], color: str) -> str:
        if not q:
            return f"{Color.DIM}<Empty>{Color.RESET}"
        return " <- ".join(f"{color}[{t.name}]{Color.RESET}" for t in q)

    def run_call_stack(self) -> None:
        while not self.stack.is_empty():
            task = self.stack.pop()
            if task:
                self.display_state(f"Executing Sync Stack Frame: {task.name}")
                task.action()
                self.display_state(f"Completed Frame: {task.name}")

    def drain_microtasks(self) -> None:
        """Microtask Checkpoint: process.nextTick didahulukan, lalu Microtasks."""
        while self.next_tick_queue or self.microtask_queue:
            while self.next_tick_queue:
                task = self.next_tick_queue.popleft()
                self.display_state(f"Draining nextTick: {task.name}")
                task.action()

            while self.microtask_queue:
                task = self.microtask_queue.popleft()
                self.display_state(f"Draining Microtask (Promise/QueueMicrotask): {task.name}")
                task.action()
                if self.next_tick_queue:
                    break

    def step(self) -> bool:
        self.tick_count += 1
        ready_timers = self.web_api.tick(self.tick_count)
        for t in ready_timers:
            self.macrotask_queue.append(t)

        if not self.stack.is_empty():
            self.run_call_stack()
            return True

        if self.next_tick_queue or self.microtask_queue:
            self.drain_microtasks()
            return True

        if self.macrotask_queue:
            macro = self.macrotask_queue.popleft()
            self.display_state(f"Event Loop Step: Picking 1 Macrotask ({macro.name})")
            macro.action()
            self.display_state(f"Completed Macrotask ({macro.name}) -> Triggering Microtask Checkpoint")
            self.drain_microtasks()
            return True

        if self.web_api.active_timers:
            self.display_state("Waiting for Web API background timers/I-O...")
            return True

        return False

    def run_all(self, max_ticks: int = 100) -> None:
        self.display_state("Initial Script Execution (Global Context Entry)")
        count = 0
        while self.step() and count < max_ticks:
            count += 1
        self.display_state("Event Loop Settled (No Pending Tasks)")


def run_canonical_scenario(delay: float = 0.3) -> None:
    """
    Skenario Kanonikal V8 / Node.js:
    console.log('1: Sync Start')
    setTimeout(() => console.log('2: Timeout 0ms'), 0)
    process.nextTick(() => console.log('3: process.nextTick'))
    Promise.resolve().then(() => console.log('4: Promise.then Microtask'))
    queueMicrotask(() => console.log('5: queueMicrotask'))
    console.log('6: Sync End')
    """
    engine = JSEventLoopEngine(step_delay=delay)
    print(f"{Color.BOLD}{Color.CYAN}Loading Canonical Event Loop Execution Scenario...{Color.RESET}")

    engine.schedule_timeout("setTimeout_0ms", "2: Timeout 0ms (Macrotask)", delay_ms=0)
    engine.schedule_next_tick("process_nextTick", "3: process.nextTick (High-pri Microtask)")
    engine.schedule_microtask("Promise_resolve_then", "4: Promise.then (Standard Microtask)")
    engine.schedule_microtask("queueMicrotask", "5: queueMicrotask (Standard Microtask)")
    engine.schedule_sync("Sync_Start", "1: Sync Start (Call Stack Frame 1)")
    engine.schedule_sync("Sync_End", "6: Sync End (Call Stack Frame 2)")

    engine.run_all()


def run_nested_microtask_scenario(delay: float = 0.3) -> None:
    """Skenario Starvation / Nested Microtask Checkpoint."""
    engine = JSEventLoopEngine(step_delay=delay)

    def nested_factory():
        engine.log("1: Outer Promise Settled")
        engine.schedule_microtask("Nested_Microtask_1", "2: Injected Nested Promise Microtask")

    task = RuntimeTask("Outer_Promise", "Outer_Promise", TaskType.MICRO, nested_factory)
    engine.microtask_queue.append(task)
    engine.schedule_timeout("Delayed_Macrotask", "3: Delayed Macrotask Completed", delay_ms=0)
    engine.schedule_sync("Sync_Bootstrap", "0: Sync Bootstrap Execution")

    engine.run_all()


def main() -> None:
    print(f"{Color.BOLD}{Color.CYAN}=============================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} JS Asynchronous Runtime Internals & Event Loop Simulator     {Color.RESET}")
    print(f"{Color.DIM} Lab Exercise: Microtask Starvation, Macrotasks, Call Stack  {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}=============================================================={Color.RESET}")
    print("1. Jalankan Skenario Kanonikal (Sync vs nextTick vs Promise vs Timer)")
    print("2. Jalankan Skenario Nested Microtask (Microtask Drain Priority)")
    print("3. Jalankan Fast Run (Semua skenario tanpa delay)")

    choice = input(f"{Color.YELLOW}Pilih opsi [1-3, default=1]: {Color.RESET}").strip()
    if choice == "2":
        run_nested_microtask_scenario(delay=0.3)
    elif choice == "3":
        run_canonical_scenario(delay=0.0)
    else:
        run_canonical_scenario(delay=0.3)

    print(f"\n{Color.BOLD}{Color.GREEN}✔ Simulasi Event Loop Berhasil Diselesaikan!{Color.RESET}\n")


if __name__ == "__main__":
    main()

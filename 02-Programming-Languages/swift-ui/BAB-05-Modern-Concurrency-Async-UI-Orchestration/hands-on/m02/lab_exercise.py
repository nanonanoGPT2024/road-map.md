#!/usr/bin/env python3
"""
Lab Hands-on: Modern Concurrency & Async UI Orchestration (SwiftUI Architecture in Python)
Simulates:
  - @MainActor isolation & thread-affinity verification
  - Structured Concurrency: TaskGroups, cooperative cancellation, and task priority
  - View Lifecycle-bound async tasks (.task modifier simulation)
  - Reactive state reconciliation pipeline with UI frame rendering
"""

import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum

# --- ANSI Terminal Colors ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_BG_DARK = "\033[100m"

class TaskPriority(Enum):
    BACKGROUND = 1
    USER_INITIATED = 2
    HIGH = 3

class ActorIsolationViolation(Exception):
    """Raised when a non-isolated thread/coroutine modifies MainActor state directly."""
    pass

class MainActor:
    """
    Simulates Swift's @MainActor runtime. Ensures that any mutation targeting
    UI-bound state is strictly executed on the simulated Main Execution Context.
    """
    _main_thread_id: Optional[int] = None
    _active_token: Optional[str] = None

    @classmethod
    def register_main_context(cls, token: str = "MAIN_RUNLOOP"):
        cls._active_token = token

    @classmethod
    def assert_isolated(cls, context_token: str):
        if context_token != cls._active_token:
            raise ActorIsolationViolation(
                f"[PURPLE WARNING] MainActor isolation breached! "
                f"Attempted write from context: '{context_token}' instead of '{cls._active_token}'"
            )

    @classmethod
    async def run(cls, coro_func, *args, **kwargs):
        """Dispatches work explicitly onto the MainActor context."""
        # Yield control to simulate event-loop hopping
        await asyncio.sleep(0.001)
        return await coro_func("MAIN_RUNLOOP", *args, **kwargs)


@dataclass
class UIState:
    profile_name: str = "Guest"
    metrics_count: int = 0
    notifications: List[str] = field(default_factory=list)
    is_loading: bool = False
    render_version: int = 0


class ObservableViewModel:
    """
    Models a SwiftUI ObservableObject / @Observable class.
    Manages state mutation through simulated @MainActor constraints.
    """
    def __init__(self):
        self._state = UIState()
        self._observers: Set[asyncio.Queue] = set()

    @property
    def state(self) -> UIState:
        return self._state

    def register_observer(self, queue: asyncio.Queue):
        self._observers.add(queue)

    def unregister_observer(self, queue: asyncio.Queue):
        self._observers.discard(queue)

    async def mutate_state(self, caller_context: str, **kwargs):
        """Protected mutator: enforces actor isolation check."""
        MainActor.assert_isolated(caller_context)
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
        self._state.render_version += 1
        
        # Broadcast mutation to UI renderer queue
        for q in self._observers:
            await q.put(self._state)


class AsyncNetworkService:
    """Mock external services with non-deterministic latency and cancellation points."""
    
    @staticmethod
    async def fetch_profile(user_id: int) -> str:
        await asyncio.sleep(0.2)  # Co-operative suspension point
        return f"User_#0{user_id}_SwiftMaster"

    @staticmethod
    async def fetch_metrics() -> int:
        await asyncio.sleep(0.35)
        return random.randint(1200, 4800)

    @staticmethod
    async def fetch_notifications() -> List[str]:
        # Simulating heavy network request
        for _ in range(3):
            await asyncio.sleep(0.1)  # Checking cancellation token cooperatively
        return ["New PR Review", "Build Succeeded #412", "SwiftUI Conf Announced"]


class SwiftUIComponentSimulator:
    """
    Simulates a SwiftUI View hierarchy handling async lifecycle:
    - .task { await loadData() }
    - Automatic cancellation upon view unmount/dismiss
    - Diff-based View terminal rendering
    """
    def __init__(self, view_id: str, view_model: ObservableViewModel):
        self.view_id = view_id
        self.vm = view_model
        self.render_queue = asyncio.Queue()
        self.active_tasks: List[asyncio.Task] = []
        self._is_mounted = False

    async def mount(self):
        self._is_mounted = True
        self.vm.register_observer(self.render_queue)
        print(f"{CLR_CYAN}[View::{self.view_id}]{CLR_RESET} Initializing and mounting to hierarchy...")
        
        # Spawn UI Renderer Consumer
        asyncio.create_task(self._ui_render_loop())
        
        # Trigger SwiftUI style .task modifier
        task = asyncio.create_task(self._on_appear_task())
        self.active_tasks.append(task)

    async def unmount(self):
        """Simulates View navigation pop: all child tasks MUST cancel automatically."""
        print(f"\n{CLR_YELLOW}[View::{self.view_id}]{CLR_RESET} Unmounting component (Navigating away)...")
        self._is_mounted = False
        self.vm.unregister_observer(self.render_queue)
        for task in self.active_tasks:
            if not task.done():
                task.cancel()
        print(f"{CLR_RED}[CancellationEngine]{CLR_RESET} Cancelled {len(self.active_tasks)} active child task(s).")

    async def _ui_render_loop(self):
        """Simulates View body re-evaluation upon Published/Observable property changes."""
        while self._is_mounted:
            try:
                state: UIState = await asyncio.wait_for(self.render_queue.get(), timeout=0.1)
                self._render_view(state)
                self.render_queue.task_done()
            except asyncio.TimeoutError:
                continue

    def _render_view(self, state: UIState):
        """Terminal visualizer for component rendering."""
        status_tag = f"{CLR_YELLOW}LOADING{CLR_RESET}" if state.is_loading else f"{CLR_GREEN}STABLE{CLR_RESET}"
        print(f"\n{CLR_BG_DARK}┌──────────────── VIEW FRAME BUFFER (v{state.render_version:02d}) ────────────────┐{CLR_RESET}")
        print(f"│ Status:  [{status_tag}]")
        print(f"│ Profile: {CLR_BOLD}{state.profile_name}{CLR_RESET}")
        print(f"│ Metrics: {CLR_CYAN}{state.metrics_count} ops/s{CLR_RESET}")
        print(f"│ Notifications ({len(state.notifications)}):")
        for note in state.notifications:
            print(f"│   - {note}")
        print(f"{CLR_BG_DARK}└────────────────────────────────────────────────────────┘{CLR_RESET}")

    async def _on_appear_task(self):
        """Simulates SwiftUI `.task(priority:)` executing structured concurrent calls."""
        print(f"{CLR_BLUE}[TaskGroup]{CLR_RESET} Spawning Structured Child Tasks...")
        
        # 1. Update loading state on MainActor
        await MainActor.run(self.vm.mutate_state, is_loading=True)

        try:
            # 2. Emulate Swift `withTaskGroup(of:returning:)` pattern
            # Concurrently dispatch profile, metrics, and notification queries
            t1 = asyncio.create_task(AsyncNetworkService.fetch_profile(88))
            t2 = asyncio.create_task(AsyncNetworkService.fetch_metrics())
            t3 = asyncio.create_task(AsyncNetworkService.fetch_notifications())
            
            # Cooperative Task awaiting: updates arrive as soon as they settle
            results = await asyncio.gather(t1, t2, t3)
            
            profile, metrics, notifications = results
            
            # 3. Batch commit results back onto @MainActor
            print(f"{CLR_MAGENTA}[MainActor]{CLR_RESET} Marshalling results back to Main Context UI...")
            await MainActor.run(
                self.vm.mutate_state,
                profile_name=profile,
                metrics_count=metrics,
                notifications=notifications,
                is_loading=False
            )

        except asyncio.CancelledError:
            print(f"{CLR_RED}[Task]{CLR_RESET} TaskGroup cancelled midway! Releasing network sockets...")
            raise


async def demonstrate_isolation_violation(vm: ObservableViewModel):
    """Demonstrates runtime detection when mutating state outside the MainActor."""
    print(f"\n{CLR_BOLD}--- Scenario 1: Simulating Actor Isolation Violation ---{CLR_RESET}")
    print("Spawning a background thread/task directly writing to Observable state...")
    await asyncio.sleep(0.05)
    
    try:
        # Deliberately using a 'BACKGROUND_DISPATCH_QUEUE' token
        await vm.mutate_state("BACKGROUND_DISPATCH_QUEUE", profile_name="HackerProfile")
    except ActorIsolationViolation as aiv:
        print(f"{CLR_RED}Caught expected violation:{CLR_RESET} {aiv}")
        print(f"{CLR_GREEN}✓ State safety preserved. No out-of-band corruption.{CLR_RESET}")


async def main():
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}  SwiftUI Modern Concurrency & Async UI Orchestration Simulator       {CLR_RESET}")
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}\n")
    
    MainActor.register_main_context("MAIN_RUNLOOP")
    shared_view_model = ObservableViewModel()

    # Step 1: Prove Actor Boundary Enforcement
    await demonstrate_isolation_violation(shared_view_model)

    # Step 2: Normal Lifecycle Mount and Structured Fetching
    print(f"\n{CLR_BOLD}--- Scenario 2: View Lifecycle & TaskGroup Concurrency ---{CLR_RESET}")
    view = SwiftUIComponentSimulator(view_id="DashboardHomeView", view_model=shared_view_model)
    await view.mount()

    # Wait for the async task group to complete and render
    await asyncio.sleep(0.45)

    # Step 3: Simulate Immediate Dismissal & Cooperative Cancellation
    print(f"\n{CLR_BOLD}--- Scenario 3: Screen Navigation Pop & Task Cancellation ---{CLR_RESET}")
    # Mount a second view that gets cancelled before tasks finish
    detail_view = SwiftUIComponentSimulator(view_id="HeavyDetailView", view_model=shared_view_model)
    await detail_view.mount()
    
    # Abrupt unmount after only 50ms while network services are mid-flight
    await asyncio.sleep(0.05)
    await detail_view.unmount()
    
    # Grace period to let async cancellations settle
    await asyncio.sleep(0.2)
    print(f"\n{CLR_GREEN}Lab run completed successfully with verified concurrency guarantees.{CLR_RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
        exit(0)
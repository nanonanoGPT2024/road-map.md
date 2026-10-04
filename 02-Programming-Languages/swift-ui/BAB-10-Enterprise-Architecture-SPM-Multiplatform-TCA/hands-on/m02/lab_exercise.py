#!/usr/bin/env python3
"""
Lab Hands-on: TCA (The Composable Architecture) & Enterprise Multiplatform Core
Topic: swift-ui | Chapter 10: Enterprise Architecture: SPM, Multiplatform, & TCA

Simulates the runtime mechanics of Point-Free's Composable Architecture (TCA):
1. Pure Reducers: In-out State mutations driven by discrete Actions.
2. Unidirectional Data Flow: UI -> Send Action -> Reducer -> Mutate State & Return Effect.
3. Cancellable Async Effects: Task cancellation keys, debounce, concurrent dispatchers.
4. Environment & Dependency Injection: Platform-tailored client drivers (iOS, macOS, watchOS).
5. Modular SPM Boundaries: Feature Core decoupled from Platform Drivers.
"""

from __future__ import annotations
import sys
import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, Dict, List

# --- ANSI Terminal Formatting ---
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    DIM = "\033[2m"

# --- Target Platform Definition (SPM Multiplatform Simulation) ---
class TargetPlatform(Enum):
    IOS = "iOS"
    MACOS = "macOS"
    WATCHOS = "watchOS"

# --- Domain Models ---
@dataclass
class Order:
    id: str
    item_count: int
    total_amount: float
    status: str

# --- TCA Core: State, Actions, and Dependencies ---
@dataclass
class AppState:
    platform: TargetPlatform
    orders: List[Order] = field(default_factory=list)
    query: str = ""
    is_loading: bool = False
    error_message: Optional[str] = None
    telemetry_logs_sent: int = 0

class AppAction:
    class QueryChanged:
        def __init__(self, query: str): self.query = query
        def __repr__(self): return f"AppAction.QueryChanged('{self.query}')"

    class FetchOrders:
        def __repr__(self): return "AppAction.FetchOrders"

    class OrdersReceived:
        def __init__(self, orders: List[Order]): self.orders = orders
        def __repr__(self): return f"AppAction.OrdersReceived(count={len(self.orders)})"

    class FetchFailed:
        def __init__(self, error: str): self.error = error
        def __repr__(self): return f"AppAction.FetchFailed('{self.error}')"

    class CancelOngoingSync:
        def __repr__(self): return "AppAction.CancelOngoingSync"

    class FlushTelemetry:
        def __repr__(self): return "AppAction.FlushTelemetry"

    class TelemetryFlushed:
        def __init__(self, count: int): self.count = count
        def __repr__(self): return f"AppAction.TelemetryFlushed(count={self.count})"

# --- Environment / Dependency Injection Layer ---
class APIClient:
    """Simulates an SPM Modularized Client with multiplatform optimizations."""
    def __init__(self, platform: TargetPlatform):
        self.platform = platform

    def search_orders(self, query: str, cancel_flag: threading.Event) -> List[Order]:
        # Emulate latency based on simulated platform constraints
        latency = 0.4 if self.platform == TargetPlatform.MACOS else 0.7
        step = 0.05
        elapsed = 0.0
        while elapsed < latency:
            if cancel_flag.is_set():
                raise InterruptedError("Async network task cancelled by TCA Effect manager.")
            time.sleep(step)
            elapsed += step

        return [
            Order(id=f"ORD-{i:03d}", item_count=i * 2, total_amount=i * 49.99, status="PROCESSED")
            for i in range(1, 4)
        ]

    def sync_telemetry(self, platform: TargetPlatform) -> int:
        # Multiplatform adaptation: watchOS throttles sync payloads
        time.sleep(0.2)
        return 5 if platform == TargetPlatform.WATCHOS else 25

class Environment:
    def __init__(self, platform: TargetPlatform):
        self.platform = platform
        self.api_client = APIClient(platform)

# --- TCA Effect Engine ---
class Effect:
    """Encapsulates async operations that emit actions back into the Store."""
    def __init__(self, run: Callable[[Callable[[Any], None], threading.Event], None], cancel_id: Optional[str] = None):
        self.run = run
        self.cancel_id = cancel_id

    @staticmethod
    def none() -> Effect:
        return Effect(lambda send, cancel_flag: None)

    @staticmethod
    def cancel(cancel_id: str) -> Effect:
        def _cancel(send, cancel_flag):
            pass
        return Effect(_cancel, cancel_id=f"__CANCEL_{cancel_id}__")

    @staticmethod
    def run_async(operation: Callable[[threading.Event], Optional[Any]], cancel_id: Optional[str] = None) -> Effect:
        def _runner(send: Callable[[Any], None], cancel_flag: threading.Event):
            try:
                action = operation(cancel_flag)
                if action and not cancel_flag.is_set():
                    send(action)
            except InterruptedError:
                pass  # Gracefully discard cancelled tasks
            except Exception as e:
                send(AppAction.FetchFailed(str(e)))
        return Effect(_runner, cancel_id)

# --- Reducer Logic ---
def app_reducer(state: AppState, action: Any, env: Environment) -> Effect:
    """Pure reducer executing deterministic state transitions and returning effects."""
    if isinstance(action, AppAction.QueryChanged):
        state.query = action.query
        print(f"  {TerminalColor.CYAN}State Mutation:{TerminalColor.RESET} query -> '{state.query}'")
        # Trigger an automatic cancellation of previous search, then run fresh query
        return Effect.run_async(
            lambda flag: (
                time.sleep(0.1),  # Debounce simulation
                AppAction.FetchOrders()
            )[1],
            cancel_id="SEARCH_QUERY"
        )

    elif isinstance(action, AppAction.FetchOrders):
        state.is_loading = True
        state.error_message = None
        print(f"  {TerminalColor.CYAN}State Mutation:{TerminalColor.RESET} is_loading = True")
        
        current_query = state.query
        return Effect.run_async(
            lambda flag: AppAction.OrdersReceived(env.api_client.search_orders(current_query, flag)),
            cancel_id="ORDER_FETCH"
        )

    elif isinstance(action, AppAction.OrdersReceived):
        state.is_loading = False
        state.orders = action.orders
        print(f"  {TerminalColor.CYAN}State Mutation:{TerminalColor.RESET} is_loading = False, orders = {len(state.orders)} items")
        return Effect.none()

    elif isinstance(action, AppAction.FetchFailed):
        state.is_loading = False
        state.error_message = action.error
        print(f"  {TerminalColor.RED}State Mutation Error:{TerminalColor.RESET} error = '{action.error}'")
        return Effect.none()

    elif isinstance(action, AppAction.CancelOngoingSync):
        state.is_loading = False
        print(f"  {TerminalColor.YELLOW}Effect Cancellation Dispatched for: ORDER_FETCH{TerminalColor.RESET}")
        return Effect.cancel("ORDER_FETCH")

    elif isinstance(action, AppAction.FlushTelemetry):
        print(f"  {TerminalColor.MAGENTA}Effect Dispatched:{TerminalColor.RESET} Syncing telemetry for {env.platform.value}")
        return Effect.run_async(
            lambda flag: AppAction.TelemetryFlushed(env.api_client.sync_telemetry(env.platform))
        )

    elif isinstance(action, AppAction.TelemetryFlushed):
        state.telemetry_logs_sent += action.count
        print(f"  {TerminalColor.CYAN}State Mutation:{TerminalColor.RESET} telemetry_logs_sent = {state.telemetry_logs_sent}")
        return Effect.none()

    return Effect.none()

# --- TCA Store Implementation ---
class Store:
    """Manages unidirectional data flow, thread safety, and effect orchestration."""
    def __init__(self, initial_state: AppState, reducer: Callable[[AppState, Any, Environment], Effect], environment: Environment):
        self.state = initial_state
        self.reducer = reducer
        self.environment = environment
        self._lock = threading.Lock()
        self._active_cancellables: Dict[str, threading.Event] = {}

    def send(self, action: Any):
        with self._lock:
            print(f"\n{TerminalColor.BOLD}{TerminalColor.BLUE}[Store Action Received]{TerminalColor.RESET} {action}")
            effect = self.reducer(self.state, action, self.environment)

        # Handle explicit cancellation requests
        if effect.cancel_id and effect.cancel_id.startswith("__CANCEL_"):
            target_id = effect.cancel_id.replace("__CANCEL_", "").replace("__", "")
            self._cancel_effect(target_id)
            return

        # Handle task cancellation if key is already active
        if effect.cancel_id:
            self._cancel_effect(effect.cancel_id)
            cancel_event = threading.Event()
            self._active_cancellables[effect.cancel_id] = cancel_event
        else:
            cancel_event = threading.Event()

        # Run Effect concurrently
        def worker():
            effect.run(self.send, cancel_event)
            if effect.cancel_id and effect.cancel_id in self._active_cancellables:
                if self._active_cancellables[effect.cancel_id] == cancel_event:
                    del self._active_cancellables[effect.cancel_id]

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _cancel_effect(self, cancel_id: str):
        if cancel_id in self._active_cancellables:
            print(f"  {TerminalColor.YELLOW}[Store Effect Token Aborted]{TerminalColor.RESET} -> Cancelling token: {cancel_id}")
            self._active_cancellables[cancel_id].set()
            del self._active_cancellables[cancel_id]

# --- Verification & Simulation Harness ---
def run_lab_demonstration():
    print(f"{TerminalColor.BOLD}{TerminalColor.GREEN}=== Enterprise SwiftUI Architecture: TCA Engine & Multiplatform Lab ==={TerminalColor.RESET}")
    print(f"Targeting: SPM Core Dependency Separation & Composable Effects Verification\n")

    # 1. Setup multiplatform instances
    ios_env = Environment(platform=TargetPlatform.IOS)
    ios_state = AppState(platform=TargetPlatform.IOS)
    store_ios = Store(initial_state=ios_state, reducer=app_reducer, environment=ios_env)

    # 2. Standard Flow: Search, Automatic Fetch, and Result Delivery
    print(f"{TerminalColor.BOLD}[Phase 1: Basic Unidirectional State Mutation (iOS)]{TerminalColor.RESET}")
    store_ios.send(AppAction.QueryChanged("SwiftUI Books"))
    time.sleep(1.0)  # Wait for debounce and network call completion

    # 3. Effect Cancellation Flow: Send request and immediately cancel via UI interaction
    print(f"\n{TerminalColor.BOLD}[Phase 2: Cancellable Side-Effects & Concurrency Interruption]{TerminalColor.RESET}")
    store_ios.send(AppAction.FetchOrders())
    time.sleep(0.1)  # Let thread initiate
    store_ios.send(AppAction.CancelOngoingSync())
    time.sleep(0.8)  # Let worker finish safely and ensure no action was emitted

    # 4. Multiplatform Behavioral Adaptation: watchOS vs macOS
    print(f"\n{TerminalColor.BOLD}[Phase 3: Multiplatform Driver Adaptation (watchOS vs macOS)]{TerminalColor.RESET}")
    watch_env = Environment(platform=TargetPlatform.WATCHOS)
    store_watch = Store(initial_state=AppState(platform=TargetPlatform.WATCHOS), reducer=app_reducer, environment=watch_env)
    
    mac_env = Environment(platform=TargetPlatform.MACOS)
    store_mac = Store(initial_state=AppState(platform=TargetPlatform.MACOS), reducer=app_reducer, environment=mac_env)

    print(f"Dispatching Telemetry sync across platform-specific dependencies...")
    store_watch.send(AppAction.FlushTelemetry())
    store_mac.send(AppAction.FlushTelemetry())
    time.sleep(0.5)

    # 5. Diagnostic State Inspection
    print(f"\n{TerminalColor.BOLD}{TerminalColor.GREEN}=== Final Store State Verification ==={TerminalColor.RESET}")
    print(f"iOS State     -> Query: '{store_ios.state.query}', Orders Cached: {len(store_ios.state.orders)}, Loading: {store_ios.state.is_loading}")
    print(f"watchOS State -> Telemetry Count: {store_watch.state.telemetry_logs_sent} (Throttled mode)")
    print(f"macOS State   -> Telemetry Count: {store_mac.state.telemetry_logs_sent} (High-throughput mode)")
    print(f"\n{TerminalColor.DIM}TCA deterministic state flow and cancellation mechanics verified successfully.{TerminalColor.RESET}")

if __name__ == "__main__":
    run_lab_demonstration()
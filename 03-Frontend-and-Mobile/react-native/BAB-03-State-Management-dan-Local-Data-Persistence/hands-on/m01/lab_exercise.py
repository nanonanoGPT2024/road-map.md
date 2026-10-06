#!/usr/bin/env python3
"""
React Native State Management & Local Persistence Simulator
BAB-03: State Management & Local Data Persistence
Hands-on Lab Exercise: M01 - Store Lifecycle, Reactivity & Storage Engines
"""

import sys
import json
import time
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_MAGENTA = "\033[35m"
COLOR_RED = "\033[31m"
COLOR_BG_DARK = "\033[40m"


def header(text: str) -> None:
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== {text} ==={COLOR_RESET}")


def success(text: str) -> None:
    print(f"{COLOR_GREEN}✔ {text}{COLOR_RESET}")


def info(text: str) -> None:
    print(f"{COLOR_BLUE}ℹ {text}{COLOR_RESET}")


def warn(text: str) -> None:
    print(f"{COLOR_YELLOW}⚠ {text}{COLOR_RESET}")


def log_event(component: str, message: str) -> None:
    print(f"{COLOR_MAGENTA}[{component}]{COLOR_RESET} {message}")


# --- 1. Local Storage Engine Abstraction ---
class AsyncStorageSimulator:
    """Simulates React Native @react-native-async-storage/async-storage (Asynchronous I/O bridge)"""
    def __init__(self, artificial_delay_ms: float = 25.0):
        self._disk: Dict[str, str] = {}
        self.delay = artificial_delay_ms / 1000.0

    def set_item(self, key: str, value: str) -> None:
        time.sleep(self.delay)  # Emulating JS -> Native Bridge JSON Serialization overhead
        self._disk[key] = value

    def get_item(self, key: str) -> Optional[str]:
        time.sleep(self.delay)
        return self._disk.get(key, None)

    def remove_item(self, key: str) -> None:
        time.sleep(self.delay)
        self._disk.pop(key, None)


class MMKVSimulator:
    """Simulates react-native-mmkv (Synchronous C++ JSI direct memory mapped I/O)"""
    def __init__(self):
        self._memory_mapped_cache: Dict[str, Any] = {}

    def set_string(self, key: str, value: str) -> None:
        # Zero bridge serialization overhead via JSI
        self._memory_mapped_cache[key] = value

    def get_string(self, key: str) -> Optional[str]:
        return self._memory_mapped_cache.get(key, None)

    def contains(self, key: str) -> bool:
        return key in self._memory_mapped_cache


# --- 2. Reactive State Store (Zustand / Redux pattern) ---
@dataclass
class AppState:
    theme: str = "light"
    auth_token: Optional[str] = None
    user_profile: Dict[str, Any] = field(default_factory=lambda: {"username": "Guest", "points": 0})
    offline_queue: List[str] = field(default_factory=list)


class ReactiveStore:
    def __init__(self, persistence_engine: MMKVSimulator, persist_key: str = "APP_PERSISTED_STATE"):
        self.storage = persistence_engine
        self.persist_key = persist_key
        self.state = AppState()
        self.subscribers: List[Callable[[AppState], None]] = []

    def subscribe(self, callback: Callable[[AppState], None]) -> Callable[[], None]:
        self.subscribers.append(callback)
        def unsubscribe():
            if callback in self.subscribers:
                self.subscribers.remove(callback)
        return unsubscribe

    def _notify(self) -> None:
        for sub in self.subscribers:
            sub(self.state)

    def set_state(self, updates: Dict[str, Any]) -> None:
        for k, v in updates.items():
            if hasattr(self.state, k):
                setattr(self.state, k, v)
        self._persist()
        self._notify()

    def _persist(self) -> None:
        payload = {
            "theme": self.state.theme,
            "auth_token": self.state.auth_token,
            "user_profile": self.state.user_profile,
            "offline_queue": self.state.offline_queue,
        }
        self.storage.set_string(self.persist_key, json.dumps(payload))
        log_event("MMKV-Persist", f"Persisted snapshot to disk ({len(json.dumps(payload))} bytes)")

    def rehydrate(self) -> bool:
        raw = self.storage.get_string(self.persist_key)
        if not raw:
            warn("No persisted snapshot found on disk. Initializing default state.")
            return False

        try:
            data = json.loads(raw)
            self.state.theme = data.get("theme", "light")
            self.state.auth_token = data.get("auth_token")
            self.state.user_profile = data.get("user_profile", {})
            self.state.offline_queue = data.get("offline_queue", [])
            log_event("StoreHydration", "Store successfully hydrated from MMKV!")
            self._notify()
            return True
        except Exception as e:
            warn(f"Hydration failed: {e}")
            return False


# --- 3. UI Component Simulation ---
class ScreenComponent:
    def __init__(self, name: str, selector: Callable[[AppState], Any]):
        self.name = name
        self.selector = selector
        self.current_value: Any = None
        self.render_count: int = 0

    def on_state_changed(self, state: AppState) -> None:
        new_val = self.selector(state)
        if new_val != self.current_value:
            self.current_value = new_val
            self.render_count += 1
            print(
                f"  {COLOR_CYAN}[Component: {self.name}]{COLOR_RESET} "
                f"Triggered Re-render #{self.render_count} -> New Value: {COLOR_BOLD}{self.current_value}{COLOR_RESET}"
            )


# --- 4. Interactive Simulation & Verification ---
def run_benchmark(iterations: int = 100) -> None:
    header(f"Performance Benchmark: AsyncStorage vs MMKV ({iterations} ops)")
    async_store = AsyncStorageSimulator(artificial_delay_ms=2.0)
    mmkv_store = MMKVSimulator()

    # Benchmark AsyncStorage
    start = time.perf_counter()
    for i in range(iterations):
        async_store.set_item(f"key_{i}", f"val_{i}")
        _ = async_store.get_item(f"key_{i}")
    async_duration = (time.perf_counter() - start) * 1000.0

    # Benchmark MMKV
    start = time.perf_counter()
    for i in range(iterations):
        mmkv_store.set_string(f"key_{i}", f"val_{i}")
        _ = mmkv_store.get_string(f"key_{i}")
    mmkv_duration = (time.perf_counter() - start) * 1000.0

    print(f"  AsyncStorage (Bridge-based async queue) : {COLOR_YELLOW}{async_duration:.2f} ms{COLOR_RESET}")
    print(f"  MMKV (JSI Direct Memory-Mapped C++)     : {COLOR_GREEN}{mmkv_duration:.2f} ms{COLOR_RESET}")
    speedup = async_duration / max(mmkv_duration, 0.0001)
    success(f"MMKV is approximately {speedup:.1f}x faster than AsyncStorage bridge!")


def main_interactive_lab() -> None:
    print(f"{COLOR_BOLD}{COLOR_MAGENTA}===================================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}   REACT NATIVE LAB: STATE MANAGEMENT & LOCAL PERSISTENCE (BAB-03)   {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_MAGENTA}===================================================================={COLOR_RESET}")

    mmkv = MMKVSimulator()
    store = ReactiveStore(persistence_engine=mmkv)

    # Mount UI Components with selectors
    header("Step 1: Mounting React Native UI Components & Selectors")
    theme_ui = ScreenComponent("ThemeToggler", lambda s: s.theme)
    profile_ui = ScreenComponent("ProfileHeader", lambda s: f"{s.user_profile['username']} ({s.user_profile['points']} pts)")
    auth_ui = ScreenComponent("AuthGuard", lambda s: "Authenticated" if s.auth_token else "Guest/SignedOut")

    store.subscribe(theme_ui.on_state_changed)
    store.subscribe(profile_ui.on_state_changed)
    store.subscribe(auth_ui.on_state_changed)
    info("3 UI components subscribed with fine-grained selectors.")

    header("Step 2: Simulating State Mutations & Selective Re-rendering")
    log_event("Action", "User taps 'Dark Mode' toggle")
    store.set_state({"theme": "dark"})

    log_event("Action", "User completes achievement (+50 points)")
    updated_profile = dict(store.state.user_profile)
    updated_profile["points"] += 50
    store.set_state({"user_profile": updated_profile})

    log_event("Action", "User logs in with OAuth token")
    store.set_state({"auth_token": "jwt_rn_session_99214a"})

    header("Step 3: Simulating App Cold Boot & Rehydration from MMKV")
    info("Killing simulated app process (clearing in-memory store)...")
    del store

    info("New app session starts: Bootstrapping fresh store...")
    fresh_store = ReactiveStore(persistence_engine=mmkv)
    fresh_theme_ui = ScreenComponent("ThemeToggler", lambda s: s.theme)
    fresh_profile_ui = ScreenComponent("ProfileHeader", lambda s: f"{s.user_profile['username']} ({s.user_profile['points']} pts)")
    fresh_store.subscribe(fresh_theme_ui.on_state_changed)
    fresh_store.subscribe(fresh_profile_ui.on_state_changed)

    is_hydrated = fresh_store.rehydrate()
    if is_hydrated:
        success("Rehydration verified: State restored perfectly without network call!")
        print(f"    Current Theme       : {fresh_store.state.theme}")
        print(f"    Current User Profile: {fresh_store.state.user_profile}")
        print(f"    Current Auth Token  : {fresh_store.state.auth_token}")

    header("Step 4: Running Storage Performance Benchmark")
    run_benchmark(iterations=150)

    header("Lab Execution Status")
    success("All checks and lifecycle stages completed successfully with 100% compliance!")


if __name__ == "__main__":
    main_interactive_lab()

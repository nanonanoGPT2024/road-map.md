#!/usr/bin/env python3
"""
Lab Exercise: Vue.js Async Flow, Forms, and Data Fetching Simulation
Chapter: BAB-07-Asynchronous-Flow-Forms-dan-Data-Fetching
Platform: Python 3 CLI Interactive Simulation with ANSI Colors
"""

import sys
import time
import asyncio
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[48;5;236m"


def header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN} [VUE SIMULATOR] {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def log_step(badge: str, message: str, color: str = GREEN):
    print(f"{BOLD}{color}[{badge}]{RESET} {message}")


# ==============================================================================
# 1. Reactive Core Simulation (ref & watchEffect)
# ==============================================================================
class Ref:
    def __init__(self, initial_value: Any, name: str = "unnamed"):
        self._value = initial_value
        self.name = name
        self._subscribers: List[Callable[[Any], None]] = []

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_val: Any):
        if self._value != new_val:
            old = self._value
            self._value = new_val
            log_step("REACTIVE TRIGGER", f"Ref<{self.name}> updated: {DIM}{old}{RESET} -> {BOLD}{new_val}{RESET}", MAGENTA)
            for sub in self._subscribers:
                sub(new_val)

    def subscribe(self, callback: Callable[[Any], None]):
        self._subscribers.append(callback)


# ==============================================================================
# 2. Form & v-model Simulation with Modifiers (.trim, .number, .lazy)
# ==============================================================================
@dataclass
class FormField:
    name: str
    ref: Ref
    modifiers: List[str] = field(default_factory=list)
    validator: Optional[Callable[[Any], Optional[str]]] = None
    error: Optional[str] = None

    def input(self, raw_value: Any, trigger_type: str = "input"):
        # Handle .lazy modifier (only update on change/blur)
        if "lazy" in self.modifiers and trigger_type == "input":
            log_step("v-model.lazy", f"Field '{self.name}' skipped reactive flush on keystroke (waiting for change/blur)", YELLOW)
            return

        val = raw_value
        if "trim" in self.modifiers and isinstance(val, str):
            val = val.strip()
        if "number" in self.modifiers:
            try:
                val = float(val) if "." in str(val) else int(val)
            except ValueError:
                pass

        self.ref.value = val
        self.validate()

    def validate(self) -> bool:
        if self.validator:
            self.error = self.validator(self.ref.value)
            if self.error:
                log_step("FORM VALIDATION", f"Field '{self.name}': {RED}{self.error}{RESET}", RED)
                return False
        self.error = None
        log_step("FORM VALIDATION", f"Field '{self.name}' valid: {GREEN}OK{RESET}", GREEN)
        return True


# ==============================================================================
# 3. Asynchronous Data Fetching Engine with AbortController & State
# ==============================================================================
class AbortSignal:
    def __init__(self):
        self.aborted = False

    def abort(self):
        self.aborted = True


class MockApiServer:
    USERS_DB = [
        {"id": 1, "username": "alice_dev", "role": "Frontend Architect", "team": "Vue Core"},
        {"id": 2, "username": "bob_admin", "role": "Fullstack Lead", "team": "Platform"},
        {"id": 3, "username": "charlie_qa", "role": "QA Engineer", "team": "Testing"},
    ]

    @classmethod
    async def fetch_user(cls, query: str, signal: AbortSignal, delay_sec: float = 0.5) -> List[Dict]:
        elapsed = 0.0
        step = 0.1
        while elapsed < delay_sec:
            if signal.aborted:
                raise asyncio.CancelledError("Fetch request aborted by client (AbortController).")
            await asyncio.sleep(step)
            elapsed += step

        results = [u for u in cls.USERS_DB if query.lower() in u["username"].lower() or query.lower() in u["role"].lower()]
        return results


class UseFetchComposable:
    """Simulates custom Vue 3 composable: useFetch(url, options)"""
    def __init__(self):
        self.data = Ref(None, name="fetch_data")
        self.is_loading = Ref(False, name="isLoading")
        self.error = Ref(None, name="error")
        self._current_signal: Optional[AbortSignal] = None

    async def execute(self, query: str, debounce_ms: int = 0):
        # Cancel previous pending request (Vue 3 watch/AbortController pattern)
        if self._current_signal:
            log_step("ABORT CONTROLLER", f"Aborting stale inflight query: '{self._current_signal}'", YELLOW)
            self._current_signal.abort()

        signal = AbortSignal()
        self._current_signal = signal

        if debounce_ms > 0:
            log_step("DEBOUNCE", f"Debouncing for {debounce_ms}ms before network dispatch...", BLUE)
            await asyncio.sleep(debounce_ms / 1000.0)
            if signal.aborted:
                log_step("DEBOUNCE", "Query superseded during debounce window; dropped.", DIM)
                return

        self.is_loading.value = True
        self.error.value = None

        try:
            log_step("NETWORK DISPATCH", f"GET /api/users?q={query}", CYAN)
            res = await MockApiServer.fetch_user(query, signal, delay_sec=0.35)
            self.data.value = res
            log_step("FETCH SUCCESS", f"Loaded {len(res)} record(s) from mock API", GREEN)
        except asyncio.CancelledError as ce:
            self.error.value = "Request Cancelled"
            log_step("FETCH CANCELLED", str(ce), YELLOW)
        except Exception as e:
            self.error.value = str(e)
            log_step("FETCH ERROR", f"Failed: {e}", RED)
        finally:
            if self._current_signal is signal:
                self.is_loading.value = False


# ==============================================================================
# 4. Interactive Simulation Runner
# ==============================================================================
async def run_simulation():
    header("BAB-07: Async Flow, Forms & Data Fetching in Vue 3")

    # Part A: Two-way binding with modifiers
    print(f"\n{BOLD}{BLUE}[SCENARIO 1] Reactive Forms & v-model Modifiers (.trim, .number, .lazy){RESET}")
    username_ref = Ref("", name="form.username")
    age_ref = Ref(0, name="form.age")

    username_field = FormField(
        name="username",
        ref=username_ref,
        modifiers=["trim"],
        validator=lambda v: "Username minimal 4 karakter" if len(str(v)) < 4 else None
    )

    age_field = FormField(
        name="age",
        ref=age_ref,
        modifiers=["number"],
        validator=lambda v: "Umur minimal 18 tahun" if not isinstance(v, (int, float)) or v < 18 else None
    )

    log_step("USER ACTION", "Input username dengan trailing whitespace: '   evan_you   '")
    username_field.input("   evan_you   ")
    print(f"   -> Result Ref value: '{username_ref.value}' (Cleaned by .trim)")

    log_step("USER ACTION", "Input username invalid: 'yo'")
    username_field.input("yo")

    log_step("USER ACTION", "Input age string numeric: '24'")
    age_field.input("24")
    print(f"   -> Result Ref type: {type(age_ref.value).__name__} = {age_ref.value} (Cast by .number)")

    # Part B: Async Data Fetching & Debounced Search Pipeline
    print(f"\n{BOLD}{BLUE}[SCENARIO 2] Debounced Search with AbortController Cancellation{RESET}")
    fetcher = UseFetchComposable()

    log_step("USER TYPING", "User mengetik cepat di form: 'a' -> 'al' -> 'alice'")
    task1 = asyncio.create_task(fetcher.execute(query="a", debounce_ms=100))
    await asyncio.sleep(0.04)  # Ketikan kedua muncul sebelum debounce task 1 selesai

    task2 = asyncio.create_task(fetcher.execute(query="al", debounce_ms=100))
    await asyncio.sleep(0.04)  # Ketikan ketiga muncul

    task3 = asyncio.create_task(fetcher.execute(query="alice", debounce_ms=100))

    # Await all tasks to finish cleanly
    await asyncio.gather(task1, task2, task3, return_exceptions=True)

    print(f"\n{BOLD}{GREEN}[FINAL COMPONENT RENDER STATE]{RESET}")
    print(f"  • isLoading : {BOLD}{fetcher.is_loading.value}{RESET}")
    print(f"  • error     : {BOLD}{fetcher.error.value}{RESET}")
    print(f"  • data      : {BOLD}{fetcher.data.value}{RESET}")

    # Validation self-test assertion
    assert username_ref.value == "yo", "Expected username ref to hold 'yo'"
    assert age_ref.value == 24, "Expected age ref to hold integer 24"
    assert fetcher.data.value is not None, "Expected search data to be fetched"
    assert len(fetcher.data.value) == 1, "Expected 1 matching record for 'alice'"
    assert fetcher.data.value[0]["username"] == "alice_dev"

    print(f"\n{BOLD}{GREEN}✔ All Vue Async Flow & Form simulations passed verified!{RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Simulation interrupted by user.{RESET}")
        sys.exit(0)

#!/usr/bin/env python3
"""
BAB-05: State Management Engines & Reactive Patterns
Hands-on Lab Exercise: Fine-Grained Reactive Signals & Unidirectional Store Engine
"""

from typing import Callable, Any, Set, List, Optional, Dict
import time

# --- ANSI Terminal Color Palette ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
GRAY = "\033[90m"


# --- Fine-Grained Reactivity (Signal / Computed / Effect) ---
_active_subscriber: Optional[Callable[[], None]] = None


class Signal:
    """Reactive primitive holding a value and tracking subscriber nodes."""

    def __init__(self, value: Any, name: str = "AnonymousSignal"):
        self._value = value
        self.name = name
        self._subscribers: Set[Callable[[], None]] = set()

    def get(self) -> Any:
        global _active_subscriber
        if _active_subscriber is not None:
            self._subscribers.add(_active_subscriber)
        return self._value

    def set(self, new_value: Any) -> None:
        if self._value != new_value:
            old = self._value
            self._value = new_value
            print(
                f"  {GRAY}[Signal: {self.name}]{RESET} Changed: {YELLOW}{old}{RESET} -> {GREEN}{new_value}{RESET}"
            )
            self._notify()

    def _notify(self) -> None:
        # Clone subscribers to prevent mutation while iterating
        for subscriber in list(self._subscribers):
            subscriber()

    def __repr__(self) -> str:
        return f"Signal({self.name}={self._value})"


class Computed:
    """Derived reactive state memoized and recomputed on dependency notification."""

    def __init__(self, compute_fn: Callable[[], Any], name: str = "AnonymousComputed"):
        self.compute_fn = compute_fn
        self.name = name
        self._value: Any = None
        self._dirty: bool = True
        self._subscribers: Set[Callable[[], None]] = set()

        def _recompute_listener():
            self._dirty = True
            print(f"  {GRAY}[Computed: {self.name}]{RESET} Marked dirty by dependency")
            self._notify()

        self._listener = _recompute_listener

    def get(self) -> Any:
        global _active_subscriber
        if self._dirty:
            prev_sub = _active_subscriber
            _active_subscriber = self._listener
            try:
                self._value = self.compute_fn()
                self._dirty = False
                print(
                    f"  {GRAY}[Computed: {self.name}]{RESET} Evaluated fresh value: {CYAN}{self._value}{RESET}"
                )
            finally:
                _active_subscriber = prev_sub

        if _active_subscriber is not None:
            self._subscribers.add(_active_subscriber)

        return self._value

    def _notify(self) -> None:
        for subscriber in list(self._subscribers):
            subscriber()


def effect(fn: Callable[[], None], name: str = "AnonymousEffect") -> Callable[[], None]:
    """Side-effect runner that auto-subscribes to any signal read during execution."""

    def runner():
        global _active_subscriber
        prev_sub = _active_subscriber
        _active_subscriber = runner
        try:
            print(f"  {GRAY}[Effect: {name}]{RESET} Triggered execution...")
            fn()
        finally:
            _active_subscriber = prev_sub

    runner()
    return runner


# --- Unidirectional Flux / Redux Store Pattern ---
class Action:
    def __init__(self, action_type: str, payload: Optional[Any] = None):
        self.type = action_type
        self.payload = payload


Reducer = Callable[[Dict[str, Any], Action], Dict[str, Any]]
Middleware = Callable[
    ["Store", Action, Callable[[Action], None]], None
]


class Store:
    """Predictable unidirectional state store inspired by Redux."""

    def __init__(self, reducer: Reducer, initial_state: Dict[str, Any]):
        self._reducer = reducer
        self._state = initial_state
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._middlewares: List[Middleware] = []

    def get_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def subscribe(self, listener: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def apply_middleware(self, *middlewares: Middleware) -> None:
        self._middlewares.extend(middlewares)

    def dispatch(self, action: Action) -> None:
        def core_dispatch(act: Action) -> None:
            prev_state = self._state
            self._state = self._reducer(self._state, act)
            print(
                f"  {GRAY}[Store: Reducer]{RESET} Action: {MAGENTA}{act.type}{RESET} => State updated"
            )
            for listener in self._listeners:
                listener(self._state)

        # Middleware pipeline execution
        chain = core_dispatch
        for mw in reversed(self._middlewares):
            current_chain = chain

            def make_step(m=mw, nxt=current_chain):
                return lambda a: m(self, a, nxt)

            chain = make_step()

        chain(action)


# --- Simulation Walkthrough ---
def run_simulation() -> None:
    print(f"\n{BOLD}{CYAN}============================================================{RESET}")
    print(f"{BOLD}{CYAN}  BAB-05: Reactive Systems & State Engines Laboratory       {RESET}")
    print(f"{BOLD}{CYAN}============================================================{RESET}\n")

    # Part 1: Fine-Grained Signals Demo
    print(f"{BOLD}{BLUE}[PHASE 1] Fine-Grained Reactive Graph (Signals & Computeds){RESET}")
    print(f"{GRAY}Constructing dependency DAG: price (Signal) + quantity (Signal) -> total (Computed){RESET}")

    price = Signal(100, name="price")
    quantity = Signal(2, name="quantity")
    tax_rate = Signal(0.1, name="tax_rate")

    subtotal = Computed(lambda: price.get() * quantity.get(), name="subtotal")
    grand_total = Computed(
        lambda: round(subtotal.get() * (1.0 + tax_rate.get()), 2), name="grand_total"
    )

    # Register reactive DOM/UI effect
    @effect
    def render_cart_ui():
        print(
            f"    {GREEN}>>> UI Render:{RESET} Item subtotal = ${subtotal.get()}, "
            f"Grand Total (incl tax) = {BOLD}${grand_total.get()}{RESET}"
        )

    print(f"\n{YELLOW}-> Modifying price to 150...{RESET}")
    price.set(150)

    print(f"\n{YELLOW}-> Modifying quantity to 3...{RESET}")
    quantity.set(3)

    print(f"\n{YELLOW}-> Modifying tax_rate to 0.15...{RESET}")
    tax_rate.set(0.15)

    # Part 2: Unidirectional Redux Store Demo
    print(f"\n{BOLD}{BLUE}[PHASE 2] Unidirectional Flux/Redux Store Architecture{RESET}")

    initial_state = {"count": 0, "status": "idle", "history": []}

    def counter_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
        new_state = dict(state)
        history = list(state.get("history", []))

        if action.type == "INCREMENT":
            step = action.payload or 1
            new_state["count"] += step
            history.append(f"+{step}")
        elif action.type == "DECREMENT":
            step = action.payload or 1
            new_state["count"] -= step
            history.append(f"-{step}")
        elif action.type == "SET_STATUS":
            new_state["status"] = action.payload

        new_state["history"] = history
        return new_state

    # Logger Middleware
    def logger_middleware(store: Store, action: Action, next_dispatch: Callable[[Action], None]):
        print(f"  {GRAY}[Middleware:Logger]{RESET} Dispatching action: {BOLD}{action.type}{RESET}")
        start = time.perf_counter()
        next_dispatch(action)
        elapsed = (time.perf_counter() - start) * 1000
        print(
            f"  {GRAY}[Middleware:Logger]{RESET} Processed {action.type} in {elapsed:.3f}ms"
        )

    store = Store(counter_reducer, initial_state)
    store.apply_middleware(logger_middleware)

    # UI Subscription
    store.subscribe(
        lambda state: print(
            f"    {MAGENTA}>>> State Broadcast:{RESET} Count={BOLD}{state['count']}{RESET}, "
            f"Status='{state['status']}', History={state['history']}"
        )
    )

    print(f"\n{YELLOW}-> Dispatching counter actions...{RESET}")
    store.dispatch(Action("INCREMENT", 5))
    store.dispatch(Action("SET_STATUS", "active"))
    store.dispatch(Action("DECREMENT", 2))

    print(f"\n{BOLD}{GREEN}✓ Simulation completed successfully without errors.{RESET}\n")


if __name__ == "__main__":
    run_simulation()

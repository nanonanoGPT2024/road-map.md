#!/usr/bin/env python3
"""
Lab Exercise: Decentralized & Enterprise State Management Simulation in Angular
Topic: BAB-07 - State Management Terdesentralisasi dan Skala Besar (NgRx & SignalStore)
Architecture:
  - Decentralized Feature State Slices (Auth, Catalog, Cart)
  - Pure Reducers & Immutable State Tree
  - Memoized Selectors with Computation Cache
  - Async Effects Pipeline (Side Effects & Dispatch)
  - Modern SignalStore Simulation (Signals, Computed, patchState)
"""

import sys
import time
import json
import copy
from typing import Any, Callable, Dict, List, Optional, Tuple

# ANSI Terminal Styling
ESC = "\033["
RESET = f"{ESC}0m"
BOLD = f"{ESC}1m"
DIM = f"{ESC}2m"
CYAN = f"{ESC}36m"
GREEN = f"{ESC}32m"
YELLOW = f"{ESC}33m"
RED = f"{ESC}31m"
MAGENTA = f"{ESC}35m"
BLUE = f"{ESC}34m"
BG_BLUE = f"{ESC}44m"
BG_DARK = f"{ESC}40m"


def header(title: str) -> None:
    line = "=" * 65
    print(f"\n{BLUE}{line}{RESET}")
    print(f"{BOLD}{CYAN} [ANGULAR ARCHITECTURE LAB] {title.upper()}{RESET}")
    print(f"{BLUE}{line}{RESET}")


def badge(category: str, text: str, color: str = GREEN) -> str:
    return f"{color}[{category}]{RESET} {text}"


# =====================================================================
# 1. CORE DISPATCHER & ACTION SPECIFICATION
# =====================================================================

class Action:
    def __init__(self, action_type: str, payload: Optional[Dict[str, Any]] = None):
        self.type = action_type
        self.payload = payload or {}
        self.timestamp = time.time()

    def __repr__(self) -> str:
        payload_str = json.dumps(self.payload) if self.payload else "{}"
        return f"{YELLOW}{self.type}{RESET} {DIM}{payload_str}{RESET}"


def create_action(action_type: str) -> Callable[..., Action]:
    def action_creator(**kwargs: Any) -> Action:
        return Action(action_type, kwargs)
    return action_creator


# Defined Actions for Feature Modules
LoginSuccess = create_action("[Auth Feature] Login Success")
Logout = create_action("[Auth Feature] Logout")

LoadProductsSuccess = create_action("[Catalog Feature] Load Products Success")
UpdateProductStock = create_action("[Catalog Feature] Update Product Stock")

AddToCart = create_action("[Cart Feature] Add Item")
RemoveFromCart = create_action("[Cart Feature] Remove Item")
ClearCart = create_action("[Cart Feature] Clear Cart")


# =====================================================================
# 2. SELECTOR SYSTEM WITH MEMOIZATION
# =====================================================================

class MemoizedSelector:
    def __init__(self, name: str, projector: Callable[..., Any], *input_selectors: "MemoizedSelector"):
        self.name = name
        self.projector = projector
        self.input_selectors = input_selectors
        self._last_inputs: Optional[Tuple[Any, ...]] = None
        self._last_result: Any = None
        self.cache_hits = 0
        self.computations = 0

    def __call__(self, state: Dict[str, Any]) -> Any:
        if self.input_selectors:
            inputs = tuple(selector(state) for selector in self.input_selectors)
        else:
            inputs = (state,)

        if self._last_inputs is not None and inputs == self._last_inputs:
            self.cache_hits += 1
            return self._last_result

        self.computations += 1
        self._last_inputs = inputs
        self._last_result = self.projector(*inputs)
        return self._last_result


# =====================================================================
# 3. ROOT & FEATURE STATE STORE (NgRx Redux Pattern)
# =====================================================================

class EnterpriseStateStore:
    def __init__(self) -> None:
        self._feature_reducers: Dict[str, Callable[[Any, Action], Any]] = {}
        self._state: Dict[str, Any] = {}
        self._effects: List[Callable[[Action, "EnterpriseStateStore"], Optional[Action]]] = []
        self.action_history: List[Action] = []

    def register_feature(self, feature_name: str, reducer_fn: Callable[[Any, Action], Any], initial_state: Any) -> None:
        self._feature_reducers[feature_name] = reducer_fn
        self._state[feature_name] = copy.deepcopy(initial_state)
        print(f"  {badge('STORE', f'Registered Slice: {feature_name}', CYAN)}")

    def add_effect(self, effect_fn: Callable[[Action, "EnterpriseStateStore"], Optional[Action]]) -> None:
        self._effects.append(effect_fn)

    def select(self, selector: MemoizedSelector) -> Any:
        return selector(self._state)

    def dispatch(self, action: Action) -> None:
        self.action_history.append(action)
        print(f"  {badge('DISPATCH', str(action), YELLOW)}")

        # Reducer Phase (Pure Immutable Transitions)
        next_state: Dict[str, Any] = {}
        for feature_name, reducer in self._feature_reducers.items():
            curr_feature_state = self._state.get(feature_name)
            next_state[feature_name] = reducer(copy.deepcopy(curr_feature_state), action)
        self._state = next_state

        # Effects Pipeline (Side-effects & Asynchronous Dispatches)
        for effect in self._effects:
            next_action = effect(action, self)
            if next_action:
                print(f"    {badge('EFFECT TRIGGER', f'Side-effect caused action: {next_action.type}', MAGENTA)}")
                self.dispatch(next_action)

    @property
    def snapshot(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)


# =====================================================================
# 4. REDUCERS IMPLEMENTATION (Decentralized Feature Modules)
# =====================================================================

def auth_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    if action.type == "[Auth Feature] Login Success":
        return {
            **state,
            "isAuthenticated": True,
            "user": action.payload.get("user", {}),
            "role": action.payload.get("role", "viewer")
        }
    elif action.type == "[Auth Feature] Logout":
        return {
            **state,
            "isAuthenticated": False,
            "user": None,
            "role": "guest"
        }
    return state


def catalog_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    if action.type == "[Catalog Feature] Load Products Success":
        items = {item["id"]: item for item in action.payload.get("products", [])}
        return {**state, "entities": items, "loaded": True}
    elif action.type == "[Catalog Feature] Update Product Stock":
        pid = action.payload.get("id")
        qty = action.payload.get("quantity", 0)
        entities = copy.deepcopy(state.get("entities", {}))
        if pid in entities:
            entities[pid]["stock"] = max(0, entities[pid]["stock"] - qty)
        return {**state, "entities": entities}
    return state


def cart_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    if action.type == "[Cart Feature] Add Item":
        pid = action.payload.get("id")
        qty = action.payload.get("quantity", 1)
        items = copy.deepcopy(state.get("items", {}))
        items[pid] = items.get(pid, 0) + qty
        return {**state, "items": items, "totalItems": sum(items.values())}
    elif action.type == "[Cart Feature] Remove Item":
        pid = action.payload.get("id")
        items = copy.deepcopy(state.get("items", {}))
        if pid in items:
            del items[pid]
        return {**state, "items": items, "totalItems": sum(items.values())}
    elif action.type == "[Cart Feature] Clear Cart":
        return {"items": {}, "totalItems": 0}
    return state


# =====================================================================
# 5. ANGULAR SIGNAL STORE SIMULATION (Signal-Based Reactive Primitives)
# =====================================================================

class WritableSignal:
    def __init__(self, initial_value: Any, name: str = "signal"):
        self._value = initial_value
        self.name = name
        self._subscribers: List[Callable[[Any], None]] = []

    def get(self) -> Any:
        return self._value

    def set(self, new_value: Any) -> None:
        if self._value != new_value:
            self._value = new_value
            self._notify()

    def update(self, fn: Callable[[Any], Any]) -> None:
        self.set(fn(self._value))

    def subscribe(self, fn: Callable[[Any], None]) -> None:
        self._subscribers.append(fn)

    def _notify(self) -> None:
        for sub in self._subscribers:
            sub(self._value)


class ComputedSignal:
    def __init__(self, calculation: Callable[[], Any], *dependencies: WritableSignal, name: str = "computed"):
        self.name = name
        self.calculation = calculation
        self._cached_value = self.calculation()
        for dep in dependencies:
            dep.subscribe(lambda _: self._recompute())

    def _recompute(self) -> None:
        self._cached_value = self.calculation()

    def get(self) -> Any:
        return self._cached_value


class SignalStore:
    def __init__(self, initial_state: Dict[str, Any]):
        self._signals: Dict[str, WritableSignal] = {
            k: WritableSignal(v, name=k) for k, v in initial_state.items()
        }

    def select_signal(self, key: str) -> WritableSignal:
        return self._signals[key]

    def patch_state(self, updates: Dict[str, Any]) -> None:
        for key, val in updates.items():
            if key in self._signals:
                self._signals[key].set(val)
            else:
                self._signals[key] = WritableSignal(val, name=key)

    def snapshot(self) -> Dict[str, Any]:
        return {k: sig.get() for k, sig in self._signals.items()}


# =====================================================================
# 6. SIDE EFFECT DEMONSTRATION
# =====================================================================

def stock_sync_effect(action: Action, store: EnterpriseStateStore) -> Optional[Action]:
    """Sync catalog inventory whenever items are placed in the cart."""
    if action.type == "[Cart Feature] Add Item":
        prod_id = action.payload.get("id")
        qty = action.payload.get("quantity", 1)
        return UpdateProductStock(id=prod_id, quantity=qty)
    return None


# =====================================================================
# 7. INTERACTIVE CLI RUNNER & LAB SIMULATION
# =====================================================================

def run_simulation() -> None:
    header("NgRx Decentralized Architecture Initializing")

    store = EnterpriseStateStore()

    # Initial States
    store.register_feature("auth", auth_reducer, {
        "isAuthenticated": False,
        "user": None,
        "role": "guest"
    })
    store.register_feature("catalog", catalog_reducer, {
        "entities": {},
        "loaded": False
    })
    store.register_feature("cart", cart_reducer, {
        "items": {},
        "totalItems": 0
    })

    # Wire Effects
    store.add_effect(stock_sync_effect)

    # Build Selectors
    select_cart = MemoizedSelector("selectCart", lambda state: state.get("cart", {}))
    select_catalog = MemoizedSelector("selectCatalog", lambda state: state.get("catalog", {}))
    
    select_cart_detailed = MemoizedSelector(
        "selectCartDetailed",
        lambda cart, catalog: [
            {
                "id": pid,
                "name": catalog.get("entities", {}).get(pid, {}).get("name", "Unknown"),
                "qty": qty,
                "subtotal": qty * catalog.get("entities", {}).get(pid, {}).get("price", 0)
            }
            for pid, qty in cart.get("items", {}).items()
        ],
        select_cart,
        select_catalog
    )

    header("Step 1: Populating Product Catalog via Async Effect Dispatch")
    products = [
        {"id": "ANG-01", "name": "Enterprise Angular Design System", "price": 850000, "stock": 10},
        {"id": "ANG-02", "name": "NgRx & SignalStore Deep Dive Guide", "price": 450000, "stock": 15},
        {"id": "ANG-03", "name": "Micro-frontend Shell Template", "price": 1200000, "stock": 4},
    ]
    store.dispatch(LoadProductsSuccess(products=products))

    header("Step 2: Authenticating User in Auth Feature Slice")
    store.dispatch(LoginSuccess(user={"id": "usr_99", "name": "Budi Santoso"}, role="architect"))

    header("Step 3: Cart Dispatches & Cascading Reactive Stock Effects")
    store.dispatch(AddToCart(id="ANG-01", quantity=2))
    store.dispatch(AddToCart(id="ANG-02", quantity=1))

    header("Step 4: Evaluating Memoized Cross-Slice Selector")
    cart_summary = store.select(select_cart_detailed)
    print(f"\n{BOLD}{GREEN}Generated Cart View Projection:{RESET}")
    for item in cart_summary:
        print(f"  • {item['name']} (x{item['qty']}) -> {CYAN}Rp {item['subtotal']:,}{RESET}")

    # Test Selector Memoization Cache Hit
    print(f"\n{badge('CACHE TEST', 'Re-evaluating selector without state mutation...', BLUE)}")
    store.select(select_cart_detailed)
    print(f"  Memoization Computations: {select_cart_detailed.computations} (Expected: 1)")
    print(f"  Memoization Cache Hits:   {select_cart_detailed.cache_hits} (Expected: 1)")

    header("Step 5: Modern Angular @ngrx/signals (SignalStore) Simulation")
    sig_store = SignalStore({"filter": "active", "counter": 10})
    count_sig = sig_store.select_signal("counter")
    double_sig = ComputedSignal(lambda: count_sig.get() * 2, count_sig, name="doubleCount")

    print(f"  Initial Signal count: {count_sig.get()} | Computed double: {double_sig.get()}")
    print(f"  Patching state via patchState(counter -> 25)...")
    sig_store.patch_state({"counter": 25})
    print(f"  Updated Signal count: {CYAN}{count_sig.get()}{RESET} | Auto-recomputed double: {GREEN}{double_sig.get()}{RESET}")

    header("Final Enterprise State Snapshot (Decentralized Slices)")
    final_tree = store.snapshot
    for slice_name, slice_val in final_tree.items():
        print(f"{BOLD}{MAGENTA}[Slice: {slice_name}]{RESET}")
        print(f"  {json.dumps(slice_val, indent=2)}")

    print(f"\n{BOLD}{GREEN}✓ Lab Exercise Completed: 100% Valid Functional Simulation.{RESET}\n")


if __name__ == "__main__":
    run_simulation()

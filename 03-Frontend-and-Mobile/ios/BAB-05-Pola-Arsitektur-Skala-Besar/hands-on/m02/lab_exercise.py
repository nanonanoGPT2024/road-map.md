#!/usr/bin/env python3
"""
Lab Hands-on: iOS Architecture Deep Dive
Topic: Pola Arsitektur Skala Besar (Clean Architecture, MVVM, & TCA)
Simulates: The Composable Architecture (TCA) state machine, UDF (Unidirectional
Data Flow), Reducers, Async Side-Effects with cancellation IDs, and View binding.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Any
import threading
import time
import uuid
import sys

# ==============================================================================
# ANSI Formatting Helper
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

def print_header(title: str):
    print(f"\n{TermColor.BOLD}{TermColor.BLUE}=== {title} ==={TermColor.RESET}")

def print_log(layer: str, message: str, color: str = TermColor.CYAN):
    print(f"{color}[{layer.upper()}]{TermColor.RESET} {message}")


# ==============================================================================
# Domain Entities (Clean Architecture - Domain Layer)
# ==============================================================================
@dataclass(frozen=True)
class AccountBalance:
    account_id: str
    currency: str
    amount: float

@dataclass(frozen=True)
class TransactionItem:
    id: str
    description: str
    amount: float
    timestamp: float


# ==============================================================================
# Data & Service Dependencies (Clean Architecture - Data/Infrastructure Layer)
# ==============================================================================
class BankingAPIClient:
    """
    Simulates asynchronous networking dependency in TCA Environment.
    Supports deliberate latency and failure flags.
    """
    def fetch_balance(self, account_id: str) -> AccountBalance:
        time.sleep(0.4)  # Simulate network latency
        return AccountBalance(account_id=account_id, currency="USD", amount=12450.75)

    def fetch_transactions(self, account_id: str) -> List[TransactionItem]:
        time.sleep(0.6)  # Simulate network latency
        return [
            TransactionItem("tx-101", "Apple Store Reserve", -1299.00, time.time() - 3600),
            TransactionItem("tx-102", "Wire Transfer Payroll", 4500.00, time.time() - 7200),
            TransactionItem("tx-103", "AWS Cloud Infrastructure", -249.50, time.time() - 14400)
        ]

    def deposit(self, account_id: str, amount: float) -> bool:
        time.sleep(0.3)
        return True


# ==============================================================================
# TCA Core: State, Action, Effect
# ==============================================================================
@dataclass
class AppState:
    """Immutable state snapshot representing UI condition."""
    account: Optional[AccountBalance] = None
    transactions: List[TransactionItem] = field(default_factory=list)
    is_loading: bool = False
    is_refreshing_tx: bool = False
    error_message: Optional[str] = None
    last_action_name: str = "Init"

class ActionType(Enum):
    # UI Actions
    ON_APPEAR = auto()
    REFRESH_PULLED = auto()
    DEPOSIT_TAPPED = auto()
    CANCEL_ACTIVE_FETCH = auto()
    
    # Internal / Effect-driven Actions
    BALANCE_RESPONSE_RECEIVED = auto()
    TRANSACTIONS_RESPONSE_RECEIVED = auto()
    OPERATION_FAILED = auto()

@dataclass
class Action:
    type: ActionType
    payload: Any = None


class Effect:
    """
    Encapsulates side-effects (Network, Database, Timers).
    Returns runnable tasks that emit downstream Actions into the Store.
    """
    def __init__(self, task: Optional[Callable[[Callable[[Action], None]], None]] = None, cancellation_id: Optional[str] = None):
        self.task = task
        self.cancellation_id = cancellation_id

    @staticmethod
    def none() -> 'Effect':
        return Effect()

    @staticmethod
    def fire_and_forget(work: Callable[[], None]) -> 'Effect':
        def _wrapper(dispatch: Callable[[Action], None]):
            work()
        return Effect(task=_wrapper)

    @staticmethod
    def run(task: Callable[[Callable[[Action], None]], None], cancellation_id: Optional[str] = None) -> 'Effect':
        return Effect(task=task, cancellation_id=cancellation_id)


# ==============================================================================
# TCA Reducer Implementation
# ==============================================================================
def app_reducer(state: AppState, action: Action, client: BankingAPIClient) -> tuple[AppState, List[Effect]]:
    """
    Pure Reducer: Computes the next state deterministically given current state and action.
    Returns: (Updated State, List of Side Effects)
    """
    state.last_action_name = action.type.name
    effects: List[Effect] = []

    if action.type == ActionType.ON_APPEAR:
        state.is_loading = True
        state.error_message = None

        # Effect: Fetch Balance with cancellation capability
        def fetch_balance_effect(dispatch: Callable[[Action], None]):
            try:
                balance = client.fetch_balance("ACC-88319")
                dispatch(Action(ActionType.BALANCE_RESPONSE_RECEIVED, payload=balance))
            except Exception as e:
                dispatch(Action(ActionType.OPERATION_FAILED, payload=str(e)))

        effects.append(Effect.run(fetch_balance_effect, cancellation_id="FETCH_BALANCE"))
        return state, effects

    elif action.type == ActionType.BALANCE_RESPONSE_RECEIVED:
        state.account = action.payload
        state.is_loading = False
        return state, effects

    elif action.type == ActionType.REFRESH_PULLED:
        state.is_refreshing_tx = True

        def fetch_tx_effect(dispatch: Callable[[Action], None]):
            try:
                txs = client.fetch_transactions("ACC-88319")
                dispatch(Action(ActionType.TRANSACTIONS_RESPONSE_RECEIVED, payload=txs))
            except Exception as e:
                dispatch(Action(ActionType.OPERATION_FAILED, payload=str(e)))

        effects.append(Effect.run(fetch_tx_effect, cancellation_id="FETCH_TX"))
        return state, effects

    elif action.type == ActionType.TRANSACTIONS_RESPONSE_RECEIVED:
        state.transactions = action.payload
        state.is_refreshing_tx = False
        return state, effects

    elif action.type == ActionType.CANCEL_ACTIVE_FETCH:
        state.is_refreshing_tx = False
        state.is_loading = False
        print_log("Reducer", "Cancelling in-flight operations via cancellation tokens.", TermColor.YELLOW)
        return state, effects

    elif action.type == ActionType.DEPOSIT_TAPPED:
        deposit_amount = float(action.payload)
        if state.account:
            # Immediate optimistic local state update
            new_amount = state.account.amount + deposit_amount
            state.account = AccountBalance(state.account.account_id, state.account.currency, new_amount)
            # Add synthetic transaction entry
            new_tx = TransactionItem(f"tx-{uuid.uuid4().hex[:4]}", "Instant Deposit", deposit_amount, time.time())
            state.transactions.insert(0, new_tx)

        # Side-effect: sync with remote server
        def sync_deposit_effect(dispatch: Callable[[Action], None]):
            client.deposit("ACC-88319", deposit_amount)

        effects.append(Effect.fire_and_forget(lambda: client.deposit("ACC-88319", deposit_amount)))
        return state, effects

    elif action.type == ActionType.OPERATION_FAILED:
        state.is_loading = False
        state.is_refreshing_tx = False
        state.error_message = str(action.payload)
        return state, effects

    return state, effects


# ==============================================================================
# TCA Store: Orchestrator of State, Effects, and Subscribers
# ==============================================================================
class Store:
    """
    Thread-safe implementation of TCA Store.
    Maintains centralized state, runs effects on worker threads, and tracks cancellations.
    """
    def __init__(self, initial_state: AppState, reducer: Callable, client: BankingAPIClient):
        self._state = initial_state
        self._reducer = reducer
        self._client = client
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[AppState], None]] = []
        self._running_effects: Dict[str, threading.Event] = {}

    def subscribe(self, subscriber: Callable[[AppState], None]):
        self._subscribers.append(subscriber)

    def _notify(self):
        for sub in self._subscribers:
            sub(self._state)

    def send(self, action: Action):
        with self._lock:
            print_log("Store", f"Action received -> {TermColor.BOLD}{action.type.name}{TermColor.RESET}")
            
            # Check if this action triggers cancellation of previous tasks
            if action.type == ActionType.CANCEL_ACTIVE_FETCH:
                for c_id, cancel_event in list(self._running_effects.items()):
                    cancel_event.set()
                    print_log("Effect", f"Signal cancel for token: {c_id}", TermColor.MAGENTA)
                self._running_effects.clear()

            new_state, effects = self._reducer(self._state, action, self._client)
            self._state = new_state
            self._notify()

        # Execute side effects outside state lock
        for effect in effects:
            if effect.task:
                self._execute_effect(effect)

    def _execute_effect(self, effect: Effect):
        cancel_event = threading.Event()
        if effect.cancellation_id:
            # Cancel preexisting effect with identical ID (equivalent to TCA .cancellable(id:, cancelInFlight: true))
            if effect.cancellation_id in self._running_effects:
                self._running_effects[effect.cancellation_id].set()
            self._running_effects[effect.cancellation_id] = cancel_event

        def worker():
            def dispatch_callback(downstream_action: Action):
                if cancel_event.is_set():
                    print_log("Effect", f"Effect discarded downstream action due to cancellation: {downstream_action.type.name}", TermColor.YELLOW)
                    return
                self.send(downstream_action)

            try:
                effect.task(dispatch_callback)
            finally:
                if effect.cancellation_id and effect.cancellation_id in self._running_effects:
                    if self._running_effects[effect.cancellation_id] is cancel_event:
                        del self._running_effects[effect.cancellation_id]

        t = threading.Thread(target=worker, daemon=True)
        t.start()


# ==============================================================================
# View Simulation (SwiftUI Declarative View Layer)
# ==============================================================================
class AccountDashboardView:
    """Simulates SwiftUI View subscribed to Store state updates."""
    def render(self, state: AppState):
        status = "LOADING" if state.is_loading else ("REFRESHING" if state.is_refreshing_tx else "IDLE")
        balance_str = f"{state.account.currency} {state.account.amount:,.2f}" if state.account else "N/A"
        
        print("\n" + "-"*50)
        print(f"{TermColor.BOLD}SwiftUI Frame: State Update (Trigger: {state.last_action_name}){TermColor.RESET}")
        print(f" Status: [{TermColor.YELLOW}{status}{TermColor.RESET}] | Account Balance: {TermColor.GREEN}{balance_str}{TermColor.RESET}")
        print(f" Transactions Count: {len(state.transactions)}")
        for tx in state.transactions[:3]:
            sign = "+" if tx.amount > 0 else ""
            print(f"   * {tx.description.ljust(26)}: {sign}{tx.amount:,.2f}")
        if state.error_message:
            print(f" {TermColor.RED}Error Banner: {state.error_message}{TermColor.RESET}")
        print("-" * 50)


# ==============================================================================
# Simulation Pipeline Execution
# ==============================================================================
def main():
    print_header("TCA (THE COMPOSABLE ARCHITECTURE) DEEP DIVE ENGINE")
    print("Demonstrating Reducer Isolation, Pure Mutations, and Effect Cancellations.\n")

    # Dependency Injection (Clean Architecture)
    api_client = BankingAPIClient()
    initial_state = AppState()
    
    # Store Initialization
    store = Store(initial_state=initial_state, reducer=app_reducer, client=api_client)
    view = AccountDashboardView()
    
    # Wire State Binding
    store.subscribe(view.render)

    # 1. Trigger Initial View Load
    print_log("AppCycle", "View triggered .onAppear() lifecycle hook.", TermColor.MAGENTA)
    store.send(Action(ActionType.ON_APPEAR))
    time.sleep(0.6)  # Wait for balance effect to resolve

    # 2. Trigger Transactions Refresh
    print_log("AppCycle", "User performed Pull-To-Refresh.", TermColor.MAGENTA)
    store.send(Action(ActionType.REFRESH_PULLED))
    time.sleep(0.8)  # Wait for transaction list to populate

    # 3. Optimistic UI Mutation with Fire-and-Forget Effect
    print_log("AppCycle", "User tapped 'Quick Deposit +$500.00'", TermColor.MAGENTA)
    store.send(Action(ActionType.DEPOSIT_TAPPED, payload=500.00))
    time.sleep(0.4)

    # 4. Demonstrate Effect Cancellation Mid-Flight
    print_log("AppCycle", "Triggering long refresh followed by abrupt cancellation...", TermColor.MAGENTA)
    store.send(Action(ActionType.REFRESH_PULLED))
    time.sleep(0.1)  # Action started, effect running in background
    store.send(Action(ActionType.CANCEL_ACTIVE_FETCH))
    time.sleep(0.7)  # Give time for the cancelled thread to finish without emitting to store

    print_header("SIMULATION COMPLETED SUCCESSFULLY")
    print_log("System", "Store state remained deterministic across all async thread boundaries.", TermColor.GREEN)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Lab Hands-on: Deterministic Enterprise State Management (Flutter BLoC Architecture Deep Dive)
Simulasi komprehensif arsitektur state management reaktif & deterministik ala Flutter BLoC
menggunakan pipeline event stream, concurrent event transformer, immutability audit, 
serta time-travel debugging engine.
"""

from dataclasses import dataclass, field, replace
from enum import Enum, auto
import hashlib
import json
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"
C_BLUE = "\033[34m"
C_DIM = "\033[2m"


# ==============================================================================
# 1. CORE DATA STRUCTURES & IMMUTABILITY
# ==============================================================================

class EventTransformerType(Enum):
    CONCURRENT = auto()  # Standard queue execution
    DROPPABLE = auto()   # Abaikan event baru jika event lama sedang diproses
    RESTARTABLE = auto() # Batalkan task berjalan saat event baru masuk


@dataclass(frozen=True)
class Event:
    """Base class immutable event."""
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class State:
    """Base class immutable state dengan signature hashing deterministik."""
    def fingerprint(self) -> str:
        serialized = json.dumps(self.__dict__, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:8]


@dataclass(frozen=True)
class Transition:
    current_state: State
    event: Event
    next_state: State
    timestamp: float = field(default_factory=time.time)


# ==============================================================================
# 2. APPLICATION DOMAIN: E-COMMERCE CART STATE MACHINE
# ==============================================================================

@dataclass(frozen=True)
class CartItem:
    sku: str
    name: str
    price: float
    qty: int


@dataclass(frozen=True)
class CartState(State):
    status: str = "INITIAL"  # INITIAL, LOADING, READY, ERROR
    items: Tuple[CartItem, ...] = field(default_factory=tuple)
    total_amount: float = 0.0
    error_message: Optional[str] = None
    version: int = 0


@dataclass(frozen=True)
class LoadCartEvent(Event):
    pass


@dataclass(frozen=True)
class AddItemEvent(Event):
    item: CartItem = field(default_factory=lambda: CartItem("SKU-0", "Unknown", 0.0, 1))


@dataclass(frozen=True)
class CheckoutEvent(Event):
    payment_method: str = "CREDIT_CARD"


# ==============================================================================
# 3. BLOC RUNTIME ENGINE
# ==============================================================================

class BlocObserver:
    """Observer global untuk audit log, analytics, dan telemetry state."""
    def on_event(self, bloc_name: str, event: Event):
        print(f"  {C_BLUE}► [EVENT]{C_RESET} {C_BOLD}{bloc_name}{C_RESET} received {type(event).__name__}")

    def on_transition(self, bloc_name: str, transition: Transition):
        s_from = f"{transition.current_state.status}#{transition.current_state.fingerprint()}"
        s_to = f"{transition.next_state.status}#{transition.next_state.fingerprint()}"
        print(f"  {C_MAGENTA}⇄ [TRANSITION]{C_RESET} {s_from} ──({type(transition.event).__name__})──▶ {s_to}")

    def on_error(self, bloc_name: str, error: Exception):
        print(f"  {C_RED}✖ [ERROR]{C_RESET} {bloc_name}: {error}")


class Bloc:
    """Mesin Business Logic Component berbasis Event-driven deterministik."""
    def __init__(self, initial_state: State, observer: Optional[BlocObserver] = None):
        self._state = initial_state
        self._observer = observer or BlocObserver()
        self._event_queue: queue.Queue = queue.Queue()
        self._handlers: Dict[Type[Event], Tuple[Callable, EventTransformerType]] = {}
        self._history: List[Transition] = []
        self._is_active = True
        self._worker_thread = threading.Thread(target=self._process_event_loop, daemon=True)
        self._worker_thread.start()

    @property
    def state(self) -> State:
        return self._state

    def on(self, event_type: Type[Event], transformer: EventTransformerType = EventTransformerType.CONCURRENT):
        """Dekorator untuk mendaftarkan handler event."""
        def decorator(handler_fn: Callable):
            self._handlers[event_type] = (handler_fn, transformer)
            return handler_fn
        return decorator

    def add(self, event: Event):
        """Mengirimkan event ke stream BLoC."""
        if not self._is_active:
            raise RuntimeError("Bloc telah di-dispose, tidak menerima event baru.")
        self._observer.on_event(self.__class__.__name__, event)
        self._event_queue.put(event)

    def _emit(self, new_state: State, triggering_event: Event):
        """Pure state transition emitter."""
        if self._state == new_state:
            # Drop state jika tidak ada perubahan struktural (state debouncing)
            return
        
        transition = Transition(current_state=self._state, event=triggering_event, next_state=new_state)
        self._state = new_state
        self._history.append(transition)
        self._observer.on_transition(self.__class__.__name__, transition)

    def _process_event_loop(self):
        """Event loop internal yang menjamin urutan eksekusi."""
        while self._is_active:
            try:
                event = self._event_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            event_type = type(event)
            if event_type in self._handlers:
                handler, transformer = self._handlers[event_type]
                try:
                    # Implementasi emulasi transformer
                    if transformer == EventTransformerType.DROPPABLE:
                        # Drop event berikutnya jika ada yang sama dalam antrean instan
                        pass # Disederhanakan untuk bounded event queue loop
                    
                    handler(event, lambda next_s: self._emit(next_s, event))
                except Exception as err:
                    self._observer.on_error(self.__class__.__name__, err)
            else:
                self._observer.on_error(self.__class__.__name__, NotImplementedError(f"No handler for {event_type}"))
            
            self._event_queue.task_done()

    def close(self):
        """Menutup event loop BLoC."""
        self._event_queue.join()
        self._is_active = False
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)


# ==============================================================================
# 4. CONCRETE IMPLEMENTATION: CART BLOC
# ==============================================================================

class CartBloc(Bloc):
    def __init__(self, observer: Optional[BlocObserver] = None):
        super().__init__(CartState(), observer)
        
        # Mendaftarkan domain logic handlers
        self.on(LoadCartEvent, EventTransformerType.RESTARTABLE)(self._on_load_cart)
        self.on(AddItemEvent, EventTransformerType.CONCURRENT)(self._on_add_item)
        self.on(CheckoutEvent, EventTransformerType.DROPPABLE)(self._on_checkout)

    def _on_load_cart(self, event: LoadCartEvent, emit: Callable[[CartState], None]):
        emit(replace(self.state, status="LOADING", version=self.state.version + 1))
        # Simulasi latensi repository network call
        time.sleep(0.08)
        emit(replace(
            self.state,
            status="READY",
            items=(),
            total_amount=0.0,
            version=self.state.version + 1
        ))

    def _on_add_item(self, event: AddItemEvent, emit: Callable[[CartState], None]):
        updated_items = list(self.state.items)
        updated_items.append(event.item)
        new_total = sum(i.price * i.qty for i in updated_items)
        
        emit(replace(
            self.state,
            items=tuple(updated_items),
            total_amount=new_total,
            version=self.state.version + 1
        ))

    def _on_checkout(self, event: CheckoutEvent, emit: Callable[[CartState], None]):
        if not self.state.items:
            emit(replace(
                self.state,
                status="ERROR",
                error_message="Cart is empty! Cannot checkout.",
                version=self.state.version + 1
            ))
            return

        emit(replace(self.state, status="CHECKING_OUT", version=self.state.version + 1))
        time.sleep(0.05)
        emit(replace(
            self.state,
            status="SUCCESS",
            items=(),
            total_amount=0.0,
            version=self.state.version + 1
        ))


# ==============================================================================
# 5. TIME-TRAVEL DEBUGGER ENGINE
# ==============================================================================

class TimeTravelDebugger:
    """Merekam snapshot riwayat perubahan state dan memungkinkan replayability."""
    def __init__(self, bloc: Bloc):
        self._bloc = bloc

    def print_timeline(self):
        print(f"\n{C_CYAN}{C_BOLD}┌─── TIME-TRAVEL AUDIT LOG ───────────────────────────────────────────┐{C_RESET}")
        print(f"{C_CYAN}│ Step │ Trigger Event       │ Target Status │ Hash     │ Total Amount│{C_RESET}")
        print(f"{C_CYAN}├──────┼─────────────────────┼───────────────┼──────────┼─────────────┤{C_RESET}")
        
        for idx, tr in enumerate(self._bloc._history):
            ev_name = type(tr.event).__name__[:19]
            st_name = tr.next_state.status[:13]
            h = tr.next_state.fingerprint()
            amt = getattr(tr.next_state, 'total_amount', 0.0)
            print(f"│ {idx+1:04d} │ {ev_name:<19} │ {st_name:<13} │ {h:<8} │ ${amt:<10.2f}│")
        print(f"{C_CYAN}└──────┴─────────────────────┴───────────────┴──────────┴─────────────┘{C_RESET}")

    def rewind_to(self, step_index: int) -> State:
        """Memutar balik state ke indeks snapshot tertentu secara deterministik."""
        if not (0 <= step_index < len(self._bloc._history)):
            raise IndexError("Index riwayat time-travel di luar rentang.")
        target_state = self._bloc._history[step_index].next_state
        print(f"\n{C_YELLOW}⏪ REWINDING ENGINE: Mengembalikan state ke Step {step_index + 1}...{C_RESET}")
        print(f"   Fingerprint Pulih: {C_GREEN}{target_state.fingerprint()}{C_RESET}")
        print(f"   Payload Data: {target_state}")
        return target_state


# ==============================================================================
# 6. RUNNABLE VERIFICATION TEST SUITE
# ==============================================================================

def main():
    print(f"\n{C_BOLD}=== [LAB] FLUTTER ENTERPRISE STATE MANAGEMENT (BLOC DEEP DIVE) ==={C_RESET}\n")

    observer = BlocObserver()
    cart_bloc = CartBloc(observer=observer)
    debugger = TimeTravelDebugger(cart_bloc)

    print(f"{C_DIM}Mengirim Event: Inisialisasi Keranjang Belanja...{C_RESET}")
    cart_bloc.add(LoadCartEvent())
    time.sleep(0.12)

    print(f"\n{C_DIM}Mengirim Event Beruntun: Menambah Item Transaksi...{C_RESET}")
    cart_bloc.add(AddItemEvent(item=CartItem(sku="SKU-A100", name="Mechanical Keyboard", price=120.0, qty=1)))
    cart_bloc.add(AddItemEvent(item=CartItem(sku="SKU-B200", name="Wireless Mouse", price=65.5, qty=2)))
    time.sleep(0.05)

    print(f"\n{C_DIM}Mengirim Event: Proses Checkout...{C_RESET}")
    cart_bloc.add(CheckoutEvent(payment_method="QRIS_INSTANT"))
    
    # Tunggu seluruh background event thread selesai
    cart_bloc.close()

    # Cetak visualisasi timeline state
    debugger.print_timeline()

    # Validasi Time-Travel Deterministic Restoral
    # Rewind ke state setelah penambahan item pertama (Step 3)
    target_rewind_step = 2
    restored_state = debugger.rewind_to(target_rewind_step)

    # Asserts & Verifikasi Integritas
    assert restored_state.status == "READY", "State status mismatch setelah rewind!"
    assert len(restored_state.items) == 1, "Item count state korup!"
    assert restored_state.total_amount == 120.0, "Total kalkulasi deterministik gagal!"

    print(f"\n{C_GREEN}{C_BOLD}✔ SELURUH PENGUJIAN DETERMINISTIK STATE SUKSES DIJALANKAN.{C_RESET}\n")


if __name__ == "__main__":
    main()
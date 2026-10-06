#!/usr/bin/env python3
"""
Lab Exercise: Deterministic Enterprise State Management (Flutter BLoC & Event-Sourcing Pattern)
Simulasi teknis fondasi arsitektur BLoC (Business Logic Component), Unidirectional Data Flow,
Event Transformers, Deterministic State Transition, dan Time-Travel Replay Engine.
"""

from __future__ import annotations
import sys
import time
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Callable, Any

# ============================================================================
# ANSI Terminal Styling Helper
# ============================================================================
class Color:
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

def print_header(title: str) -> None:
    border = "=" * 70
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f"  {title.center(66)}")
    print(f"{border}{Color.RESET}")

def print_step(step: str, detail: str) -> None:
    print(f"{Color.MAGENTA}[PHASE]{Color.RESET} {Color.BOLD}{step:<24}{Color.RESET}: {detail}")

def print_success(msg: str) -> None:
    print(f"{Color.GREEN}✔ [SUCCESS]{Color.RESET} {msg}")

def print_warning(msg: str) -> None:
    print(f"{Color.YELLOW}⚠ [WARN]{Color.RESET} {msg}")

def print_error(msg: str) -> None:
    print(f"{Color.RED}✖ [ERROR]{Color.RESET} {msg}")

# ============================================================================
# Core Domain & State Definitions (Immutable & Pure)
# ============================================================================
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

@dataclass(frozen=True)
class OrderItem:
    id: str
    product_name: str
    amount: float
    status: OrderStatus = OrderStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_name": self.product_name,
            "amount": self.amount,
            "status": self.status.value,
        }

@dataclass(frozen=True)
class OrderState:
    """State immutable yang merefleksikan prinsip State di Flutter BLoC."""
    is_loading: bool
    orders: tuple[OrderItem, ...] = field(default_factory=tuple)
    filter_status: Optional[OrderStatus] = None
    error_message: Optional[str] = None
    state_version: int = 0
    state_hash: str = ""

    @staticmethod
    def initial() -> OrderState:
        s = OrderState(
            is_loading=False,
            orders=(),
            filter_status=None,
            error_message=None,
            state_version=0
        )
        return s.with_computed_hash()

    def copy_with(
        self,
        is_loading: Optional[bool] = None,
        orders: Optional[tuple[OrderItem, ...]] = None,
        filter_status: Optional[OrderStatus] = None,
        error_message: Optional[str] = None,
        clear_error: bool = False,
    ) -> OrderState:
        new_state = OrderState(
            is_loading=self.is_loading if is_loading is None else is_loading,
            orders=self.orders if orders is None else orders,
            filter_status=self.filter_status if filter_status is None else filter_status,
            error_message=None if clear_error else (self.error_message if error_message is None else error_message),
            state_version=self.state_version + 1,
        )
        return new_state.with_computed_hash()

    def with_computed_hash(self) -> OrderState:
        payload = {
            "version": self.state_version,
            "loading": self.is_loading,
            "orders": [o.to_dict() for o in self.orders],
            "filter": self.filter_status.value if self.filter_status else None,
            "err": self.error_message,
        }
        raw_repr = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()[:12]
        return OrderState(
            is_loading=self.is_loading,
            orders=self.orders,
            filter_status=self.filter_status,
            error_message=self.error_message,
            state_version=self.state_version,
            state_hash=digest,
        )

# ============================================================================
# Event Hierarchy (BLoC Contract)
# ============================================================================
class OrderEvent:
    """Base class untuk semua synchronous/asynchronous Bloc Event."""
    def event_name(self) -> str:
        return self.__class__.__name__

@dataclass(frozen=True)
class LoadOrdersEvent(OrderEvent):
    tenant_id: str

@dataclass(frozen=True)
class AddOrderEvent(OrderEvent):
    order: OrderItem

@dataclass(frozen=True)
class UpdateOrderStatusEvent(OrderEvent):
    order_id: str
    target_status: OrderStatus

@dataclass(frozen=True)
class FilterOrdersEvent(OrderEvent):
    status_filter: Optional[OrderStatus]

# ============================================================================
# Bloc Observer & Middleware (Audit & Deterministic Trace)
# ============================================================================
@dataclass
class Transition:
    current_state: OrderState
    event: OrderEvent
    next_state: OrderState
    timestamp: float = field(default_factory=time.time)

class BlocObserver:
    """Mencatat setiap transisi untuk auditabilitas dan time-travel."""
    def __init__(self) -> None:
        self.transitions: List[Transition] = []

    def on_transition(self, transition: Transition) -> None:
        self.transitions.append(transition)
        print(f"  {Color.BLUE}↳ Transition #{transition.next_state.state_version}:{Color.RESET} "
              f"[{transition.event.event_name()}] "
              f"Hash: {Color.YELLOW}{transition.current_state.state_hash}{Color.RESET} "
              f"-> {Color.GREEN}{transition.next_state.state_hash}{Color.RESET}")

# ============================================================================
# OrderBloc Implementation
# ============================================================================
class OrderBloc:
    def __init__(self, observer: Optional[BlocObserver] = None) -> None:
        self._state: OrderState = OrderState.initial()
        self._observer = observer or BlocObserver()
        self._event_history: List[OrderEvent] = []

    @property
    def state(self) -> OrderState:
        return self._state

    @property
    def event_history(self) -> List[OrderEvent]:
        return list(self._event_history)

    def emit(self, event: OrderEvent, new_state: OrderState) -> None:
        prev = self._state
        self._state = new_state
        self._observer.on_transition(Transition(current_state=prev, event=event, next_state=new_state))

    def add(self, event: OrderEvent) -> None:
        """Dispatcher event dengan penanganan murni & deterministik."""
        self._event_history.append(event)
        print(f"\n{Color.BOLD}{Color.CYAN}>>> DISPATCH EVENT:{Color.RESET} {event.event_name()} | Payload: {event}")
        self._map_event_to_state(event)

    def _map_event_to_state(self, event: OrderEvent) -> None:
        if isinstance(event, LoadOrdersEvent):
            # 1. Emit loading
            self.emit(event, self._state.copy_with(is_loading=True, clear_error=True))
            # 2. Simulated fetching data
            seed_orders = (
                OrderItem(id="ORD-101", product_name="Enterprise License Tier-1", amount=1250.0, status=OrderStatus.CONFIRMED),
                OrderItem(id="ORD-102", product_name="Cloud Dedicated Worker Pool", amount=450.0, status=OrderStatus.PENDING),
            )
            self.emit(event, self._state.copy_with(is_loading=False, orders=seed_orders))

        elif isinstance(event, AddOrderEvent):
            current_orders = list(self._state.orders)
            current_orders.append(event.order)
            self.emit(event, self._state.copy_with(orders=tuple(current_orders)))

        elif isinstance(event, UpdateOrderStatusEvent):
            order_exists = any(o.id == event.order_id for o in self._state.orders)
            if not order_exists:
                self.emit(event, self._state.copy_with(
                    error_message=f"Order {event.order_id} tidak ditemukan!",
                    clear_error=False
                ))
                return

            updated = []
            for o in self._state.orders:
                if o.id == event.order_id:
                    # Invariant Check: Order yang sudah CANCELLED tidak bisa diaktifkan kembali
                    if o.status == OrderStatus.CANCELLED and event.target_status != OrderStatus.CANCELLED:
                        self.emit(event, self._state.copy_with(
                            error_message=f"Invariant Violation: Order {o.id} telah dibatalkan permanen."
                        ))
                        return
                    updated.append(OrderItem(id=o.id, product_name=o.product_name, amount=o.amount, status=event.target_status))
                else:
                    updated.append(o)
            self.emit(event, self._state.copy_with(orders=tuple(updated), clear_error=True))

        elif isinstance(event, FilterOrdersEvent):
            self.emit(event, self._state.copy_with(filter_status=event.status_filter))

# ============================================================================
# Time Travel & Replay Verification Engine
# ============================================================================
class DeterministicReplayEngine:
    """Mesin penguji kepatuhan matematis determinisme event-sourcing."""
    @staticmethod
    def replay(events: List[OrderEvent]) -> OrderState:
        replay_bloc = OrderBloc(observer=None)
        for ev in events:
            replay_bloc._map_event_to_state(ev)
        return replay_bloc.state

    @staticmethod
    def verify_determinism(source_bloc: OrderBloc) -> bool:
        original_final_state = source_bloc.state
        events = source_bloc.event_history
        replayed_state = DeterministicReplayEngine.replay(events)

        is_match = (
            original_final_state.state_version == replayed_state.state_version and
            original_final_state.state_hash == replayed_state.state_hash and
            len(original_final_state.orders) == len(replayed_state.orders)
        )
        return is_match

# ============================================================================
# Interactive Terminal UI Runner
# ============================================================================
def display_current_state(state: OrderState) -> None:
    print(f"\n{Color.BG_DARK}--- [CURRENT WIDGET RE-RENDER VIEW] ---{Color.RESET}")
    print(f"  Version: {state.state_version} | Hash: {Color.YELLOW}{state.state_hash}{Color.RESET} | Loading: {state.is_loading}")
    if state.error_message:
        print(f"  {Color.RED}Banner Error: {state.error_message}{Color.RESET}")
    if state.filter_status:
        print(f"  Active Filter: {Color.CYAN}{state.filter_status.value}{Color.RESET}")
    
    print(f"  Visible Orders ({len(state.orders)} total):")
    for o in state.orders:
        if state.filter_status and o.status != state.filter_status:
            continue
        status_color = Color.GREEN if o.status == OrderStatus.CONFIRMED else (Color.RED if o.status == OrderStatus.CANCELLED else Color.YELLOW)
        print(f"    • [{o.id}] {o.product_name:<32} ${o.amount:>8.2f} [{status_color}{o.status.value}{Color.RESET}]")
    print(f"{Color.BG_DARK}---------------------------------------{Color.RESET}\n")

def run_automated_suite(bloc: OrderBloc) -> None:
    print_header("MENJALANKAN SUITE SIMULASI DETERMINISTIK OTOMATIS")
    
    print_step("STEP 1", "Dispatch LoadOrdersEvent untuk menginisiasi repositori")
    bloc.add(LoadOrdersEvent(tenant_id="enterprise-corp-01"))
    display_current_state(bloc.state)

    print_step("STEP 2", "Dispatch AddOrderEvent (menambah pesanan baru)")
    new_item = OrderItem(id="ORD-103", product_name="Mobile Push Gateway Service", amount=890.0, status=OrderStatus.PENDING)
    bloc.add(AddOrderEvent(order=new_item))
    display_current_state(bloc.state)

    print_step("STEP 3", "Dispatch UpdateOrderStatusEvent ke CONFIRMED")
    bloc.add(UpdateOrderStatusEvent(order_id="ORD-103", target_status=OrderStatus.CONFIRMED))
    display_current_state(bloc.state)

    print_step("STEP 4", "Uji Invariant Violation (Membatalkan lalu mengaktifkan kembali)")
    bloc.add(UpdateOrderStatusEvent(order_id="ORD-102", target_status=OrderStatus.CANCELLED))
    bloc.add(UpdateOrderStatusEvent(order_id="ORD-102", target_status=OrderStatus.CONFIRMED))
    display_current_state(bloc.state)

    print_step("STEP 5", "Filter View dengan FilterOrdersEvent")
    bloc.add(FilterOrdersEvent(status_filter=OrderStatus.CONFIRMED))
    display_current_state(bloc.state)

    print_header("AUDIT & DETERMINISTIC TIME-TRAVEL REPLAY VERIFICATION")
    is_deterministic = DeterministicReplayEngine.verify_determinism(bloc)
    if is_deterministic:
        print_success(f"Determinisme 100% TERBUKTI! State Hash Replay cocok presisi: {bloc.state.state_hash}")
    else:
        print_error("Determinisme gagal! State mutation leak terdeteksi.")
        sys.exit(1)

def interactive_loop() -> None:
    observer = BlocObserver()
    bloc = OrderBloc(observer=observer)

    if not sys.stdin.isatty():
        # Pipeline execution / automated test
        run_automated_suite(bloc)
        return

    print_header("FLUTTER DETERMINISTIC STATE MANAGEMENT (BLoC SIMULATOR)")
    print(f"{Color.DIM}Silakan pilih opsi untuk mengeksplorasi arsitektur BLoC secara interaktif.{Color.RESET}")

    while True:
        print(f"\n{Color.BOLD}Menu Navigasi Lab:{Color.RESET}")
        print("  1. Inisialisasi & Ambil Data (LoadOrdersEvent)")
        print("  2. Tambah Pesanan Baru (AddOrderEvent)")
        print("  3. Ubah Status Pesanan (UpdateOrderStatusEvent)")
        print("  4. Uji Pelanggaran Invariant State")
        print("  5. Verifikasi Determinisme (Time Travel Replay Engine)")
        print("  6. Jalankan Full Automated Test Suite")
        print("  0. Keluar")

        try:
            choice = input(f"{Color.CYAN}Pilih opsi [0-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            bloc.add(LoadOrdersEvent(tenant_id="enterprise-user"))
            display_current_state(bloc.state)
        elif choice == "2":
            order_id = f"ORD-{int(time.time()) % 1000}"
            item = OrderItem(id=order_id, product_name="Cloud Microservice Instance", amount=299.0, status=OrderStatus.PENDING)
            bloc.add(AddOrderEvent(order=item))
            display_current_state(bloc.state)
        elif choice == "3":
            if not bloc.state.orders:
                print_warning("Belum ada data pesanan. Jalankan opsi 1 terlebih dahulu.")
                continue
            target_id = bloc.state.orders[0].id
            bloc.add(UpdateOrderStatusEvent(order_id=target_id, target_status=OrderStatus.CONFIRMED))
            display_current_state(bloc.state)
        elif choice == "4":
            if not bloc.state.orders:
                print_warning("Jalankan opsi 1 terlebih dahulu.")
                continue
            target_id = bloc.state.orders[0].id
            print_step("ACTION", f"Membatalkan {target_id} lalu mencoba mengonfirmasinya lagi...")
            bloc.add(UpdateOrderStatusEvent(order_id=target_id, target_status=OrderStatus.CANCELLED))
            bloc.add(UpdateOrderStatusEvent(order_id=target_id, target_status=OrderStatus.CONFIRMED))
            display_current_state(bloc.state)
        elif choice == "5":
            print_step("AUDIT", "Memutar ulang seluruh sequence event dari t0...")
            ok = DeterministicReplayEngine.verify_determinism(bloc)
            if ok:
                print_success(f"VERIFIKASI BERHASIL! Hash identik: {bloc.state.state_hash}")
            else:
                print_error("VERIFIKASI GAGAL! Terjadi divergensi state.")
        elif choice == "6":
            fresh_bloc = OrderBloc(observer=BlocObserver())
            run_automated_suite(fresh_bloc)
        elif choice == "0":
            print("Sesi ditutup.")
            break
        else:
            print_warning("Pilihan tidak valid.")

if __name__ == "__main__":
    interactive_loop()

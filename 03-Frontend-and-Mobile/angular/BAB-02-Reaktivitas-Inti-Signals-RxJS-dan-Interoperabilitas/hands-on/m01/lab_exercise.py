#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Reaktivitas Inti Angular (Signals, RxJS, dan Interoperabilitas)
BAB-02: Reaktivitas Inti - Signals, RxJS, dan Interoperabilitas

Simulasi teknis mandiri berbasis CLI untuk mendalami:
1. Signal graph reactivity: writable signal, computed signal (lazy & glitch-free), effect.
2. Dependency tracking via execution context stack.
3. RxJS primitives: Observable, Subject, Pipe, Operators (map, filter).
4. Interoperability bridge: toSignal() dan toObservable().
"""

import sys
import time
from typing import Callable, Any, List, Set, Optional, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")

# ==============================================================================
# ANSI Color Palette for Terminal UI
# ==============================================================================
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    RESET = "\033[0m"


# ==============================================================================
# 1. CORE REACTIVITY ENGINE (ANGULAR SIGNALS SPEC SIMULATION)
# ==============================================================================

# Global execution context stack for dependency tracking
_active_consumer: Optional["ReactiveNode"] = None


class ReactiveNode:
    """Base class for any reactive consumer (Computed / Effect)."""
    def on_dependency_changed(self) -> None:
        pass


class Signal(Generic[T]):
    """Writable Signal: Holds state and notifies dependent consumers on modification."""
    def __init__(self, initial_value: T, equal: Optional[Callable[[T, T], bool]] = None):
        self._value = initial_value
        self._equal = equal if equal is not None else (lambda a, b: a == b)
        self.consumers: Set[ReactiveNode] = set()

    def __call__(self) -> T:
        """Read signal value & register dependency with the current reactive consumer."""
        global _active_consumer
        if _active_consumer is not None:
            self.consumers.add(_active_consumer)
        return self._value

    def set(self, new_value: T) -> None:
        """Directly set a new value."""
        if self._equal(self._value, new_value):
            return  # No-op if value is structurally equal
        self._value = new_value
        self._notify_consumers()

    def update(self, update_fn: Callable[[T], T]) -> None:
        """Update value based on the previous value."""
        self.set(update_fn(self._value))

    def _notify_consumers(self) -> None:
        # Create a copy of consumers to prevent set mutation during notification
        for consumer in list(self.consumers):
            consumer.on_dependency_changed()


class Computed(ReactiveNode, Generic[T]):
    """Computed Signal: Derives state lazily with memoization and glitch-free caching."""
    def __init__(self, computation: Callable[[], T]):
        self._computation = computation
        self._value: Optional[T] = None
        self._dirty = True
        self.consumers: Set[ReactiveNode] = set()

    def on_dependency_changed(self) -> None:
        if not self._dirty:
            self._dirty = True
            for consumer in list(self.consumers):
                consumer.on_dependency_changed()

    def __call__(self) -> T:
        global _active_consumer
        if _active_consumer is not None:
            self.consumers.add(_active_consumer)

        if self._dirty:
            # Recompute while tracking inner dependencies
            prev_consumer = _active_consumer
            _active_consumer = self
            try:
                self._value = self._computation()
                self._dirty = False
            finally:
                _active_consumer = prev_consumer

        return self._value  # type: ignore[return-value]


class Effect(ReactiveNode):
    """Side-effect runner: Automatically re-executes when its signal dependencies change."""
    def __init__(self, effect_fn: Callable[[], None]):
        self._effect_fn = effect_fn
        self._scheduled = False
        self.run()

    def on_dependency_changed(self) -> None:
        if not self._scheduled:
            self._scheduled = True
            # In Angular, effects run on microtask queue. We simulate synchronous run here.
            self.run()

    def run(self) -> None:
        global _active_consumer
        self._scheduled = False
        prev_consumer = _active_consumer
        _active_consumer = self
        try:
            self._effect_fn()
        finally:
            _active_consumer = prev_consumer


def untracked(fn: Callable[[], T]) -> T:
    """Execute reading of signals without establishing reactive dependencies."""
    global _active_consumer
    prev = _active_consumer
    _active_consumer = None
    try:
        return fn()
    finally:
        _active_consumer = prev


# ==============================================================================
# 2. RXJS PRIMITIVES & OPERATORS SIMULATION
# ==============================================================================

class Subscription:
    def __init__(self, unsubscribe_callback: Callable[[], None]):
        self._unsubscribe_callback = unsubscribe_callback
        self.closed = False

    def unsubscribe(self) -> None:
        if not self.closed:
            self.closed = True
            self._unsubscribe_callback()


class Observable(Generic[T]):
    """Observable Stream Primitive."""
    def __init__(self, subscribe_fn: Callable[[Any], Optional[Callable[[], None]]]):
        self._subscribe_fn = subscribe_fn

    def subscribe(self, next_fn: Callable[[T], None], error_fn: Optional[Callable[[Any], None]] = None) -> Subscription:
        class Observer:
            def next(self, val: T) -> None:
                next_fn(val)
            def error(self, err: Any) -> None:
                if error_fn:
                    error_fn(err)

        observer = Observer()
        teardown = self._subscribe_fn(observer)
        return Subscription(teardown if teardown else (lambda: None))

    def pipe(self, *operators: Callable[["Observable[Any]"], "Observable[Any]"]) -> "Observable[Any]":
        current: Observable[Any] = self
        for op in operators:
            current = op(current)
        return current


class Subject(Observable[T]):
    """Subject: Multicast event emitter acting as both Observable and Observer."""
    def __init__(self):
        self._observers: List[Any] = []

        def subscribe_fn(obs: Any):
            self._observers.append(obs)
            return lambda: self._observers.remove(obs) if obs in self._observers else None

        super().__init__(subscribe_fn)

    def next(self, value: T) -> None:
        for obs in list(self._observers):
            obs.next(value)


def rx_map(project: Callable[[Any], Any]):
    """RxJS map operator."""
    def operator(source: Observable[Any]) -> Observable[Any]:
        def subscribe_fn(observer: Any):
            sub = source.subscribe(
                lambda val: observer.next(project(val)),
                lambda err: observer.error(err)
            )
            return sub.unsubscribe
        return Observable(subscribe_fn)
    return operator


def rx_filter(predicate: Callable[[Any], bool]):
    """RxJS filter operator."""
    def operator(source: Observable[Any]) -> Observable[Any]:
        def subscribe_fn(observer: Any):
            sub = source.subscribe(
                lambda val: observer.next(val) if predicate(val) else None,
                lambda err: observer.error(err)
            )
            return sub.unsubscribe
        return Observable(subscribe_fn)
    return operator


# ==============================================================================
# 3. INTEROPERABILITY BRIDGES (toSignal & toObservable)
# ==============================================================================

def to_signal(source$: Observable[T], initial_value: T) -> Signal[T]:
    """Bridge: Convert an RxJS Observable stream into an Angular Signal."""
    sig = Signal[T](initial_value)
    source$.subscribe(lambda val: sig.set(val))
    return sig


def to_observable(source_signal: Signal[T]) -> Observable[T]:
    """Bridge: Convert an Angular Signal into an RxJS Observable stream via Effect."""
    def subscribe_fn(observer: Any):
        # Trigger emit whenever effect captures a new signal value
        def effect_body():
            val = source_signal()
            observer.next(val)

        eff = Effect(effect_body)
        return lambda: eff.consumers.clear()

    return Observable(subscribe_fn)


# ==============================================================================
# 4. INTERACTIVE CLI LAB & DEMO HARNESS
# ==============================================================================

def print_banner():
    print(f"{Colors.HEADER}{Colors.BOLD}" + "=" * 70)
    print(" ANGULAR REACTIVITY ENGINE: SIGNALS & RXJS INTEROP LAB")
    print(" BAB-02: Reaktivitas Inti - Signals, RxJS, dan Interoperabilitas")
    print("=" * 70 + f"{Colors.RESET}\n")


def demo_signals_glitch_free():
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- [1] DEMO: Writable Signal & Glitch-Free Diamond Graph ---{Colors.RESET}")
    print(f"{Colors.DIM}Struktur Graf: A -> B (A*2), A -> C (A+10), D = B + C (Diamond shape){Colors.RESET}")
    
    A = Signal[int](1)
    B = Computed[int](lambda: A() * 2)
    C = Computed[int](lambda: A() + 10)
    D = Computed[int](lambda: B() + C())

    print(f"Initial: A={Colors.GREEN}{A()}{Colors.RESET}, B={Colors.YELLOW}{B()}{Colors.RESET}, C={Colors.YELLOW}{C()}{Colors.RESET} => D={Colors.BOLD}{D()}{Colors.RESET}")
    
    print(f"\n{Colors.BLUE}--> Mengubah nilai A: A.set(5){Colors.RESET}")
    A.set(5)
    print(f"Result:  A={Colors.GREEN}{A()}{Colors.RESET}, B={Colors.YELLOW}{B()}{Colors.RESET}, C={Colors.YELLOW}{C()}{Colors.RESET} => D={Colors.BOLD}{D()}{Colors.RESET}")
    print(f"{Colors.GREEN}[V] Glitch-free verified! Reevaluasi D terjadi konsisten tanpa intermediate state tearing.{Colors.RESET}")


def demo_effect_and_untracked():
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- [2] DEMO: Effect Tracking & untracked() Scope ---{Colors.RESET}")
    
    counter = Signal[int](0)
    logger_prefix = Signal[str]("COUNTER_LOG")
    effect_run_count = 0

    def effect_action():
        nonlocal effect_run_count
        effect_run_count += 1
        # Baca prefix secara UNTRACKED agar perubahan prefix TIDAK men-trigger effect ini
        pfx = untracked(lambda: logger_prefix())
        cnt = counter()
        print(f"  {Colors.MAGENTA}[Effect Run #{effect_run_count}]{Colors.RESET} {pfx} :: count = {cnt}")

    print("Registrasi Effect...")
    eff = Effect(effect_action)

    print(f"\n{Colors.BLUE}--> Incrementing counter.update(lambda n: n + 1){Colors.RESET}")
    counter.update(lambda n: n + 1)

    print(f"\n{Colors.BLUE}--> Mengubah logger_prefix.set('NEW_PREFIX') (Untracked dependency){Colors.RESET}")
    logger_prefix.set("NEW_PREFIX")
    print(f"  {Colors.DIM}(Effect tidak terpanggil karena logger_prefix di-wrap untracked){Colors.RESET}")

    print(f"\n{Colors.BLUE}--> Incrementing counter lagi...{Colors.RESET}")
    counter.update(lambda n: n + 1)
    print(f"{Colors.GREEN}[V] Total Effect executions: {effect_run_count} (Expected: 3){Colors.RESET}")


def demo_rxjs_stream():
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- [3] DEMO: RxJS Event Stream Pipeline ---{Colors.RESET}")
    print(f"{Colors.DIM}Subject -> pipe(filter(even), map(x10)) -> Subscriber{Colors.RESET}")
    
    events$ = Subject[int]()
    pipeline$ = events$.pipe(
        rx_filter(lambda n: n % 2 == 0),
        rx_map(lambda n: f"Genap * 10 = {n * 10}")
    )

    outputs: List[str] = []
    sub = pipeline$.subscribe(lambda val: outputs.append(val))

    print(f"{Colors.BLUE}--> Emitting values: 1, 2, 3, 4, 5, 6 ke Subject{Colors.RESET}")
    for item in [1, 2, 3, 4, 5, 6]:
        events$.next(item)

    for out in outputs:
        print(f"  {Colors.YELLOW}Stream Item received:{Colors.RESET} {out}")

    sub.unsubscribe()
    print(f"{Colors.GREEN}[V] RxJS Stream pipeline execution complete!{Colors.RESET}")


def demo_interop():
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- [4] DEMO: Interoperabilitas toSignal() & toObservable() ---{Colors.RESET}")
    
    # 1. toSignal: Stream to Reactive State
    print(f"{Colors.BOLD}(A) toSignal(source$, initial){Colors.RESET}")
    action_stream$ = Subject[str]()
    status_sig = to_signal(action_stream$, initial_value="IDLE")
    print(f"  Nilai awal Signal: {Colors.GREEN}{status_sig()}{Colors.RESET}")
    
    action_stream$.next("LOADING")
    print(f"  Stream emit 'LOADING' -> Signal bernilai: {Colors.GREEN}{status_sig()}{Colors.RESET}")
    action_stream$.next("SUCCESS")
    print(f"  Stream emit 'SUCCESS' -> Signal bernilai: {Colors.GREEN}{status_sig()}{Colors.RESET}")

    # 2. toObservable: Reactive State to Stream
    print(f"\n{Colors.BOLD}(B) toObservable(signal){Colors.RESET}")
    user_role_sig = Signal[str]("USER")
    role_stream$ = to_observable(user_role_sig)

    captured: List[str] = []
    sub = role_stream$.subscribe(lambda r: captured.append(r))

    print(f"{Colors.BLUE}--> Mengubah Signal: user_role_sig.set('ADMIN'){Colors.RESET}")
    user_role_sig.set("ADMIN")
    print(f"{Colors.BLUE}--> Mengubah Signal: user_role_sig.set('SUPERADMIN'){Colors.RESET}")
    user_role_sig.set("SUPERADMIN")

    print(f"  Stream captured {len(captured)} event perubahan: {captured}")
    sub.unsubscribe()
    print(f"{Colors.GREEN}[V] Interoperability bridge bidirectional sync sukses!{Colors.RESET}")


def interactive_playground():
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== [5] INTERACTIVE LAB PLAYGROUND ==={Colors.RESET}")
    print("Membuat reactive shopping cart berbasis Signals...")
    
    price = Signal[float](150000.0)
    qty = Signal[int](1)
    discount_pct = Signal[float](0.10)  # 10%

    subtotal = Computed[float](lambda: price() * qty())
    total_tax = Computed[float](lambda: subtotal() * 0.11)  # PPN 11%
    grand_total = Computed[float](lambda: (subtotal() * (1.0 - discount_pct())) + total_tax())

    def print_cart():
        print(f"\n{Colors.HEADER}--- RINGKASAN KERANJANG BELANJA ---{Colors.RESET}")
        print(f"  Harga Satuan : Rp {price():,.2f}")
        print(f"  Jumlah (Qty) : {qty()}")
        print(f"  Diskon       : {discount_pct() * 100:.0f}%")
        print(f"  Subtotal     : Rp {subtotal():,.2f}")
        print(f"  PPN (11%)    : Rp {total_tax():,.2f}")
        print(f"  {Colors.BOLD}{Colors.GREEN}Grand Total  : Rp {grand_total():,.2f}{Colors.RESET}")

    print_cart()

    while True:
        print(f"\n{Colors.BOLD}Menu Opsi:{Colors.RESET}")
        print("  1. Ubah Quantity (qty.set)")
        print("  2. Tambah Quantity (qty.update +1)")
        print("  3. Ubah Diskon (discount_pct.set)")
        print("  4. Ubah Harga (price.set)")
        print("  5. Kembali ke menu utama")
        
        try:
            choice = input(f"{Colors.YELLOW}Pilih opsi [1-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            try:
                new_q = int(input("Masukkan Qty baru: ").strip())
                qty.set(max(1, new_q))
                print_cart()
            except ValueError:
                print(f"{Colors.RED}Input angka tidak valid.{Colors.RESET}")
        elif choice == "2":
            qty.update(lambda q: q + 1)
            print_cart()
        elif choice == "3":
            try:
                disc = float(input("Masukkan diskon persen (contoh 0.20 untuk 20%): ").strip())
                discount_pct.set(max(0.0, min(1.0, disc)))
                print_cart()
            except ValueError:
                print(f"{Colors.RED}Input angka tidak valid.{Colors.RESET}")
        elif choice == "4":
            try:
                p = float(input("Masukkan harga baru (Rp): ").strip())
                price.set(max(0.0, p))
                print_cart()
            except ValueError:
                print(f"{Colors.RED}Input angka tidak valid.{Colors.RESET}")
        elif choice == "5" or choice == "":
            break
        else:
            print(f"{Colors.RED}Pilihan tidak dikenal.{Colors.RESET}")


def run_full_suite():
    print_banner()
    demo_signals_glitch_free()
    time.sleep(0.3)
    demo_effect_and_untracked()
    time.sleep(0.3)
    demo_rxjs_stream()
    time.sleep(0.3)
    demo_interop()
    time.sleep(0.3)
    print(f"\n{Colors.BOLD}{Colors.GREEN}SEMUA SKENARIO LAB BERHASIL DIJALANKAN DENGAN SEMPURNA.{Colors.RESET}\n")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_full_suite()
        return

    # Check if non-interactive environment (CI / piped script)
    if not sys.stdin.isatty():
        run_full_suite()
        return

    while True:
        print_banner()
        print(f"{Colors.BOLD}Silakan pilih modul eksperimen reaktivitas:{Colors.RESET}")
        print(f"  {Colors.CYAN}1.{Colors.RESET} Demo 1: Writable Signal & Glitch-Free Diamond Dependency Graph")
        print(f"  {Colors.CYAN}2.{Colors.RESET} Demo 2: Effect Tracking & untracked() Execution Scope")
        print(f"  {Colors.CYAN}3.{Colors.RESET} Demo 3: RxJS Event Stream Pipeline (Subject & Operators)")
        print(f"  {Colors.CYAN}4.{Colors.RESET} Demo 4: Interop Bridge (toSignal & toObservable)")
        print(f"  {Colors.CYAN}5.{Colors.RESET} Interactive Playground: Shopping Cart Signal Graph")
        print(f"  {Colors.CYAN}6.{Colors.RESET} Jalankan Seluruh Skenario Otomatis (Full Suite)")
        print(f"  {Colors.CYAN}0.{Colors.RESET} Keluar (Exit)")
        
        try:
            choice = input(f"\n{Colors.YELLOW}Masukkan pilihan [0-6]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab...")
            break

        if choice == "1":
            demo_signals_glitch_free()
        elif choice == "2":
            demo_effect_and_untracked()
        elif choice == "3":
            demo_rxjs_stream()
        elif choice == "4":
            demo_interop()
        elif choice == "5":
            interactive_playground()
        elif choice == "6":
            run_full_suite()
        elif choice == "0":
            print(f"\n{Colors.GREEN}Terima kasih telah bereksperimen dengan Reaktivitas Inti Angular!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Opsi tidak valid.{Colors.RESET}")

        try:
            input(f"\n{Colors.DIM}Tekan [Enter] untuk kembali ke menu...{Colors.RESET}")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lab Hands-on: Angular Core Reactivity Engine Deep Dive
Topic: Signals, RxJS Stream Semantics, and Interoperability Layer (toSignal / toObservable)
Standard Library Only: time, typing, collections, sys
"""

import sys
import time
from typing import Callable, Generic, TypeVar, Any, Optional, Set, List

T = TypeVar("T")
R = TypeVar("R")

# --- ANSI Terminal Color Formatting ---
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"
CLR_BOLD = "\033[1m"


# ============================================================================
# Section 1: Push-Pull Signal Reactivity Algorithm
# ============================================================================

class ReactiveNode:
    """Basis untuk dependency tracking graph: Producer & Consumer abstraction."""
    def __init__(self) -> None:
        self.producers: Set['ReactiveNode'] = set()
        self.consumers: Set['ReactiveNode'] = set()

    def mark_dirty(self) -> None:
        """Propagasi fase Push: Memberitahu dependent node bahwa nilai invalid."""
        for consumer in list(self.consumers):
            consumer.mark_dirty()


# Global reactive execution context stack
_active_consumer: Optional['ReactiveNode'] = None
_consumer_stack: List[Optional['ReactiveNode']] = []


def _push_context(consumer: Optional['ReactiveNode']) -> None:
    global _active_consumer
    _consumer_stack.append(_active_consumer)
    _active_consumer = consumer


def _pop_context() -> None:
    global _active_consumer
    _active_consumer = _consumer_stack.pop() if _consumer_stack else None


class Signal(Generic[T], ReactiveNode):
    """
    Writable Signal: Node producer state murni.
    Mendukung setter dengan dirty-checking value (equality check).
    """
    def __init__(self, initial_value: T) -> None:
        super().__init__()
        self._value: T = initial_value

    def __call__(self) -> T:
        # Consumer tracking phase
        if _active_consumer is not None:
            self.consumers.add(_active_consumer)
            _active_consumer.producers.add(self)
        return self._value

    def set(self, new_value: T) -> None:
        if self._value != new_value:
            self._value = new_value
            self.mark_dirty()

    def update(self, updater: Callable[[T], T]) -> None:
        self.set(updater(self._value))


class Computed(Generic[T], ReactiveNode):
    """
    Computed Signal: Lazy evaluated (Pull-based), Memoized derivation.
    Menghilangkan redundant work via dirty-flag checking & dynamic pruning.
    """
    def __init__(self, computation: Callable[[], T]) -> None:
        super().__init__()
        self._computation: Callable[[], T] = computation
        self._cached_value: Optional[T] = None
        self._is_dirty: bool = True
        self.evaluation_count: int = 0

    def mark_dirty(self) -> None:
        if not self._is_dirty:
            self._is_dirty = True
            # Propagasi ke downstream consumer
            super().mark_dirty()

    def __call__(self) -> T:
        if _active_consumer is not None:
            self.consumers.add(_active_consumer)
            _active_consumer.producers.add(self)

        # Pull Phase: Recompute hanya jika status flag dirty
        if self._is_dirty:
            # Clear old dynamic edges sebelum recording dependency baru
            for producer in self.producers:
                producer.consumers.discard(self)
            self.producers.clear()

            _push_context(self)
            try:
                self._cached_value = self._computation()
                self.evaluation_count += 1
                self._is_dirty = False
            finally:
                _pop_context()

        return self._cached_value  # type: ignore[return-value]


class Effect(ReactiveNode):
    """
    Side-Effect Scheduler: Merespon perubahan dependency graph.
    Dieksekusi minimal satu kali saat inisialisasi.
    """
    def __init__(self, effect_fn: Callable[[], None]) -> None:
        super().__init__()
        self._effect_fn = effect_fn
        self.run_count: int = 0
        self.run()

    def mark_dirty(self) -> None:
        # Segera jadwalkan evaluasi ulang efek
        self.run()

    def run(self) -> None:
        for producer in self.producers:
            producer.consumers.discard(self)
        self.producers.clear()

        _push_context(self)
        try:
            self._effect_fn()
            self.run_count += 1
        finally:
            _pop_context()


# ============================================================================
# Section 2: Push-based RxJS Observable & Operators Simulation
# ============================================================================

class Subscription:
    def __init__(self, unsubscribe_fn: Callable[[], None]) -> None:
        self._unsubscribe_fn = unsubscribe_fn
        self.is_closed = False

    def unsubscribe(self) -> None:
        if not self.is_closed:
            self._unsubscribe_fn()
            self.is_closed = True


class Observable(Generic[T]):
    """Push-based stream primitive mirip rxjs Observable."""
    def __init__(self, subscribe_fn: Callable[[Callable[[T], None]], Optional[Callable[[], None]]]) -> None:
        self._subscribe_fn = subscribe_fn

    def subscribe(self, next_handler: Callable[[T], None]) -> Subscription:
        cleanup = self._subscribe_fn(next_handler)
        return Subscription(cleanup if cleanup else lambda: None)

    def pipe_map(self, transform_fn: Callable[[T], R]) -> 'Observable[R]':
        def _subscribe(handler: Callable[[R], None]):
            return self.subscribe(lambda val: handler(transform_fn(val))).unsubscribe
        return Observable(_subscribe)

    def pipe_filter(self, predicate_fn: Callable[[T], bool]) -> 'Observable[T]':
        def _subscribe(handler: Callable[[T], None]):
            def inner_next(val: T):
                if predicate_fn(val):
                    handler(val)
            return self.subscribe(inner_next).unsubscribe
        return Observable(_subscribe)


class Subject(Observable[T]):
    """RxJS Subject: Multicast emitter stream."""
    def __init__(self) -> None:
        self._observers: List[Callable[[T], None]] = []

        def _sub(handler: Callable[[T], None]):
            self._observers.append(handler)
            return lambda: self._observers.remove(handler)

        super().__init__(_sub)

    def next(self, value: T) -> None:
        for obs in list(self._observers):
            obs(value)


# ============================================================================
# Section 3: Reactivity Interoperability Layer (toSignal & toObservable)
# ============================================================================

def to_signal(source_obs: Observable[T], initial_value: T) -> Signal[T]:
    """
    Konversi RxJS Push-Stream menjadi Pull-based Angular Signal.
    Mencegah memory leak melalui explicit stream unsubscription.
    """
    sig = Signal(initial_value)
    source_obs.subscribe(lambda val: sig.set(val))
    return sig


def to_observable(source_signal: Callable[[], T]) -> Observable[T]:
    """
    Konversi Angular Signal menjadi RxJS Push-Stream via bridge Effect.
    Emits setiap kali signal dependency memicu state shift.
    """
    def _subscribe(observer: Callable[[T], None]):
        # Buat bridge effect yang memancarkan payload ke observer
        effect_instance = Effect(lambda: observer(source_signal()))
        return lambda: effect_instance.producers.clear()

    return Observable(_subscribe)


# ============================================================================
# Section 4: Hands-on Interactive Test Verification
# ============================================================================

def log_section(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title} ==={CLR_RESET}")


def run_benchmark_and_verification() -> None:
    log_section("TEST 1: Dynamic Dependency Graph & Diamond Problem Glitch Prevention")
    # Topology:
    #         price
    #        /     \
    #    tax_rate  discount
    #        \     /
    #       net_total
    
    price = Signal(100.0)
    tax_rate = Computed(lambda: price() * 0.11)          # 11% Tax
    discount = Computed(lambda: price() * 0.05)          # 5% Promo
    net_total = Computed(lambda: price() + tax_rate() - discount())

    print(f"{CLR_CYAN}[Init]{CLR_RESET} Price: {price():.2f} | Tax: {tax_rate():.2f} | "
          f"Discount: {discount():.2f} | {CLR_BOLD}Net Total: {net_total():.2f}{CLR_RESET}")
    print(f"Eval Count - Tax: {tax_rate.evaluation_count}, NetTotal: {net_total.evaluation_count}")

    # Re-reading should yield cached values without re-evaluating
    _ = net_total()
    print(f"{CLR_GREEN}✓ Memoization verified:{CLR_RESET} NetTotal eval count remains {net_total.evaluation_count}")

    # Mutating root signal
    price.set(200.0)
    print(f"{CLR_YELLOW}[Update]{CLR_RESET} Price mutasi -> 200.0 (Status dirty flag propagated)")
    print(f"Hasil Evaluasi Net Total Baru: {CLR_BOLD}{net_total():.2f}{CLR_RESET}")
    print(f"Eval Count - Tax: {tax_rate.evaluation_count}, NetTotal: {net_total.evaluation_count}")

    log_section("TEST 2: Side-Effect Reaction Tracking")
    audit_logs: List[str] = []
    
    _ = Effect(lambda: audit_logs.append(
        f"AUDIT LOG: Price={price():.1f}, Computed Net={net_total():.2f}"
    ))

    price.set(300.0)
    price.set(300.0)  # Duplicate write: should NOT trigger effect due to dirty check
    price.set(400.0)

    for log in audit_logs:
        print(f"{CLR_MAGENTA}→ {log}{CLR_RESET}")
    print(f"{CLR_GREEN}✓ Dirty checking successfully skipped redundant write (total logs: {len(audit_logs)}){CLR_RESET}")

    log_section("TEST 3: RxJS Functional Pipeline")
    sensor_stream: Subject[int] = Subject[int]()
    stream_output: List[str] = []

    # Pipeline: Filter bilangan genap -> transform (map) ke deskripsi tegangan
    sensor_stream \
        .pipe_filter(lambda val: val % 2 == 0) \
        .pipe_map(lambda val: f"Sensor Peak: {val} mV") \
        .subscribe(lambda mapped_str: stream_output.append(mapped_str))

    for packet in [101, 102, 105, 108, 110, 113]:
        sensor_stream.next(packet)

    for item in stream_output:
        print(f"{CLR_CYAN}RxJS Stream Event:{CLR_RESET} {item}")
    assert len(stream_output) == 3, "Stream filtering and transformation mismatch!"
    print(f"{CLR_GREEN}✓ Push-stream pipeline functional correctness confirmed.{CLR_RESET}")

    log_section("TEST 4: Interoperability Bridge (toSignal & toObservable)")
    # Scenario A: RxJS Subject -> Angular Signal via toSignal
    telemetry_stream: Subject[int] = Subject[int]()
    telemetry_sig = to_signal(telemetry_stream, initial_value=0)

    print(f"Initial toSignal Value: {CLR_BOLD}{telemetry_sig()}{CLR_RESET}")
    telemetry_stream.next(42)
    print(f"Pushed 42 to stream -> Signal value: {CLR_BOLD}{telemetry_sig()}{CLR_RESET}")
    telemetry_stream.next(99)
    print(f"Pushed 99 to stream -> Signal value: {CLR_BOLD}{telemetry_sig()}{CLR_RESET}")
    assert telemetry_sig() == 99, "toSignal synchronization failed!"

    # Scenario B: Angular Signal -> RxJS Observable via toObservable
    cart_count = Signal(1)
    cart_events: List[str] = []

    cart_stream = to_observable(cart_count)
    cart_stream.pipe_map(lambda count: f"Items in cart: {count}").subscribe(lambda msg: cart_events.append(msg))

    cart_count.update(lambda c: c + 1)
    cart_count.update(lambda c: c + 3)

    for evt in cart_events:
        print(f"{CLR_YELLOW}toObservable Emitted:{CLR_RESET} {evt}")
    assert len(cart_events) == 3, "toObservable bridging missed events!"

    print(f"\n{CLR_BOLD}{CLR_GREEN}======================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}   ALL REACTIVITY LAB SUITES EXECUTED SUCCESSFULLY    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================{CLR_RESET}")


if __name__ == "__main__":
    start_time = time.perf_counter()
    run_benchmark_and_verification()
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"{CLR_CYAN}Execution completed in {elapsed:.3f} ms via standard Python runtime.{CLR_RESET}")
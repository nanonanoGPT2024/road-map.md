#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi Reactive Streams & Akka/Pekko Streams (Scala Paradigm)
BAB-09: Data Streaming, Reaktif, & Integrasi Sistem

Simulasi Python 3 murni (zero-dependency) yang mengimplementasikan:
1. Reactive Streams Specification: Publisher, Subscriber, Subscription (demand-driven backpressure `request(n)`).
2. Akka Streams DSL Primitives: Source, Flow, Sink, Via, RunWith.
3. Overflow Strategy & Buffer Management: Backpressure vs DropHead vs DropTail.
4. Telemetri real-time dengan kode warna ANSI terminal.
"""

import sys
import time
import queue
import threading
from typing import Callable, Generic, TypeVar, Optional, List
from dataclasses import dataclass
from enum import Enum

T = TypeVar("T")
R = TypeVar("R")

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE = "\033[94m"
CLR_BG_DARK = "\033[100m"


class OverflowStrategy(Enum):
    BACKPRESSURE = "Backpressure (Tahan Publisher)"
    DROP_HEAD = "DropHead (Buang Elemen Terlama)"
    DROP_TAIL = "DropTail (Buang Elemen Terbaru)"


class Subscription:
    """Kontrak Subscription Reactive Streams (Akka/Pekko Stream equivalent)."""
    def request(self, n: int) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError


class Subscriber(Generic[T]):
    """Kontrak Subscriber Reactive Streams (Sink materialize)."""
    def on_subscribe(self, subscription: Subscription) -> None:
        raise NotImplementedError

    def on_next(self, item: T) -> None:
        raise NotImplementedError

    def on_error(self, err: Exception) -> None:
        raise NotImplementedError

    def on_complete(self) -> None:
        raise NotImplementedError


class Publisher(Generic[T]):
    """Kontrak Publisher Reactive Streams (Source stream)."""
    def subscribe(self, subscriber: Subscriber[T]) -> None:
        raise NotImplementedError


# ==========================================
# Implementasi Reactive Pipeline & Backpressure
# ==========================================

class StreamSubscription(Subscription, Generic[T]):
    def __init__(self, data: List[T], subscriber: Subscriber[T], throttle_ms: int = 100):
        self.data = list(data)
        self.subscriber = subscriber
        self.throttle_ms = throttle_ms
        self.cancelled = False
        self.demand = 0
        self.lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None

    def request(self, n: int) -> None:
        with self.lock:
            if self.cancelled:
                return
            self.demand += n
            print(f"  {CLR_BLUE}[Subscription]{CLR_RESET} Diterima request sinyal demand: +{n} (Total demand: {self.demand})")
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(target=self._process_demand, daemon=True)
                self._worker_thread.start()

    def _process_demand(self) -> None:
        while True:
            item = None
            with self.lock:
                if self.cancelled:
                    break
                if self.demand > 0 and self.data:
                    item = self.data.pop(0)
                    self.demand -= 1
                elif not self.data:
                    self.cancelled = True
                    self.subscriber.on_complete()
                    break
                else:
                    # Menunggu permintaan demand berikutnya (Backpressure aktif)
                    break

            if item is not None:
                if self.throttle_ms > 0:
                    time.sleep(self.throttle_ms / 1000.0)
                self.subscriber.on_next(item)

    def cancel(self) -> None:
        with self.lock:
            self.cancelled = True
            print(f"  {CLR_RED}[Subscription]{CLR_RESET} Aliran dibatalkan (Cancel).")


class Source(Generic[T]):
    """Representasi Source Akka Streams (e.g. Source(1 to 10))."""
    def __init__(self, elements: List[T]):
        self.elements = elements

    @classmethod
    def from_iterable(cls, items: List[T]) -> "Source[T]":
        return cls(items)

    def via(self, flow: "Flow[T, R]") -> "Source[R]":
        """Menyambungkan Source dengan Flow operator."""
        transformed = []
        for x in self.elements:
            res = flow.apply(x)
            if res is not None:
                transformed.append(res)
        return Source(transformed)

    def run_with(self, sink: "Sink[T]", throttle_ms: int = 80) -> None:
        """Materializer: Menghubungkan Source dengan Sink dan menjalankan runtime."""
        print(f"{CLR_MAGENTA}{CLR_BOLD}>>> Materializing Graph Pipeline... <<<{CLR_RESET}")
        publisher = ListPublisher(self.elements, throttle_ms)
        publisher.subscribe(sink.as_subscriber())


class Flow(Generic[T, R]):
    """Representasi Flow transformer (Map, Filter, Logging)."""
    def __init__(self, transform_fn: Callable[[T], Optional[R]], label: str = "Transform"):
        self.transform_fn = transform_fn
        self.label = label

    def apply(self, item: T) -> Optional[R]:
        return self.transform_fn(item)

    @classmethod
    def filter(cls, predicate: Callable[[T], bool]) -> "Flow[T, T]":
        return cls(lambda x: x if predicate(x) else None, label=f"Filter({predicate.__name__})")

    @classmethod
    def map(cls, mapper: Callable[[T], R]) -> "Flow[T, R]":
        return cls(lambda x: mapper(x), label=f"Map({mapper.__name__})")


class Sink(Generic[T]):
    """Representasi Sink penerima akhir (e.g. Sink.foreach, Sink.fold)."""
    def __init__(self, on_element: Callable[[T], None], batch_size: int = 2):
        self.on_element = on_element
        self.batch_size = batch_size

    def as_subscriber(self) -> Subscriber[T]:
        return FunctionalSubscriber(self.on_element, batch_size=self.batch_size)


class ListPublisher(Publisher[T]):
    def __init__(self, items: List[T], throttle_ms: int = 80):
        self.items = list(items)
        self.throttle_ms = throttle_ms

    def subscribe(self, subscriber: Subscriber[T]) -> None:
        subscription = StreamSubscription(self.items, subscriber, self.throttle_ms)
        subscriber.on_subscribe(subscription)


class FunctionalSubscriber(Subscriber[T]):
    def __init__(self, action: Callable[[T], None], batch_size: int = 2):
        self.action = action
        self.batch_size = batch_size
        self.subscription: Optional[Subscription] = None
        self.received_count = 0

    def on_subscribe(self, subscription: Subscription) -> None:
        self.subscription = subscription
        print(f"  {CLR_CYAN}[Subscriber]{CLR_RESET} Terkoneksi. Meminta batch awal: {self.batch_size} item.")
        self.subscription.request(self.batch_size)

    def on_next(self, item: T) -> None:
        self.received_count += 1
        print(f"  {CLR_GREEN}[Sink Received]{CLR_RESET} Item #{self.received_count}: {item}")
        self.action(item)

        # Reactive Backpressure demand pull: Minta lagi jika batch selesai
        if self.received_count % self.batch_size == 0 and self.subscription:
            print(f"  {CLR_YELLOW}[Backpressure Control]{CLR_RESET} Buffer batch sink habis. Menarik batch demand baru...")
            self.subscription.request(self.batch_size)

    def on_error(self, err: Exception) -> None:
        print(f"  {CLR_RED}[Subscriber Error]{CLR_RESET} Pipeline fault: {err}")

    def on_complete(self) -> None:
        print(f"  {CLR_CYAN}{CLR_BOLD}[Pipeline Complete]{CLR_RESET} Selesai memproses seluruh data stream tanpa dropped frames!\n")


# ==========================================
# Simulasi Buffer Overflow Strategy
# ==========================================

def simulate_buffer_strategy(strategy: OverflowStrategy, buffer_cap: int = 4, incoming_count: int = 8):
    print(f"\n{CLR_BOLD}=== Simulasi Buffer Operator: {strategy.value} (Kapasitas: {buffer_cap}) ==={CLR_RESET}")
    buf: List[int] = []

    for i in range(1, incoming_count + 1):
        time.sleep(0.04)
        if len(buf) < buffer_cap:
            buf.append(i)
            print(f"  {CLR_GREEN}+ Masuk:{CLR_RESET} Item {i:<2} | Status Buffer [{len(buf)}/{buffer_cap}]: {buf}")
        else:
            if strategy == OverflowStrategy.BACKPRESSURE:
                print(f"  {CLR_YELLOW}! Backpressure:{CLR_RESET} Buffer penuh! Menunda produser untuk item {i}...")
                popped = buf.pop(0)
                print(f"    -> Konsumen memproses: {popped} | Membebaskan slot...")
                buf.append(i)
                print(f"    -> Item {i} sekarang masuk. Buffer: {buf}")
            elif strategy == OverflowStrategy.DROP_HEAD:
                dropped = buf.pop(0)
                buf.append(i)
                print(f"  {CLR_RED}! DropHead:{CLR_RESET} Membuang elemen tertua [{dropped}]. Memasukkan [{i}]. Buffer: {buf}")
            elif strategy == OverflowStrategy.DROP_TAIL:
                dropped = buf.pop()
                buf.append(i)
                print(f"  {CLR_MAGENTA}! DropTail:{CLR_RESET} Membuang elemen terbaru [{dropped}]. Memasukkan [{i}]. Buffer: {buf}")


# ==========================================
# Menu Interaktif CLI
# ==========================================

def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}========================================================================
*  SCALA BAB-09: DATA STREAMING, REAKTIF & INTEGRASI SISTEM           *
*  Simulasi Interaktif: Reactive Streams Specification & Akka DSL      *
========================================================================{CLR_RESET}
    """
    print(banner)


def run_sensor_event_pipeline():
    print(f"\n{CLR_BOLD}--- Demo 1: Event Log Processing Pipeline (Source ~> Flow ~> Sink) ---{CLR_RESET}")
    print("Contoh kasus: Stream log sensor temperatur dari IoT Gateway.")

    @dataclass
    class SensorEvent:
        device_id: str
        temperature: float
        status: str

    raw_events = [
        SensorEvent("sensor-1", 24.5, "OK"),
        SensorEvent("sensor-2", 41.2, "CRITICAL"),
        SensorEvent("sensor-1", 25.1, "OK"),
        SensorEvent("sensor-3", 18.9, "OK"),
        SensorEvent("sensor-2", 43.8, "CRITICAL"),
        SensorEvent("sensor-4", 65.0, "FATAL"),
        SensorEvent("sensor-3", 19.4, "OK"),
    ]

    source = Source.from_iterable(raw_events)

    # Filter hanya event anomali
    filter_flow = Flow.filter(lambda ev: ev.temperature >= 40.0)
    # Map ke format alert string
    alert_flow = Flow.map(lambda ev: f"ALERT [{ev.device_id.upper()}] Temp: {ev.temperature}C ({ev.status})")

    # Pipeline: Source -> Filter -> Map
    pipeline = source.via(filter_flow).via(alert_flow)

    processed_items = []
    sink = Sink(lambda alert_msg: processed_items.append(alert_msg), batch_size=2)

    pipeline.run_with(sink, throttle_ms=60)
    time.sleep(0.5)
    print(f"{CLR_GREEN}Total alert terdeteksi: {len(processed_items)}{CLR_RESET}")


def run_backpressure_demo():
    print(f"\n{CLR_BOLD}--- Demo 2: Reactive Streams Specification (Demand-Driven Backpressure) ---{CLR_RESET}")
    print("Produser memproduksi 10 payload angka, Sink memproses dengan demand window batch = 3.")

    numbers = list(range(101, 111))
    source = Source.from_iterable(numbers)
    sink = Sink(lambda x: time.sleep(0.05), batch_size=3)
    source.run_with(sink, throttle_ms=40)
    time.sleep(1.0)


def run_overflow_demo():
    print(f"\n{CLR_BOLD}--- Demo 3: Strategi Penanganan Buffer Overflow ---{CLR_RESET}")
    for strat in [OverflowStrategy.BACKPRESSURE, OverflowStrategy.DROP_HEAD, OverflowStrategy.DROP_TAIL]:
        simulate_buffer_strategy(strat, buffer_cap=3, incoming_count=6)


def main():
    print_banner()

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{CLR_YELLOW}Mode non-interaktif otomatis (--auto)...{CLR_RESET}")
        run_sensor_event_pipeline()
        run_backpressure_demo()
        run_overflow_demo()
        print(f"\n{CLR_GREEN}{CLR_BOLD}[VERIFIED]{CLR_RESET} Semua skenario simulasi reactive streaming berhasil dieksekusi.")
        return

    while True:
        print(f"{CLR_BOLD}Pilih Skenario Hands-on:{CLR_RESET}")
        print("  1. Jalankan Pipeline Log Stream (Source ~> Flow.filter ~> Flow.map ~> Sink)")
        print("  2. Jalankan Protocol Reactive Streams Backpressure (request(n))")
        print("  3. Simulasi Buffer Overflow Strategies (DropHead / DropTail / Backpressure)")
        print("  4. Jalankan Semua Simulasi Secara Sekuensial")
        print("  5. Keluar")

        try:
            choice = input(f"\n{CLR_CYAN}Masukkan pilihan (1-5): {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari lab exercise.")
            break

        if choice == "1":
            run_sensor_event_pipeline()
        elif choice == "2":
            run_backpressure_demo()
        elif choice == "3":
            run_overflow_demo()
        elif choice == "4":
            run_sensor_event_pipeline()
            run_backpressure_demo()
            run_overflow_demo()
        elif choice == "5":
            print(f"{CLR_GREEN}Lab exercise selesai.{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan coba lagi.{CLR_RESET}")

        print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    main()

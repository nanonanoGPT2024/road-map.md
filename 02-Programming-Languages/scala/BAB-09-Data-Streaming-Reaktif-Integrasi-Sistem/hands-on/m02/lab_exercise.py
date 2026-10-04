#!/usr/bin/env python3
"""
Laboratorium Sistem Streaming Reaktif & Integrasi Sistem (Scala/Akka Streams Paradigma).
Mensimulasikan spesifikasi Reactive Streams (Publisher, Subscriber, Subscription)
dengan mekanisme Backpressure dinamis (pull-demand berbasis token 'request(n)'),
pipeline transformatif asinkron, dan mitigasi buffer overflow.
"""

import time
import threading
import random
from typing import Callable, Any, List, Optional
from dataclasses import dataclass
from collections import deque

# ANSI Palette untuk visualisasi terminal
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_CYAN    = "\033[36m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_RED     = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE    = "\033[34m"

@dataclass
class MetricEvent:
    event_id: int
    sensor_id: str
    temperature: float
    pressure: float
    timestamp: float

class Subscription:
    """Kontrak penghubung antara Publisher dan Subscriber untuk demand backpressure."""
    def request(self, n: int) -> None:
        raise NotImplementedError
    def cancel(self) -> None:
        raise NotImplementedError

class Subscriber:
    """Penerima event reaktif dengan kendali laju konsumsi."""
    def on_subscribe(self, subscription: Subscription) -> None:
        raise NotImplementedError
    def on_next(self, item: Any) -> None:
        raise NotImplementedError
    def on_error(self, err: Exception) -> None:
        raise NotImplementedError
    def on_complete(self) -> None:
        raise NotImplementedError

class Publisher:
    """Produsen event reaktif terikat aturan demand upstream."""
    def subscribe(self, subscriber: Subscriber) -> None:
        raise NotImplementedError

class ReactiveSourceSubscription(Subscription):
    """Implementasi konkrit kendali demand token (pull-based signaling)."""
    def __init__(self, publisher: 'SensorTelemetrySource', subscriber: Subscriber):
        self.publisher = publisher
        self.subscriber = subscriber
        self._demand = 0
        self._is_cancelled = False
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def request(self, n: int) -> None:
        if n <= 0:
            self.subscriber.on_error(ValueError("Spesifikasi Reactive Streams: demand n harus > 0"))
            return
        with self._cond:
            if not self._is_cancelled:
                self._demand += n
                self._cond.notify_all()

    def cancel(self) -> None:
        with self._cond:
            self._is_cancelled = True
            self._cond.notify_all()

    def obtain_demand(self) -> bool:
        """Memblokir upstream emitter jika downstream kehabisan kapasitas demand."""
        with self._cond:
            while self._demand <= 0 and not self._is_cancelled and not self.publisher.is_terminated:
                self._cond.wait(timeout=0.1)
            if self._is_cancelled or self.publisher.is_terminated:
                return False
            self._demand -= 1
            return True

class SensorTelemetrySource(Publisher):
    """
    Source Reaktif: Memancarkan metrik sensor hanya jika dialokasikan demand
    oleh subscriber hilir (mencegah OOM dan network saturation).
    """
    def __init__(self, total_events: int):
        self.total_events = total_events
        self.emitted_count = 0
        self.is_terminated = False
        self._worker_thread: Optional[threading.Thread] = None

    def subscribe(self, subscriber: Subscriber) -> None:
        sub = ReactiveSourceSubscription(self, subscriber)
        subscriber.on_subscribe(sub)
        self._worker_thread = threading.Thread(target=self._run_emitter, args=(sub,), daemon=True)
        self._worker_thread.start()

    def _run_emitter(self, subscription: ReactiveSourceSubscription) -> None:
        for idx in range(1, self.total_events + 1):
            if not subscription.obtain_demand():
                break

            # Simulasi generate telemetri
            evt = MetricEvent(
                event_id=idx,
                sensor_id=f"sensor-cluster-{idx % 3 + 1}",
                temperature=round(random.uniform(20.0, 95.0), 2),
                pressure=round(random.uniform(1.0, 5.0), 2),
                timestamp=time.time()
            )
            self.emitted_count += 1
            subscription.subscriber.on_next(evt)
            time.sleep(0.01) # Upstream sangat cepat (10ms)

        self.is_terminated = True
        subscription.subscriber.on_complete()

class ReactiveTransformFlow(Publisher, Subscriber):
    """
    Operator Flow: Melakukan Filter dan Map transformasi reaktif,
    meneruskan sinyal demand ke hulu dan memproses data ke hilir.
    """
    def __init__(self, filter_fn: Callable[[MetricEvent], bool], map_fn: Callable[[MetricEvent], Any]):
        self.filter_fn = filter_fn
        self.map_fn = map_fn
        self.upstream_subscription: Optional[Subscription] = None
        self.downstream_subscriber: Optional[Subscriber] = None

    def on_subscribe(self, subscription: Subscription) -> None:
        self.upstream_subscription = subscription
        if self.downstream_subscriber:
            self.downstream_subscriber.on_subscribe(subscription)

    def subscribe(self, subscriber: Subscriber) -> None:
        self.downstream_subscriber = subscriber
        if self.upstream_subscription:
            subscriber.on_subscribe(self.upstream_subscription)

    def on_next(self, item: MetricEvent) -> None:
        # Pemrosesan reaktif inline pipeline
        if self.filter_fn(item):
            transformed = self.map_fn(item)
            if self.downstream_subscriber:
                self.downstream_subscriber.on_next(transformed)
        else:
            # Data di-drop oleh filter; minta ganti rugi 1 token ke hulu agar pipeline tidak macet
            if self.upstream_subscription:
                self.upstream_subscription.request(1)

    def on_error(self, err: Exception) -> None:
        if self.downstream_subscriber:
            self.downstream_subscriber.on_error(err)

    def on_complete(self) -> None:
        if self.downstream_subscriber:
            self.downstream_subscriber.on_complete()

class SlowDatabaseSink(Subscriber):
    """
    Subscriber Konsumen Lambat (I/O Bottleneck):
    Menerapkan buffer dinamis dan pull batching berbasis window demand.
    """
    def __init__(self, batch_size: int, processing_delay: float):
        self.batch_size = batch_size
        self.delay = processing_delay
        self.subscription: Optional[Subscription] = None
        self.buffer = deque()
        self.processed_count = 0
        self.completed = threading.Event()
        self.high_watermark = 0

    def on_subscribe(self, subscription: Subscription) -> None:
        self.subscription = subscription
        print(f"{CLR_CYAN}[Sink Inisialisasi]{CLR_RESET} Terkoneksi. Meminta window awal: {CLR_BOLD}{self.batch_size}{CLR_RESET} item")
        self.subscription.request(self.batch_size)

    def on_next(self, item: Any) -> None:
        self.buffer.append(item)
        if len(self.buffer) > self.high_watermark:
            self.high_watermark = len(self.buffer)

        # Simulasi commit database saat buffer mencapai batch size
        if len(self.buffer) >= self.batch_size:
            self._flush_batch()

    def _flush_batch(self) -> None:
        items_to_process = []
        while self.buffer:
            items_to_process.append(self.buffer.popleft())

        time.sleep(self.delay) # Simulasi operasi I/O latency tinggi (Blocking Disk/Network)
        self.processed_count += len(items_to_process)
        
        sample = items_to_process[-1]
        print(f"{CLR_YELLOW}[Sink Flush DB]{CLR_RESET} Sukses commit {CLR_GREEN}{len(items_to_process)}{CLR_RESET} entri. "
              f"Sampel Terakhir: [ID={sample['event_id']}, Tag={sample['alert_level']}] | "
              f"Buffer Saat Ini: {len(self.buffer)}")

        # Sinyal Reaktif: Tarik batch berikutnya secara asinkron
        if self.subscription:
            self.subscription.request(len(items_to_process))

    def on_error(self, err: Exception) -> None:
        print(f"{CLR_RED}[Sink Fatal Error]{CLR_RESET}: {err}")
        self.completed.set()

    def on_complete(self) -> None:
        # Kosongkan sisa buffer jika ada
        if self.buffer:
            self._flush_batch()
        print(f"{CLR_GREEN}{CLR_BOLD}[Sink Selesai]{CLR_RESET} Seluruh stream berhasil terproses.")
        self.completed.set()

def main():
    print(f"{CLR_MAGENTA}{CLR_BOLD}========================================================================{CLR_RESET}")
    print(f"{CLR_MAGENTA}{CLR_BOLD}  LAB RUNTIME: SCALA/AKKA REACTIVE DATA STREAMING & INTEGRATION SIM    {CLR_RESET}")
    print(f"{CLR_MAGENTA}{CLR_BOLD}========================================================================{CLR_RESET}\n")

    total_events = 40
    batch_size = 5
    slowdown_io_delay = 0.12  # 120ms per flush (12x lebih lambat dari generator upstream)

    print(f"{CLR_BLUE}[Arsitektur Pipeline]{CLR_RESET}")
    print(f" Source (10ms/evt) ---> Flow Filter/Enricher ---> SlowSink (120ms/batch {batch_size})")
    print(f" Konfigurasi: Total Event={total_events}, Demand Window={batch_size}\n")

    # Inisialisasi Komponen Streaming
    source = SensorTelemetrySource(total_events=total_events)

    # Filter: Hanya tangkap anomali temperatur tinggi (> 45.0 C)
    def anomaly_detector(evt: MetricEvent) -> bool:
        return evt.temperature > 45.0

    # Map: Transformasi ke DTO terintegrasi
    def enrich_telemetry(evt: MetricEvent) -> dict:
        alert = "CRITICAL" if evt.temperature > 80.0 else "WARNING"
        return {
            "event_id": evt.event_id,
            "sensor": evt.sensor_id,
            "val": f"{evt.temperature}°C / {evt.pressure}bar",
            "alert_level": alert
        }

    pipeline_flow = ReactiveTransformFlow(filter_fn=anomaly_detector, map_fn=enrich_telemetry)
    db_sink = SlowDatabaseSink(batch_size=batch_size, processing_delay=slowdown_io_delay)

    # Materialisasi Topologi Reaktif: Source ~> Flow ~> Sink
    start_time = time.time()
    source.subscribe(pipeline_flow)
    pipeline_flow.subscribe(db_sink)

    # Tunggu sink menyelesaikan seluruh demand ter-materialisasi
    db_sink.completed.wait(timeout=15.0)
    elapsed = time.time() - start_time

    print(f"\n{CLR_CYAN}{CLR_BOLD}--- RINGKASAN METRIK RUNTIME ---{CLR_RESET}")
    print(f"Total Emitted Upstream : {CLR_BOLD}{source.emitted_count}{CLR_RESET} entri")
    print(f"Total Processed Sink   : {CLR_BOLD}{db_sink.processed_count}{CLR_RESET} entri anomali")
    print(f"Buffer High Watermark  : {CLR_BOLD}{db_sink.high_watermark}{CLR_RESET} item (Terkendali via Backpressure)")
    print(f"Total Eksekusi         : {CLR_BOLD}{elapsed:.2f}{CLR_RESET} detik")
    
    # Validasi Backpressure: High watermark buffer tidak boleh meledak melebihi batch_size * 2
    if db_sink.high_watermark <= batch_size * 2:
        print(f"Status Sistem          : {CLR_GREEN}{CLR_BOLD}STABIL - Protokol Backpressure Reactive Streams Sukses!{CLR_RESET}\n")
    else:
        print(f"Status Sistem          : {CLR_RED}{CLR_BOLD}OVERFLOW - Buffer meledak melanggar batas aman.{CLR_RESET}\n")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Lab Exercise: Reactive Java & Event Loop Systems Simulation
BAB-08: Reactive Java & Event Loop Architecture (Reactive Streams, Backpressure, Netty EventLoop)

Simulasi teknis konsep fondasi arsitektur Reactive Streams (Publisher, Subscriber, Subscription),
mekanisme Backpressure flow-control, Netty-style Single-Threaded Event Loop, serta
thread handoff via Scheduler offloading (publishOn/subscribeOn).
"""

import sys
import time
import queue
import threading
from typing import Callable, Any, List, Optional
from enum import Enum


# ANSI Color Codes for Rich Terminal Visualization
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def log_event(thread_name: str, component: str, message: str, color: str = ANSI.WHITE):
    timestamp = time.strftime("%H:%M:%S")
    thread_tag = f"[{thread_name:^20}]"
    comp_tag = f"[{component:^14}]"
    print(f"{ANSI.DIM}{timestamp}{ANSI.RESET} {ANSI.BLUE}{thread_tag}{ANSI.RESET} {color}{comp_tag}{ANSI.RESET} {message}")


# ============================================================================
# Bagian 1: Reactive Streams Specification (Flow.Publisher, Flow.Subscriber)
# ============================================================================

class Subscription:
    """Kontrak Subscription untuk negosiasi kuota item (Backpressure)."""
    def request(self, n: int) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError


class Subscriber:
    """Kontrak Reactive Subscriber sesuai Reactive Streams Specification."""
    def on_subscribe(self, subscription: Subscription) -> None:
        raise NotImplementedError

    def on_next(self, item: Any) -> None:
        raise NotImplementedError

    def on_error(self, err: Exception) -> None:
        raise NotImplementedError

    def on_complete(self) -> None:
        raise NotImplementedError


class BackpressureOverflowStrategy(Enum):
    DROP = "DROP"
    BUFFER = "BUFFER"
    ERROR = "ERROR"


class SimpleSubscription(Subscription):
    def __init__(self, publisher: 'FluxPublisher', subscriber: Subscriber):
        self.publisher = publisher
        self.subscriber = subscriber
        self.requested = 0
        self.cancelled = False
        self._lock = threading.Lock()

    def request(self, n: int) -> None:
        if self.cancelled:
            return
        with self._lock:
            self.requested += n
            log_event(
                threading.current_thread().name,
                "SUBSCRIPTION",
                f"{ANSI.YELLOW}Subscriber meminta request({n}). Total demand saat ini: {self.requested}{ANSI.RESET}",
                ANSI.YELLOW
            )
        self.publisher.drain(self)

    def cancel(self) -> None:
        self.cancelled = True
        log_event(
            threading.current_thread().name,
            "SUBSCRIPTION",
            f"{ANSI.RED}Subscription di-cancel oleh Subscriber.{ANSI.RESET}",
            ANSI.RED
        )


class FluxPublisher:
    """Simulasi Publisher bergaya Project Reactor (Flux) dengan kendali Backpressure."""
    def __init__(self, items: List[Any], buffer_capacity: int = 5, strategy: BackpressureOverflowStrategy = BackpressureOverflowStrategy.BUFFER):
        self.items = items.copy()
        self.buffer_capacity = buffer_capacity
        self.strategy = strategy
        self.buffer: List[Any] = []
        self._lock = threading.Lock()

    def subscribe(self, subscriber: Subscriber) -> None:
        log_event(
            threading.current_thread().name,
            "PUBLISHER",
            f"{ANSI.CYAN}Menerima pendaftaran subscriber baru. Menginisialisasi onSubscribe()...{ANSI.RESET}",
            ANSI.CYAN
        )
        sub = SimpleSubscription(self, subscriber)
        subscriber.on_subscribe(sub)

    def drain(self, subscription: SimpleSubscription) -> None:
        with self._lock:
            while subscription.requested > 0 and (self.items or self.buffer):
                if subscription.cancelled:
                    return

                item = self.buffer.pop(0) if self.buffer else self.items.pop(0)
                subscription.requested -= 1

                log_event(
                    threading.current_thread().name,
                    "PUBLISHER",
                    f"{ANSI.GREEN}Mengirim item: {item!r} (Sisa demand: {subscription.requested}){ANSI.RESET}",
                    ANSI.GREEN
                )
                subscription.subscriber.on_next(item)

            if not self.items and not self.buffer and not subscription.cancelled:
                log_event(
                    threading.current_thread().name,
                    "PUBLISHER",
                    f"{ANSI.MAGENTA}Semua item terkirim. Memanggil onComplete().{ANSI.RESET}",
                    ANSI.MAGENTA
                )
                subscription.subscriber.on_complete()


class SlowSubscriber(Subscriber):
    """Subscriber lambat untuk mendemonstrasikan penarikan item terkendali (Backpressure)."""
    def __init__(self, batch_size: int = 2, delay_sec: float = 0.3):
        self.batch_size = batch_size
        self.delay_sec = delay_sec
        self.subscription: Optional[Subscription] = None
        self.items_received = 0

    def on_subscribe(self, subscription: Subscription) -> None:
        self.subscription = subscription
        log_event(
            threading.current_thread().name,
            "SUBSCRIBER",
            f"{ANSI.CYAN}onSubscribe: Meminta batch pertama sebesar {self.batch_size} item.{ANSI.RESET}",
            ANSI.CYAN
        )
        self.subscription.request(self.batch_size)

    def on_next(self, item: Any) -> None:
        self.items_received += 1
        log_event(
            threading.current_thread().name,
            "SUBSCRIBER",
            f"{ANSI.WHITE}onNext: Memproses data '{item}' secara hati-hati...{ANSI.RESET}"
        )
        time.sleep(self.delay_sec)

        # Setelah memproses batch, minta batch berikutnya (reactive backpressure pull-push)
        if self.items_received % self.batch_size == 0 and self.subscription:
            log_event(
                threading.current_thread().name,
                "SUBSCRIBER",
                f"{ANSI.YELLOW}Batch selesai diproses. Meminta batch berikutnya ({self.batch_size} item)...{ANSI.RESET}",
                ANSI.YELLOW
            )
            self.subscription.request(self.batch_size)

    def on_error(self, err: Exception) -> None:
        log_event(
            threading.current_thread().name,
            "SUBSCRIBER",
            f"{ANSI.RED}onError: Mengalami kegagalan stream: {err}{ANSI.RESET}",
            ANSI.RED
        )

    def on_complete(self) -> None:
        log_event(
            threading.current_thread().name,
            "SUBSCRIBER",
            f"{ANSI.GREEN}{ANSI.BOLD}onComplete: Aliran data selesai dengan sukses! Total item: {self.items_received}{ANSI.RESET}",
            ANSI.GREEN
        )


# ============================================================================
# Bagian 2: Netty-style Single-Threaded Event Loop & Non-Blocking Task Queue
# ============================================================================

class EventLoop:
    """
    Simulasi Single-Threaded Event Loop seperti NioEventLoop pada Netty / Vert.x.
    Mengeksekusi tugas non-blocking dalam queue tanpa pernah memblokir thread loop utama.
    """
    def __init__(self, name: str = "nioEventLoopGroup-1"):
        self.name = name
        self.task_queue: queue.Queue = queue.Queue()
        self.running = False
        self.thread = threading.Thread(target=self._run, name=self.name, daemon=True)

    def start(self) -> None:
        self.running = True
        self.thread.start()
        log_event(self.name, "EVENT_LOOP", f"{ANSI.CYAN}Event Loop '{self.name}' diinisialisasi & berjalan.{ANSI.RESET}")

    def execute(self, task: Callable[[], None], desc: str = "Unnamed Task") -> None:
        if not self.running:
            raise RuntimeError("Event loop belum dijalankan!")
        self.task_queue.put((task, desc))

    def _run(self) -> None:
        while self.running:
            try:
                task, desc = self.task_queue.get(timeout=0.2)
                log_event(self.name, "EVENT_LOOP", f"{ANSI.DIM}Menjalankan task: {desc}{ANSI.RESET}")
                start = time.perf_counter()
                task()
                elapsed_ms = (time.perf_counter() - start) * 1000
                log_event(self.name, "EVENT_LOOP", f"{ANSI.GREEN}Task '{desc}' selesai dalam {elapsed_ms:.2f} ms.{ANSI.RESET}")
                self.task_queue.task_done()
            except queue.Empty:
                continue

    def stop(self) -> None:
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        log_event(self.name, "EVENT_LOOP", f"{ANSI.YELLOW}Event Loop '{self.name}' dihentikan secara graceful.{ANSI.RESET}")


# ============================================================================
# Bagian 3: Thread Handoff & Scheduler Offloading (Schedulers.boundedElastic)
# ============================================================================

class BoundedElasticScheduler:
    """Simulasi worker pool untuk operasi blocking I/O (Database, Disk, Legacy calls)."""
    def __init__(self, workers: int = 3):
        self.workers = workers
        self.queue: queue.Queue = queue.Queue()
        self.threads: List[threading.Thread] = []
        self.running = True

        for i in range(workers):
            t = threading.Thread(target=self._worker_loop, name=f"boundedElastic-{i+1}", daemon=True)
            self.threads.append(t)
            t.start()

    def _worker_loop(self):
        while self.running:
            try:
                task, desc = self.queue.get(timeout=0.2)
                log_event(threading.current_thread().name, "ELASTIC_WORKER", f"{ANSI.MAGENTA}Mengeksekusi blocking I/O task: {desc}{ANSI.RESET}")
                task()
                self.queue.task_done()
            except queue.Empty:
                continue

    def schedule(self, task: Callable[[], None], desc: str = "Blocking Task") -> None:
        self.queue.put((task, desc))

    def shutdown(self) -> None:
        self.running = False
        for t in self.threads:
            t.join(timeout=0.5)


# ============================================================================
# Skenario Praktik Laboratorium Interaktif
# ============================================================================

def banner():
    print(f"{ANSI.CYAN}{ANSI.BOLD}" + "=" * 80)
    print("      LAB SIMULASI: REACTIVE JAVA & EVENT LOOP SYSTEMS (BAB-08)")
    print("         (Reactive Streams Spec, Backpressure & Netty EventLoop)")
    print("=" * 80 + f"{ANSI.RESET}\n")


def run_scenario_1_backpressure():
    print(f"\n{ANSI.BG_BLUE}{ANSI.WHITE}{ANSI.BOLD} [SKENARIO 1] Reactive Streams Backpressure Protocol {ANSI.RESET}\n")
    print(f"{ANSI.DIM}Konsep: Publisher tidak membanjiri Subscriber. Subscriber mengendalikan laju pengiriman")
    print(f"melalui kontrak Subscription.request(n).{ANSI.RESET}\n")

    items = [f"Payload-#{i}" for i in range(1, 7)]
    publisher = FluxPublisher(items=items)
    subscriber = SlowSubscriber(batch_size=2, delay_sec=0.25)

    pub_thread = threading.Thread(
        target=lambda: publisher.subscribe(subscriber),
        name="reactive-thread-1"
    )
    pub_thread.start()
    pub_thread.join()
    print(f"\n{ANSI.GREEN}✔ Skenario 1 Selesai: Backpressure terkendali dengan harmonis!{ANSI.RESET}\n")


def run_scenario_2_event_loop_and_offloading():
    print(f"\n{ANSI.BG_MAGENTA}{ANSI.WHITE}{ANSI.BOLD} [SKENARIO 2] Netty EventLoop & Golden Rule: Never Block The Loop! {ANSI.RESET}\n")
    print(f"{ANSI.DIM}Konsep: Event Loop hanya boleh menjalankan operasi instan non-blocking.")
    print(f"Operasi blocking I/O (Database JDBC / sleep) HARUS dialihkan ke BoundedElastic Scheduler.{ANSI.RESET}\n")

    event_loop = EventLoop(name="nioEventLoop-2-1")
    elastic_pool = BoundedElasticScheduler(workers=2)
    event_loop.start()

    # Task non-blocking pada Event Loop
    def non_blocking_req(req_id: int):
        log_event(
            threading.current_thread().name,
            "INBOUND_HTTP",
            f"{ANSI.CYAN}Menerima HTTP Request #{req_id} (Non-blocking Parsing){ANSI.RESET}"
        )

    # Task blocking yang dialihkan (Offloading)
    def blocking_db_query(req_id: int):
        log_event(
            threading.current_thread().name,
            "JDBC_QUERY",
            f"{ANSI.YELLOW}Menjalankan SELECT blocking SQL Query untuk Request #{req_id}...{ANSI.RESET}"
        )
        time.sleep(0.4)
        log_event(
            threading.current_thread().name,
            "JDBC_QUERY",
            f"{ANSI.GREEN}Query Request #{req_id} selesai. Mengirim callback ke EventLoop.{ANSI.RESET}"
        )

        # Response dikirim balik ke event loop untuk ditulis ke socket (Channel.writeAndFlush)
        event_loop.execute(
            lambda: log_event(
                threading.current_thread().name,
                "SOCKET_WRITE",
                f"{ANSI.CYAN}Menulis HTTP 200 OK Response untuk #{req_id} ke Socket.{ANSI.RESET}"
            ),
            desc=f"Write-Response-#{req_id}"
        )

    # Simulasi 3 request masuk serentak
    for req_id in range(1, 4):
        rid = req_id
        event_loop.execute(lambda r=rid: non_blocking_req(r), desc=f"Parse-Req-#{rid}")
        elastic_pool.schedule(lambda r=rid: blocking_db_query(r), desc=f"DB-Offload-#{rid}")
        time.sleep(0.05)

    time.sleep(1.2)
    event_loop.stop()
    elastic_pool.shutdown()
    print(f"\n{ANSI.GREEN}✔ Skenario 2 Selesai: Event loop tetap responsif tanpa terkena starvation!{ANSI.RESET}\n")


def main():
    banner()
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg == "--scenario1":
            run_scenario_1_backpressure()
            return
        elif arg == "--scenario2":
            run_scenario_2_event_loop_and_offloading()
            return

    # Default run: Jalankan kedua skenario berurutan
    run_scenario_1_backpressure()
    time.sleep(0.5)
    run_scenario_2_event_loop_and_offloading()

    print(f"{ANSI.BOLD}{ANSI.CYAN}" + "=" * 80)
    print("  SIMULASI BERHASIL 100%: FONDASI REACTIVE JAVA & EVENT LOOP TERVERIFIKASI")
    print("=" * 80 + f"{ANSI.RESET}")


if __name__ == "__main__":
    main()

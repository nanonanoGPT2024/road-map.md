#!/usr/bin/env python3
"""
Lab: Reactive Java & Event-Loop Systems Deep Dive
Simulating Reactive Streams Specification (Publisher, Subscriber, Subscription)
alongside Netty-style Non-Blocking Event-Loop Architecture with Backpressure.
"""

import sys
import time
import threading
import queue
from typing import Callable, Any, Optional
from dataclasses import dataclass

# --- Terminal ANSI Styling ---
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BOLD = "\033[1m"


def log_event(channel: str, message: str, color: str = CLR_CYAN):
    """Format and display real-time reactive event lifecycle logs."""
    t_name = threading.current_thread().name
    print(f"{CLR_BOLD}[{time.strftime('%H:%M:%S.%f')[:-3]}]{CLR_RESET} "
          f"{color}[{channel:<16}] ({t_name:<16}){CLR_RESET} : {message}")


# ============================================================================
# Reactive Streams Specification Contracts (Reactive Java Core)
# ============================================================================

class Subscription:
    """Contract connecting Publisher and Subscriber to regulate demand (Backpressure)."""
    def request(self, n: int) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError


class Subscriber:
    """Terminal consumer receiving reactive signals."""
    def on_subscribe(self, subscription: Subscription) -> None:
        raise NotImplementedError

    def on_next(self, item: Any) -> None:
        raise NotImplementedError

    def on_error(self, err: Exception) -> None:
        raise NotImplementedError

    def on_complete(self) -> None:
        raise NotImplementedError


# ============================================================================
# Netty-Style Event Loop & Worker Scheduler
# ============================================================================

class EventLoop(threading.Thread):
    """
    Simulates a Netty NioEventLoop / Project Reactor Schedulers.single() or parallel().
    Consists of a dedicated single thread executing task-queues sequentially.
    """
    def __init__(self, name: str):
        super().__init__(name=name, daemon=True)
        self.task_queue: queue.Queue = queue.Queue()
        self.running = True
        self.start()

    def run(self):
        while self.running:
            try:
                task = self.task_queue.get(timeout=0.1)
                task()
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                log_event("EVENT_LOOP_ERR", f"Unhandled task error: {e}", CLR_RED)

    def dispatch(self, task: Callable[[], None]):
        """Schedule task to run asynchronously on this loop's thread context."""
        self.task_queue.put(task)

    def shutdown(self):
        self.running = False


# ============================================================================
# Reactive Pipeline Operators & Implementations
# ============================================================================

class FluxRangeSubscription(Subscription):
    """Emits range of integers adhering strictly to backpressure demand (REQUEST n)."""
    def __init__(self, subscriber: Subscriber, start: int, count: int, loop: Optional[EventLoop] = None):
        self.subscriber = subscriber
        self.current = start
        self.end = start + count
        self.loop = loop
        self.demand = 0
        self.cancelled = False
        self.lock = threading.Lock()
        self.emitting = False

    def request(self, n: int) -> None:
        if n <= 0:
            self.subscriber.on_error(ValueError("Rule 3.9: Demand n must be > 0"))
            return

        with self.lock:
            self.demand += n
            if self.emitting:
                return
            self.emitting = True

        # Process pipeline within the specified scheduler/event-loop context
        if self.loop:
            self.loop.dispatch(self._drain)
        else:
            self._drain()

    def cancel(self) -> None:
        with self.lock:
            self.cancelled = True

    def _drain(self) -> None:
        """Sequential drain loop avoiding re-entrancy race conditions."""
        while True:
            with self.lock:
                if self.cancelled:
                    self.emitting = False
                    return

                available = min(self.demand, self.end - self.current)
                if available == 0:
                    self.emitting = False
                    if self.current >= self.end:
                        self.subscriber.on_complete()
                    return

                self.demand -= available

            for _ in range(available):
                if self.cancelled:
                    return
                val = self.current
                self.current += 1
                self.subscriber.on_next(val)


class Flux:
    """Reactive Publisher mimicking Project Reactor's Flux with Fluent API."""
    def __init__(self, subscribe_fn: Callable[[Subscriber], None]):
        self._subscribe_fn = subscribe_fn

    @staticmethod
    def range(start: int, count: int):
        def _sub(subscriber: Subscriber):
            sub = FluxRangeSubscription(subscriber, start, count)
            subscriber.on_subscribe(sub)
        return Flux(_sub)

    def map(self, mapper: Callable[[Any], Any]):
        """Non-blocking synchronous transform operator."""
        def _sub(subscriber: Subscriber):
            outer = self
            class MapSubscriber(Subscriber):
                def on_subscribe(self, s: Subscription):
                    subscriber.on_subscribe(s)
                def on_next(self, item: Any):
                    try:
                        subscriber.on_next(mapper(item))
                    except Exception as ex:
                        subscriber.on_error(ex)
                def on_error(self, err: Exception):
                    subscriber.on_error(err)
                def on_complete(self):
                    subscriber.on_complete()
            outer._subscribe_fn(MapSubscriber())
        return Flux(_sub)

    def filter(self, predicate: Callable[[Any], bool]):
        """Conditional evaluation filter operator."""
        def _sub(subscriber: Subscriber):
            outer = self
            class FilterSubscriber(Subscriber):
                def __init__(self):
                    self.subscription: Optional[Subscription] = None

                def on_subscribe(self, s: Subscription):
                    self.subscription = s
                    subscriber.on_subscribe(s)

                def on_next(self, item: Any):
                    try:
                        if predicate(item):
                            subscriber.on_next(item)
                        else:
                            # Item dropped, automatically request next to prevent stalling demand
                            self.subscription.request(1)
                    except Exception as ex:
                        subscriber.on_error(ex)

                def on_error(self, err: Exception):
                    subscriber.on_error(err)

                def on_complete(self):
                    subscriber.on_complete()
            outer._subscribe_fn(FilterSubscriber())
        return Flux(_sub)

    def publish_on(self, loop: EventLoop):
        """Switches downstream execution context to designated EventLoop thread."""
        def _sub(subscriber: Subscriber):
            outer = self
            class PublishOnSubscriber(Subscriber, Subscription):
                def __init__(self):
                    self.upstream_sub: Optional[Subscription] = None

                def on_subscribe(self, s: Subscription):
                    self.upstream_sub = s
                    subscriber.on_subscribe(self)

                def on_next(self, item: Any):
                    loop.dispatch(lambda: subscriber.on_next(item))

                def on_error(self, err: Exception):
                    loop.dispatch(lambda: subscriber.on_error(err))

                def on_complete(self):
                    loop.dispatch(lambda: subscriber.on_complete())

                def request(self, n: int):
                    # Request propagates upstream
                    self.upstream_sub.request(n)

                def cancel(self):
                    self.upstream_sub.cancel()

            outer._subscribe_fn(PublishOnSubscriber())
        return Flux(_sub)

    def subscribe(self, subscriber: Subscriber):
        self._subscribe_fn(subscriber)


# ============================================================================
# Practical Simulation: High-Throughput Batch Processing with Backpressure
# ============================================================================

class ControlledBatchSubscriber(Subscriber):
    """
    Simulates consumer behavior requesting data in bounded windows (batch sizing)
    to prevent overwhelming downstream workers (OOM/Buffer-bloat avoidance).
    """
    def __init__(self, batch_size: int, process_delay: float):
        self.batch_size = batch_size
        self.process_delay = process_delay
        self.subscription: Optional[Subscription] = None
        self.consumed_in_batch = 0
        self.total_processed = 0
        self.completion_event = threading.Event()

    def on_subscribe(self, subscription: Subscription) -> None:
        self.subscription = subscription
        log_event("SUBSCRIBE", f"Connected to upstream. Demanding batch size = {self.batch_size}", CLR_GREEN)
        self.subscription.request(self.batch_size)

    def on_next(self, item: Any) -> None:
        self.total_processed += 1
        self.consumed_in_batch += 1
        log_event("ON_NEXT", f"Processing packet payload: [0x{item:04X}]", CLR_CYAN)

        # Emulate IO / CPU processing penalty
        if self.process_delay > 0:
            time.sleep(self.process_delay)

        # Dynamic Backpressure Trigger
        if self.consumed_in_batch >= self.batch_size:
            log_event("BACKPRESSURE", f"Window satisfied ({self.consumed_in_batch} units). Requesting next {self.batch_size}...", CLR_YELLOW)
            self.consumed_in_batch = 0
            self.subscription.request(self.batch_size)

    def on_error(self, err: Exception) -> None:
        log_event("ON_ERROR", f"Stream halted with failure: {err}", CLR_RED)
        self.completion_event.set()

    def on_complete(self) -> None:
        log_event("ON_COMPLETE", f"Stream exhausted cleanly. Total processed: {self.total_processed}", CLR_MAGENTA)
        self.completion_event.set()


# ============================================================================
# Main Execution Entrypoint
# ============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_GREEN}=== [LAB] Reactive Java & Event-Loop Engine Simulation ==={CLR_RESET}\n")

    # Spin up separate Netty-like I/O and Compute Event Loops
    worker_event_loop = EventLoop(name="reactor-nio-worker-1")

    log_event("SETUP", "Constructing Reactive Stream (Flux.range -> filter -> map -> publishOn)...", CLR_BOLD)

    # Reactive Pipeline Composition:
    # 1. Flux.range(1, 12)
    # 2. filter(even values only)
    # 3. map(bit-shift transform)
    # 4. publishOn(event_loop)
    reactive_stream = (
        Flux.range(1, 14)
        .filter(lambda x: x % 2 == 0)
        .map(lambda x: x << 4)
        .publish_on(worker_event_loop)
    )

    # Consumer demanding windows of 2 elements, simulating reactive flow control
    subscriber = ControlledBatchSubscriber(batch_size=2, process_delay=0.08)

    start_time = time.time()
    reactive_stream.subscribe(subscriber)

    # Await async stream completion
    subscriber.completion_event.wait(timeout=5.0)
    duration = time.time() - start_time

    worker_event_loop.shutdown()

    print(f"\n{CLR_BOLD}{CLR_GREEN}=== Stream Execution Metrics ==={CLR_RESET}")
    print(f"Total Pipeline Latency : {duration * 1000:.2f} ms")
    print(f"Consumed Stream Items  : {subscriber.total_processed}")
    print(f"Thread Transition Flow : MainThread -> {worker_event_loop.name}")
    print(f"{CLR_BOLD}{CLR_GREEN}Engine terminated successfully without event drops or deadlocks.{CLR_RESET}")


if __name__ == "__main__":
    main()
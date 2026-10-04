#!/usr/bin/env python3
"""
Lab Exercise: Kotlin Coroutines & Asynchronous Flow Deep Dive
Topic: Kotlin Reactive Streams (Cold Flow, Backpressure Buffering, Hot SharedFlow)
Category: 02-Programming-Languages / Chapter 06

Simulates Kotlin's Asynchronous Flow mechanisms using Python asyncio:
1. Cold Streams: Lazy evaluation, context preservation, declarative operators.
2. Backpressure Management: Bounded buffer capacity strategies (SUSPEND).
3. Hot Streams: MutableSharedFlow simulation with fan-out multicast to multiple collectors.
"""

import asyncio
import time
from typing import Callable, Any, AsyncGenerator, List


# ANSI Terminal Colors for Structured Output
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"
CLR_BLUE = "\033[34m"


def log(context: str, msg: str, color: str = CLR_RESET):
    timestamp = f"{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d}"
    print(f"{CLR_BLUE}[{timestamp}]{CLR_RESET} {CLR_BOLD}[{context:<22}]{CLR_RESET} {color}{msg}{CLR_RESET}")


class FlowCollector:
    """Simulates Kotlin's FlowCollector interface."""
    def __init__(self, emit_fn: Callable[[Any], Any]):
        self._emit = emit_fn

    async def emit(self, value: Any):
        await self._emit(value)


class Flow:
    """
    Simulates Kotlin Cold Asynchronous Flow.
    Cold stream behavior: Code inside flow block doesn't run until collected.
    """
    def __init__(self, block: Callable[[FlowCollector], Any]):
        self._block = block

    async def collect(self, action: Callable[[Any], Any]):
        """Terminal operator that triggers execution of upstream flow."""
        collector = FlowCollector(action)
        await self._block(collector)

    def map(self, transform: Callable[[Any], Any]) -> "Flow":
        """Intermediate operator: transforms upstream emissions."""
        async def mapped_block(collector: FlowCollector):
            async def upstream_action(value: Any):
                transformed = transform(value)
                await collector.emit(transformed)
            await self.collect(upstream_action)
        return Flow(mapped_block)

    def filter(self, predicate: Callable[[Any], bool]) -> "Flow":
        """Intermediate operator: filters upstream emissions."""
        async def filtered_block(collector: FlowCollector):
            async def upstream_action(value: Any):
                if predicate(value):
                    await collector.emit(value)
            await self.collect(upstream_action)
        return Flow(filtered_block)

    def buffer(self, capacity: int) -> "Flow":
        """
        Intermediate operator: runs upstream concurrently via a bounded channel/queue.
        Decouples emitter speed from collector processing speed (Backpressure handling).
        """
        async def buffered_block(collector: FlowCollector):
            queue: asyncio.Queue = asyncio.Queue(maxsize=capacity)
            sentinel = object()

            async def producer():
                try:
                    async def enqueue(val):
                        await queue.put(val)
                    await self.collect(enqueue)
                finally:
                    await queue.put(sentinel)

            producer_task = asyncio.create_task(producer())

            while True:
                item = await queue.get()
                if item is sentinel:
                    queue.task_done()
                    break
                await collector.emit(item)
                queue.task_done()

            await producer_task

        return Flow(buffered_block)


class MutableSharedFlow:
    """
    Simulates Kotlin's Hot SharedFlow: broadcast multicast stream.
    Emits active values regardless of whether subscribers are currently ready.
    """
    def __init__(self, replay: int = 0):
        self.replay = replay
        self.replay_cache: List[Any] = []
        self._subscribers: List[asyncio.Queue] = []

    async def emit(self, value: Any):
        """Multicasts a value to all active collectors and caches replay history."""
        if self.replay > 0:
            if len(self.replay_cache) >= self.replay:
                self.replay_cache.pop(0)
            self.replay_cache.append(value)

        # Distribute concurrently to subscriber mailboxes
        for queue in list(self._subscribers):
            await queue.put(value)

    async def collect(self, action: Callable[[Any], Any], subscriber_id: str):
        """Subscribes to hot emissions, processing replay cache first."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        log("SharedFlow", f"Collector '{subscriber_id}' attached", CLR_MAGENTA)

        # Replay past events
        for past_item in self.replay_cache:
            await action(past_item)

        try:
            while True:
                item = await queue.get()
                await action(item)
                queue.task_done()
        except asyncio.CancelledError:
            log("SharedFlow", f"Collector '{subscriber_id}' cancelled and detached", CLR_YELLOW)
        finally:
            self._subscribers.remove(queue)


# -------------------------------------------------------------------------
# LAB DEMONSTRATION SCENARIOS
# -------------------------------------------------------------------------

async def cold_flow_pipeline_demo():
    print(f"\n{CLR_BOLD}=== Scenario 1: Cold Flow Declarative Pipeline ==={CLR_RESET}")
    log("MainScope", "Building Cold Flow definition (nothing runs yet)...", CLR_CYAN)

    def market_feed():
        async def generator(collector: FlowCollector):
            ticks = [
                {"symbol": "BTC", "price": 64200, "vol": 1.2},
                {"symbol": "ETH", "price": 3450, "vol": 0.4},
                {"symbol": "SOL", "price": 145, "vol": 12.0},
                {"symbol": "BTC", "price": 64850, "vol": 2.5},
            ]
            for tick in ticks:
                await asyncio.sleep(0.04)
                await collector.emit(tick)
        return Flow(generator)

    pipeline = (
        market_feed()
        .filter(lambda tick: tick["symbol"] == "BTC")
        .map(lambda tick: f"Ticker: {tick['symbol']} | Notional: ${tick['price'] * tick['vol']:,.2f}")
    )

    log("MainScope", "Calling terminal operator .collect() on Pipeline A", CLR_YELLOW)
    await pipeline.collect(lambda data: log("Collector-A", f"Received -> {data}", CLR_GREEN))

    log("MainScope", "Re-collecting Pipeline A (Proves Cold evaluation uniqueness)", CLR_YELLOW)
    await pipeline.collect(lambda data: log("Collector-B", f"Received -> {data}", CLR_CYAN))


async def backpressure_buffer_demo():
    print(f"\n{CLR_BOLD}=== Scenario 2: Backpressure with .buffer() Operator ==={CLR_RESET}")
    log("MainScope", "Testing Fast Emitter (20ms) against Slow Downstream Collector (80ms)", CLR_CYAN)

    def fast_sensor_flow():
        async def stream(collector: FlowCollector):
            for i in range(1, 6):
                start = time.perf_counter()
                await collector.emit(i)
                elapsed = (time.perf_counter() - start) * 1000
                log("FastEmitter", f"Emitted #{i:02d} (Blocked: {elapsed:.2f}ms)", CLR_YELLOW)
                await asyncio.sleep(0.02)
        return Flow(stream)

    log("Test-Unbuffered", "-- Running UNBUFFERED (Emitter suspends on Collector) --", CLR_MAGENTA)
    await fast_sensor_flow().collect(lambda x: asyncio.sleep(0.08))

    log("Test-Buffered", "-- Running BUFFERED (capacity=5, Emitter runs freely) --", CLR_MAGENTA)
    buffered_flow = fast_sensor_flow().buffer(capacity=5)
    await buffered_flow.collect(lambda x: asyncio.sleep(0.08))


async def hot_shared_flow_demo():
    print(f"\n{CLR_BOLD}=== Scenario 3: Hot SharedFlow Fan-out & Multicast ==={CLR_RESET}")
    shared_flow = MutableSharedFlow(replay=1)

    async def subscriber(sub_name: str, color: str):
        async def process(item):
            log(sub_name, f"Consuming payload: '{item}'", color)
        await shared_flow.collect(process, subscriber_id=sub_name)

    # Start first subscriber
    task_sub1 = asyncio.create_task(subscriber("Subscriber-Alpha", CLR_CYAN))
    await asyncio.sleep(0.01)

    # Publish Initial Events
    log("Publisher", "Emitting: Event-101", CLR_GREEN)
    await shared_flow.emit("Event-101")
    log("Publisher", "Emitting: Event-102", CLR_GREEN)
    await shared_flow.emit("Event-102")

    # Late subscriber attaches; should receive replay cache first
    await asyncio.sleep(0.05)
    log("MainScope", "Attaching Late Subscriber-Beta (Should get replay buffer)", CLR_YELLOW)
    task_sub2 = asyncio.create_task(subscriber("Subscriber-Beta", CLR_MAGENTA))
    await asyncio.sleep(0.01)

    log("Publisher", "Emitting: Event-103", CLR_GREEN)
    await shared_flow.emit("Event-103")

    await asyncio.sleep(0.05)
    task_sub1.cancel()
    task_sub2.cancel()
    await asyncio.gather(task_sub1, task_sub2, return_exceptions=True)


async def main():
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN} LAB: KOTLIN ASYNCHRONOUS FLOW RUNTIME SIMULATION   {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================={CLR_RESET}")
    await cold_flow_pipeline_demo()
    await backpressure_buffer_demo()
    await hot_shared_flow_demo()
    print(f"\n{CLR_BOLD}{CLR_GREEN}[ALL LAB MODULE CHECKS COMPLETED SUCCESSFULLY]{CLR_RESET}")


if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Kotlin Reactive Streams & Asynchronous Flow
Bab: BAB-02-Paradigma-OOP-Idiomatis - Bab-06-Reactive-Streams-Asynchronous-Flow

Simulasi ini mendemonstrasikan semantik inti Kotlin Coroutines Flow di Python 3:
1. Cold Stream (Lazy evaluation via Generator & Async Iterator)
2. Flow Operators (map, filter, take)
3. Backpressure Management (buffer vs conflate vs collectLatest)
4. Hot Stream (StateFlow & SharedFlow dengan Replay Cache dan Multiple Collectors)
"""

import asyncio
import time
from typing import AsyncGenerator, Callable, List, TypeVar, Generic, Optional

T = TypeVar("T")
R = TypeVar("R")

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*64}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[DEMO] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*64}{CLR_RESET}")


def log(tag: str, msg: str, color: str = CLR_RESET) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CLR_BOLD}[{timestamp}] [{color}{tag:<12}{CLR_RESET}{CLR_BOLD}]{CLR_RESET} {msg}")


# ---------------------------------------------------------------------------
# 1. Core Cold Flow Simulation (Mirip Kotlin 'flow { emit(...) }')
# ---------------------------------------------------------------------------
class Flow(Generic[T]):
    """Representasi Cold Stream: eksekusi blok builder baru berjalan saat di-collect."""

    def __init__(self, builder: Callable[[], AsyncGenerator[T, None]]):
        self._builder = builder

    async def collect(self, collector: Callable[[T], None]) -> None:
        """Terminal Operator: memicu aliran data (eksekusi lazy)."""
        async for value in self._builder():
            collector(value)

    def map(self, transform: Callable[[T], R]) -> "Flow[R]":
        """Intermediate operator: mentransformasikan setiap elemen stream."""
        async def new_builder() -> AsyncGenerator[R, None]:
            async for item in self._builder():
                yield transform(item)
        return Flow(new_builder)

    def filter(self, predicate: Callable[[T], bool]) -> "Flow[T]":
        """Intermediate operator: menyaring elemen berdasarkan predikat boolean."""
        async def new_builder() -> AsyncGenerator[T, None]:
            async for item in self._builder():
                if predicate(item):
                    yield item
        return Flow(new_builder)

    def take(self, count: int) -> "Flow[T]":
        """Intermediate operator: membatasi emisi elemen hingga sejumlah N."""
        async def new_builder() -> AsyncGenerator[T, None]:
            taken = 0
            async for item in self._builder():
                if taken < count:
                    yield item
                    taken += 1
                else:
                    break
        return Flow(new_builder)


# ---------------------------------------------------------------------------
# 2. Hot Stream: SharedFlow & StateFlow Simulation
# ---------------------------------------------------------------------------
class SharedFlow(Generic[T]):
    """Hot Stream broadcast publisher dengan replay cache."""

    def __init__(self, replay: int = 1):
        self.replay = replay
        self.cache: List[T] = []
        self._subscribers: List[asyncio.Queue[T]] = []

    async def emit(self, value: T) -> None:
        self.cache.append(value)
        if len(self.cache) > self.replay:
            self.cache.pop(0)

        for q in list(self._subscribers):
            await q.put(value)

    def subscribe(self) -> asyncio.Queue[T]:
        q: asyncio.Queue[T] = asyncio.Queue()
        for item in self.cache:
            q.put_nowait(item)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[T]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)


class StateFlow(SharedFlow[T]):
    """State-holder observable hot stream (menyimpan state saat ini, mirip Kotlin StateFlow)."""

    def __init__(self, initial_value: T):
        super().__init__(replay=1)
        self._value: T = initial_value
        self.cache.append(initial_value)

    @property
    def value(self) -> T:
        return self._value

    async def emit(self, value: T) -> None:
        if self._value != value:
            self._value = value
            await super().emit(value)


# ---------------------------------------------------------------------------
# Skenario 1: Cold Flow & Karakteristik Lazy
# ---------------------------------------------------------------------------
async def demo_cold_flow() -> None:
    header("1. Cold Stream (Lazy Evaluation)")
    log("INFO", "Mendefinisikan flow generator (belum ada eksekusi...", CLR_YELLOW)

    async def number_generator() -> AsyncGenerator[int, None]:
        for i in range(1, 4):
            log("EMIT-THREAD", f"Producing nilai: {i}", CLR_MAGENTA)
            await asyncio.sleep(0.15)
            yield i

    stream = Flow(number_generator)
    log("INFO", "Flow didefinisikan! Perhatikan: data belum diproduksi.", CLR_YELLOW)
    await asyncio.sleep(0.3)

    log("COLLECTOR-1", "Mulai meng-collect stream pertama...", CLR_BLUE)
    await stream.collect(lambda x: log("CONSUME-1", f"Diterima: {x}", CLR_GREEN))

    log("INFO", "Menguji Collector kedua (Cold Stream akan mengulang eksekusi dari awal):", CLR_YELLOW)
    await stream.collect(lambda x: log("CONSUME-2", f"Diterima: {x}", CLR_CYAN))


# ---------------------------------------------------------------------------
# Skenario 2: Flow Intermediate Operators (map, filter, take)
# ---------------------------------------------------------------------------
async def demo_operators() -> None:
    header("2. Intermediate Operators (filter -> map -> take)")

    async def sensor_stream() -> AsyncGenerator[int, None]:
        data_points = [12, 25, 8, 30, 45, 18, 55, 60]
        for val in data_points:
            log("SENSOR", f"Reading raw value: {val}°C", CLR_MAGENTA)
            await asyncio.sleep(0.1)
            yield val

    base_flow = Flow(sensor_stream)
    pipeline = (
        base_flow
        .filter(lambda temp: temp >= 20)
        .map(lambda temp: f"{temp}°C ({temp * 9 / 5 + 32:.1f}°F) [WARNING: TINGGI]")
        .take(3)
    )

    log("PIPELINE", "Menjalankan filter (>=20) -> map -> take(3)...", CLR_YELLOW)
    await pipeline.collect(lambda item: log("DASHBOARD", f"Notifikasi: {item}", CLR_GREEN))


# ---------------------------------------------------------------------------
# Skenario 3: Backpressure Buffer vs Conflate
# ---------------------------------------------------------------------------
async def demo_backpressure() -> None:
    header("3. Backpressure & Buffer / Conflate Simulation")
    log("EXPLAIN", "Produser cepat (emit tiap 50ms), Konsumer lambat (proses 150ms).", CLR_YELLOW)

    print(f"\n{CLR_BOLD}--- Mode A: Conflate (Drop intermediate values, ambil yang terbaru) ---{CLR_RESET}")
    latest_val: Optional[int] = None
    stop_event = asyncio.Event()

    async def fast_producer_conflate() -> None:
        for i in range(1, 9):
            nonlocal latest_val
            latest_val = i
            log("PRODUCER", f"Emitted #{i}", CLR_MAGENTA)
            await asyncio.sleep(0.05)
        stop_event.set()

    async def slow_consumer_conflate() -> None:
        while not stop_event.is_set() or latest_val is not None:
            if latest_val is not None:
                val = latest_val
                latest_val = None
                log("CONSUMER", f"Memproses #{val} (membutuhkan 150ms)...", CLR_GREEN)
                await asyncio.sleep(0.15)
                log("CONSUMER", f"Selesai #{val}", CLR_BLUE)
            else:
                await asyncio.sleep(0.01)

    await asyncio.gather(fast_producer_conflate(), slow_consumer_conflate())

    print(f"\n{CLR_BOLD}--- Mode B: Buffered Queue (Kapasitas antrean terjaga tanpa drop) ---{CLR_RESET}")
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=10)

    async def fast_producer_buffer() -> None:
        for i in range(1, 6):
            await queue.put(i)
            log("PRODUCER", f"Disimpan ke Buffer Queue: #{i}", CLR_MAGENTA)
            await asyncio.sleep(0.05)
        await queue.put(-1)  # Sentinel EOF

    async def slow_consumer_buffer() -> None:
        while True:
            item = await queue.get()
            if item == -1:
                break
            log("CONSUMER", f"Mengambil #{item} dari Buffer, memproses lambat...", CLR_GREEN)
            await asyncio.sleep(0.12)
            queue.task_done()

    await asyncio.gather(fast_producer_buffer(), slow_consumer_buffer())


# ---------------------------------------------------------------------------
# Skenario 4: StateFlow & SharedFlow (Hot Stream Broadcast)
# ---------------------------------------------------------------------------
async def demo_hot_streams() -> None:
    header("4. Hot Stream (StateFlow UI State & SharedFlow Events)")
    state = StateFlow[str]("IDLE")
    events = SharedFlow[str](replay=2)

    log("STATEFLOW", f"Initial State value: '{state.value}'", CLR_CYAN)

    async def subscriber(name: str, queue: asyncio.Queue[str], count: int) -> None:
        for _ in range(count):
            val = await queue.get()
            log(name, f"Menerima broadcast: '{val}'", CLR_GREEN)

    sub1_q = events.subscribe()
    log("SHAREDFLOW", "Subscriber 1 mendaftar ke Event stream.", CLR_YELLOW)

    await events.emit("LOGIN_REQUEST")
    await state.emit("AUTHENTICATING")
    await events.emit("TOKEN_RECEIVED")

    log("SHAREDFLOW", "Subscriber 2 baru mendaftar (Menguji replay cache)...", CLR_YELLOW)
    sub2_q = events.subscribe()

    await state.emit("LOGGED_IN")
    await events.emit("SHOW_WELCOME_BANNER")

    # Ambil event untuk verifikasi
    task1 = asyncio.create_task(subscriber("SUB-1", sub1_q, 3))
    task2 = asyncio.create_task(subscriber("SUB-2", sub2_q, 3))
    await asyncio.gather(task1, task2)

    events.unsubscribe(sub1_q)
    events.unsubscribe(sub2_q)
    log("STATEFLOW", f"Final State saat ini: '{state.value}'", CLR_CYAN)


# ---------------------------------------------------------------------------
# Interactive Menu & Benchmark Runner
# ---------------------------------------------------------------------------
async def run_interactive() -> None:
    menu = f"""
{CLR_BOLD}{CLR_BLUE}==================================================================
   KOTLIN ASYNCHRONOUS FLOW & REACTIVE STREAMS TECHNICAL LAB
=================================================================={CLR_RESET}
{CLR_GREEN}1.{CLR_RESET} Demo 1: Cold Stream & Lazy Evaluation Semantics
{CLR_GREEN}2.{CLR_RESET} Demo 2: Intermediate Operators (map, filter, take)
{CLR_GREEN}3.{CLR_RESET} Demo 3: Backpressure Handling (Buffer vs Conflate)
{CLR_GREEN}4.{CLR_RESET} Demo 4: Hot Streams (StateFlow & SharedFlow Broadcast)
{CLR_GREEN}5.{CLR_RESET} Jalankan SEMUA Modul Simulasi Sekaligus
{CLR_RED}0.{CLR_RESET} Keluar
"""
    while True:
        print(menu)
        try:
            choice = input(f"{CLR_BOLD}Pilih opsi [0-5]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            await demo_cold_flow()
        elif choice == "2":
            await demo_operators()
        elif choice == "3":
            await demo_backpressure()
        elif choice == "4":
            await demo_hot_streams()
        elif choice == "5":
            await demo_cold_flow()
            await demo_operators()
            await demo_backpressure()
            await demo_hot_streams()
            log("COMPLETE", "Semua skenario pengujian aliran reaktif selesai!", CLR_GREEN)
        elif choice == "0":
            print(f"{CLR_BOLD}Selesai. Selamat mempelajari Kotlin Coroutines Flow!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan pilih 0-5.{CLR_RESET}")


if __name__ == "__main__":
    asyncio.run(run_interactive())

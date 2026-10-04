#!/usr/bin/env python3
"""
Lab Exercise: Kotlin Coroutines Flow & Reactive Streams Simulation
BAB-06: Reactive Streams & Asynchronous Flow

Simulasi interaktif konsep Kotlin Coroutines Flow dalam Python 3:
1. Cold Flow vs Hot Stream (SharedFlow / StateFlow)
2. Flow Builders & Transformation Operators (map, filter, take)
3. Dispatcher Switching & Context Preservation (flowOn)
4. Backpressure Strategies (buffer, conflate, collectLatest)
5. Declarative Error Handling & Completion (catch, onCompletion)
"""

import sys
import time
import asyncio
from typing import AsyncGenerator, Callable, Any, List, Optional

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def print_log(source: str, msg: str, color: str = BLUE) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{DIM}[{timestamp}]{RESET} {color}[{source:18}]{RESET} {msg}")


# ---------------------------------------------------------------------------
# 1. Cold Flow Simulator
# ---------------------------------------------------------------------------
async def cold_flow_producer(total_items: int = 4) -> AsyncGenerator[int, None]:
    """Mengemulasikan flow { emit(...) } di Kotlin. Eksekusi lazy per collector."""
    print_log("ColdFlow", "Memulai emisi (Cold: Producer baru aktif saat collect)", MAGENTA)
    for i in range(1, total_items + 1):
        await asyncio.sleep(0.15)
        print_log("ColdFlow", f"Emit nilai: {i}", GREEN)
        yield i
    print_log("ColdFlow", "Selesai mengalirkan semua item", MAGENTA)


# ---------------------------------------------------------------------------
# 2. Hot Stream Simulator (StateFlow)
# ---------------------------------------------------------------------------
class StateFlowSimulator:
    """Mengemulasikan MutableStateFlow<T> di Kotlin Coroutines."""

    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._subscribers: List[asyncio.Queue] = []

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        self._value = new_val
        for q in self._subscribers:
            q.put_nowait(new_val)

    async def collect(self, consumer_name: str, duration: float = 0.8) -> None:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        print_log(consumer_name, f"Berlangganan StateFlow. Nilai saat ini: {self._value}", YELLOW)
        end_time = asyncio.get_event_loop().time() + duration
        try:
            while asyncio.get_event_loop().time() < end_time:
                try:
                    val = await asyncio.wait_for(q.get(), timeout=0.2)
                    print_log(consumer_name, f"Menerima state terkini: {val}", GREEN)
                except asyncio.TimeoutError:
                    continue
        finally:
            self._subscribers.remove(q)
            print_log(consumer_name, "Berhenti berlangganan", DIM)


# ---------------------------------------------------------------------------
# 3. Flow Operators (map, filter, take)
# ---------------------------------------------------------------------------
async def flow_map(stream: AsyncGenerator[Any, None], transform: Callable[[Any], Any]) -> AsyncGenerator[Any, None]:
    async for item in stream:
        yield transform(item)


async def flow_filter(stream: AsyncGenerator[Any, None], predicate: Callable[[Any], bool]) -> AsyncGenerator[Any, None]:
    async for item in stream:
        if predicate(item):
            yield item


async def flow_take(stream: AsyncGenerator[Any, None], count: int) -> AsyncGenerator[Any, None]:
    taken = 0
    async for item in stream:
        if taken < count:
            yield item
            taken += 1
        if taken >= count:
            break


# ---------------------------------------------------------------------------
# 4. Context Preservation & Dispatcher Switching (flowOn)
# ---------------------------------------------------------------------------
async def simulated_flow_on_io() -> AsyncGenerator[dict, None]:
    """Mensimulasikan flowOn(Dispatchers.IO) berpindah thread pool."""
    print_log("Dispatchers.IO", "Menjalankan kalkulasi berat pada worker thread", CYAN)
    for i in range(1, 4):
        await asyncio.sleep(0.1)
        res = {"id": i, "payload": f"Data-{i*100}", "thread": "Dispatchers.IO-worker-1"}
        yield res


# ---------------------------------------------------------------------------
# 5. Backpressure Strategies (buffer, conflate, collectLatest)
# ---------------------------------------------------------------------------
async def fast_emitter(count: int = 5) -> AsyncGenerator[int, None]:
    for i in range(1, count + 1):
        await asyncio.sleep(0.05)
        print_log("FastProducer", f">> Emit #{i}", MAGENTA)
        yield i


async def demo_backpressure(mode: str) -> None:
    print_log("Strategy", f"Menguji backpressure: {mode.upper()}", YELLOW)
    if mode == "buffer":
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)

        async def worker():
            async for val in fast_emitter():
                await queue.put(val)
            await queue.put(None)

        asyncio.create_task(worker())
        while True:
            item = await queue.get()
            if item is None:
                break
            print_log("SlowConsumer", f"Memproses buffer item: {item} (butuh 0.15s)", CYAN)
            await asyncio.sleep(0.15)

    elif mode == "conflate":
        latest_val = None
        done = False

        async def worker():
            nonlocal latest_val, done
            async for val in fast_emitter():
                latest_val = val
            done = True

        asyncio.create_task(worker())
        while not done or latest_val is not None:
            if latest_val is not None:
                val_to_process = latest_val
                latest_val = None
                print_log("ConflateConsumer", f"Mengkonsumsi snapshot nilai: {val_to_process} (skip nilai usang)", GREEN)
                await asyncio.sleep(0.12)
            else:
                await asyncio.sleep(0.02)

    elif mode == "collectLatest":
        current_task: Optional[asyncio.Task] = None

        async def process_task(num: int):
            try:
                print_log("collectLatest", f"Mulai proses item #{num}...", BLUE)
                await asyncio.sleep(0.12)
                print_log("collectLatest", f"SUKSES proses item #{num}!", GREEN)
            except asyncio.CancelledError:
                print_log("collectLatest", f"DIBATALKAN item #{num} karena ada item baru!", RED)

        async for val in fast_emitter():
            if current_task and not current_task.done():
                current_task.cancel()
            current_task = asyncio.create_task(process_task(val))
        if current_task:
            await current_task


# ---------------------------------------------------------------------------
# 6. Error Handling & Completion
# ---------------------------------------------------------------------------
async def faulty_flow() -> AsyncGenerator[int, None]:
    for i in range(1, 5):
        await asyncio.sleep(0.08)
        if i == 3:
            raise ValueError("Simulasi Network Timeout pada emisi ke-3!")
        yield i


async def run_error_handling_demo() -> None:
    print_log("FlowEngine", "Menjalankan flow dengan deklaratif catch & onCompletion", YELLOW)
    try:
        async for val in faulty_flow():
            print_log("Collector", f"Menerima: {val}", GREEN)
    except Exception as e:
        print_log(".catch()", f"Menangkap exception: {e} -> Melakukan fallback!", RED)
        print_log("Fallback", "Mengalirkan data default (0) dari cache lokal", CYAN)
    finally:
        print_log(".onCompletion()", "Stream ditutup secara aman (resource cleanup).", BLUE)


# ---------------------------------------------------------------------------
# Menu Handlers
# ---------------------------------------------------------------------------
async def run_cold_hot_demo() -> None:
    print_header("DEMO 1: Cold Flow vs Hot StateFlow")
    print(f"{YELLOW}A. Cold Flow (dievaluasi ulang setiap dipanggil collect):{RESET}")
    print_log("Consumer-1", "Mulai koleksi Cold Flow", BLUE)
    async for item in cold_flow_producer(3):
        print_log("Consumer-1", f"Hasil: {item}", GREEN)

    print_log("Consumer-2", "Koleksi kedua (mengulang proses dari awal):", BLUE)
    async for item in cold_flow_producer(2):
        print_log("Consumer-2", f"Hasil: {item}", GREEN)

    print(f"\n{YELLOW}B. Hot Stream (StateFlow memancarkan data tanpa menunggu consumer):{RESET}")
    state_flow = StateFlowSimulator(initial_value="INIT_STATE")

    async def updater():
        await asyncio.sleep(0.1)
        state_flow.value = "LOADING"
        await asyncio.sleep(0.15)
        state_flow.value = "SUCCESS_DATA"

    await asyncio.gather(
        state_flow.collect("Observer-Alpha", duration=0.4),
        updater()
    )


async def run_operators_demo() -> None:
    print_header("DEMO 2: Flow Intermediate Operators (map, filter, take)")
    print(f"{DIM}Pipeline: cold_flow -> filter(genap) -> map(x * 10) -> take(2){RESET}")

    base = cold_flow_producer(6)
    even_only = flow_filter(base, lambda x: x % 2 == 0)
    scaled = flow_map(even_only, lambda x: x * 10)
    limited = flow_take(scaled, 2)

    async for result in limited:
        print_log("ResultCollector", f"Data transformasi final: {result}", GREEN)


async def run_dispatcher_demo() -> None:
    print_header("DEMO 3: Context Preservation & flowOn(Dispatchers.IO)")
    print(f"{DIM}Emisi dilakukan di pool background, konsumsi di Main dispatcher{RESET}")
    async for packet in simulated_flow_on_io():
        print_log("Dispatchers.Main", f"Update UI dengan {packet['payload']} (dari {packet['thread']})", GREEN)


async def run_backpressure_menu() -> None:
    print_header("DEMO 4: Backpressure Mitigation Strategies")
    print("1. buffer() - Antrekan elemen jika consumer lambat")
    print("2. conflate() - Lewati data usang jika consumer sibuk")
    print("3. collectLatest() - Batalkan proses lama jika ada emisi baru")
    sub = input(f"{BOLD}Pilih strategi (1/2/3): {RESET}").strip()
    if sub == "1":
        await demo_backpressure("buffer")
    elif sub == "2":
        await demo_backpressure("conflate")
    elif sub == "3":
        await demo_backpressure("collectLatest")
    else:
        print(f"{RED}Pilihan tidak valid, menjalankan buffer() default.{RESET}")
        await demo_backpressure("buffer")


async def run_all_demos() -> None:
    await run_cold_hot_demo()
    await run_operators_demo()
    await run_dispatcher_demo()
    await run_backpressure_menu()
    print_header("DEMO 5: Error Handling & Stream Completion")
    await run_error_handling_demo()


def main_interactive() -> None:
    while True:
        print(f"\n{BOLD}{MAGENTA}==================================================================={RESET}")
        print(f"{BOLD}{MAGENTA}  KOTLIN FLOW & REACTIVE STREAMS - SIMULATOR INTERAKTIF CLI (BAB-06){RESET}")
        print(f"{BOLD}{MAGENTA}==================================================================={RESET}")
        print(f" {CYAN}1.{RESET} Cold Flow vs Hot Stream (Flow vs StateFlow)")
        print(f" {CYAN}2.{RESET} Flow Intermediate Operators (map, filter, take)")
        print(f" {CYAN}3.{RESET} Dispatcher Switching & flowOn Context Preservation")
        print(f" {CYAN}4.{RESET} Backpressure Strategies (buffer, conflate, collectLatest)")
        print(f" {CYAN}5.{RESET} Exception Handling (.catch) & Lifecycle (.onCompletion)")
        print(f" {CYAN}6.{RESET} Jalankan SEMUA Skenario Pembelajaran Berurutan")
        print(f" {CYAN}0.{RESET} Keluar")
        print(f"{BOLD}{MAGENTA}-------------------------------------------------------------------{RESET}")

        pilihan = input(f"{BOLD}Pilih menu [0-6]: {RESET}").strip()

        if pilihan == "1":
            asyncio.run(run_cold_hot_demo())
        elif pilihan == "2":
            asyncio.run(run_operators_demo())
        elif pilihan == "3":
            asyncio.run(run_dispatcher_demo())
        elif pilihan == "4":
            asyncio.run(run_backpressure_menu())
        elif pilihan == "5":
            print_header("DEMO 5: Error Handling & Stream Completion")
            asyncio.run(run_error_handling_demo())
        elif pilihan == "6":
            asyncio.run(run_all_demos())
        elif pilihan == "0":
            print(f"\n{GREEN}Terima kasih! Sesi simulasi Kotlin Flow selesai.{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan '{pilihan}' tidak valid. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    try:
        main_interactive()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Program dihentikan oleh user (SIGINT). Sampai jumpa!{RESET}\n")
        sys.exit(0)

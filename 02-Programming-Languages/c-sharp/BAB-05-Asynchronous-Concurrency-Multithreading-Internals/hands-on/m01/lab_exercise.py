#!/usr/bin/env python3
"""
Lab Exercise: C# Asynchronous & Concurrency Internals Simulator
BAB-05: Asynchronous, Concurrency, and Multithreading Internals

Simulasi teknis interaktif mengenai cara kerja internal runtime C# / .NET CLR:
1. Task vs ValueTask & IAsyncStateMachine (MoveNext loop & heap allocation)
2. SynchronizationContext & ConfigureAwait(continueOnCapturedContext: false)
3. ThreadPool Work-Stealing Algorithm (Global Queue vs Local Work-Stealing Deque)
4. Channel<T> & Backpressure vs BlockingCollection
5. Interlocked CAS (Compare-And-Swap) vs Heavy Kernel Lock (Monitor/Mutex)
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# ANSI Color Codes for Terminal Styling
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def print_header(title: str):
    print(f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} === [SIMULATION] {title} === {Colors.RESET}\n")

def print_step(step: str, detail: str = ""):
    print(f" {Colors.CYAN}➜{Colors.RESET} {Colors.BOLD}{step}{Colors.RESET} {Colors.GRAY}{detail}{Colors.RESET}")

def print_success(msg: str):
    print(f"   {Colors.GREEN}✔ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"   {Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def print_info(label: str, val: Any):
    print(f"   {Colors.MAGENTA}•{Colors.RESET} {Colors.WHITE}{label}:{Colors.RESET} {Colors.YELLOW}{val}{Colors.RESET}")

# ==============================================================================
# 1. SIMULASI: Task vs ValueTask & IAsyncStateMachine
# ==============================================================================
class AsyncStateMachineState:
    INIT = -1
    AWAITING_IO = 0
    COMPLETED = -2

class CSharpTaskSimulator:
    """
    Simulasi decompilation Roslyn compiler:
    C# 'async Task<T>' menghasilkan class/struct turunan IAsyncStateMachine.
    Jika async selesai secara sinkron (sync completion/cached result):
    - Task<T> tetap mengalokasikan objek Task di Managed Heap (kecuali Task.FromResult ter-cache).
    - ValueTask<T> berupa struct (di stack), 0 bytes heap allocation!
    """
    def __init__(self, mode: str = "ValueTask"):
        self.mode = mode
        self.heap_allocations_bytes = 0
        self.stack_allocations_bytes = 0

    def execute_async_method(self, has_cache: bool):
        print_step(f"Memanggil async method dengan return type: {self.mode}", f"(Cache Hit = {has_cache})")
        time.sleep(0.3)

        if has_cache:
            # Hot-path / Synchronous completion
            if self.mode == "Task":
                # Alokasi Task<T> object di Heap: Object Header (8B) + MethodTable (8B) + Result/Fields (24B) ~= 40 bytes
                self.heap_allocations_bytes += 40
                print_warning(f"[Task<T>] Meskipun sinkron, alokasi Task di Gen0 Heap = 40 bytes.")
            else:
                # ValueTask<T> adalah Value Type (struct). Masuk CPU Register / Call Stack!
                self.stack_allocations_bytes += 16
                print_success(f"[ValueTask<T>] Synchronous completion! Stack-only (0 bytes Heap Allocation).")
            return "CachedResult#42"

        # Cold-path / Asynchronous completion (I/O pendings)
        print_step("I/O Pending! State Machine transition: MoveNext() -> Awaiting")
        if self.mode == "ValueTask":
            # Jika ValueTask menunggu (async pause), CLR membungkus ke IValueTaskSource / heap promise
            self.heap_allocations_bytes += 72
            print_warning(f"[ValueTask<T>] Async suspend terjadi! Berubah menjadi heap backing object (72 bytes).")
        else:
            self.heap_allocations_bytes += 96
            print_warning(f"[Task<T>] Async suspend! Alokasi Task + TaskCompletionSource + StateMachine Box (~96 bytes).")

        time.sleep(0.4)
        print_success("I/O selesai, Continuation callback dipicu via ThreadPool.")
        return "AsyncResult#99"

def run_task_vs_valuetask_demo():
    print_header("1. C# Async State Machine: Task vs ValueTask Heap Allocations")
    print(f"{Colors.GRAY}Mengamati beban Garbage Collector (Gen 0) saat method menyelesaikan tugas secara sinkron vs asinkron.{Colors.RESET}\n")

    print(f"{Colors.BOLD}Kasus A: Hot-path (1,000 pemanggilan dengan Cache Hit){Colors.RESET}")
    task_sim = CSharpTaskSimulator("Task")
    vtask_sim = CSharpTaskSimulator("ValueTask")

    for _ in range(5):
        task_sim.execute_async_method(has_cache=True)
        vtask_sim.execute_async_method(has_cache=True)

    print("\n--- Ringkasan Alokasi Memori (5x Sync Calls) ---")
    print_info("Task<T> Total Heap Allocation", f"{task_sim.heap_allocations_bytes} bytes (Beban GC Gen0)")
    print_info("ValueTask<T> Total Heap Allocation", f"{vtask_sim.heap_allocations_bytes} bytes (Zero GC)")

    print(f"\n{Colors.BOLD}Kasus B: Asynchronous Pause (I/O Suspension){Colors.RESET}")
    task_sim.execute_async_method(has_cache=False)
    vtask_sim.execute_async_method(has_cache=False)

# ==============================================================================
# 2. SIMULASI: SynchronizationContext & ConfigureAwait(false)
# ==============================================================================
def run_sync_context_demo():
    print_header("2. SynchronizationContext & ConfigureAwait(continueOnCapturedContext: false)")
    print(f"{Colors.GRAY}Simulasi UI Thread (Single-Threaded SynchronizationContext) vs ThreadPool context restoration.{Colors.RESET}\n")

    ui_thread_id = 1
    thread_pool_id = 42

    print_step(f"UI Event Handler dimulai pada UI Thread (Thread ID: {ui_thread_id})")
    print_info("Active SynchronizationContext", "WinFormsSyncContext (Single-threaded Dispatcher)")

    # Skenario 1: ConfigureAwait(true) default
    print(f"\n{Colors.BOLD}[Skenario 1: await DoWorkAsync() / ConfigureAwait(true)]{Colors.RESET}")
    time.sleep(0.3)
    print_step("Memulai operasi asinkron di ThreadPool...", f"Worker Thread ID: {thread_pool_id}")
    time.sleep(0.4)
    print_step("Operasi selesai. Memeriksa captured SynchronizationContext...")
    print_warning(f"Context captured! Continuation dipaksa POST kembali ke UI Thread (Thread ID: {ui_thread_id})")
    print_success(f"Continuation tereksekusi pada UI Thread: {ui_thread_id} (Aman untuk UI DOM updates)")

    # Skenario 2: ConfigureAwait(false)
    print(f"\n{Colors.BOLD}[Skenario 2: await DoWorkAsync().ConfigureAwait(false)]{Colors.RESET}")
    time.sleep(0.3)
    print_step("Memulai operasi asinkron di ThreadPool...", f"Worker Thread ID: {thread_pool_id}")
    time.sleep(0.4)
    print_step("Operasi selesai. Mengabaikan SynchronizationContext (Captured Context = NULL)...")
    print_success(f"Continuation langsung berjalan di ThreadPool worker (Thread ID: {thread_pool_id})")
    print_success("Menghindari overhead context switch & mencegah potensi Deadlock (Result / Wait())!")

# ==============================================================================
# 3. SIMULASI: CLR ThreadPool Work-Stealing Internals
# ==============================================================================
@dataclass
class ClrWorkItem:
    id: int
    name: str

class ClrWorkerThread:
    def __init__(self, thread_id: int):
        self.thread_id = thread_id
        # Local Queue adalah Double-Ended Queue (Deque):
        # Pemilik thread PUSH dan POP dari Tail (LIFO - data locality di CPU Cache).
        # Thread lain STEAL dari Head (FIFO).
        self.local_deque: deque = deque()

    def push_work(self, item: ClrWorkItem):
        self.local_deque.append(item)

    def pop_local(self) -> Optional[ClrWorkItem]:
        if self.local_deque:
            return self.local_deque.pop() # LIFO
        return None

    def steal(self) -> Optional[ClrWorkItem]:
        if self.local_deque:
            return self.local_deque.popleft() # FIFO (Work Stealing)
        return None

def run_work_stealing_demo():
    print_header("3. .NET ThreadPool Work-Stealing Deque Architecture")
    print(f"{Colors.GRAY}Prinsip: Global Queue (FIFO) + Per-Thread Local Deques (LIFO for owner, FIFO for thiefs).{Colors.RESET}\n")

    global_queue = deque([ClrWorkItem(100 + i, f"GlobalTask_{i}") for i in range(2)])
    worker1 = ClrWorkerThread(1)
    worker2 = ClrWorkerThread(2)

    # Worker 1 menghasilkan beberapa sub-task secara rekursif
    for i in range(1, 5):
        worker1.push_work(ClrWorkItem(i, f"SubTask_W1_{i}"))

    print_step("Kondisi Awal ThreadPool State:")
    print_info("Global Queue Items (FIFO)", [w.name for w in global_queue])
    print_info("Worker #1 Local Deque (Owner LIFO)", [w.name for w in worker1.local_deque])
    print_info("Worker #2 Local Deque (Idle)", [w.name for w in worker2.local_deque])

    print(f"\n{Colors.BOLD}[Eksekusi Worker #1]{Colors.RESET}")
    item1 = worker1.pop_local()
    print_success(f"Worker #1 memproses tugas miliknya dari Tail (LIFO Cache Hot): {item1.name}")

    print(f"\n{Colors.BOLD}[Worker #2 Sedang Menganggur (Work-Stealing Phase)]{Colors.RESET}")
    print_step("Worker #2 mencari pekerjaan: Local Deque kosong -> Cek Global Queue...")
    g_item = global_queue.popleft()
    print_success(f"Worker #2 mengambil dari Global Queue (FIFO): {g_item.name}")

    print_step("Worker #2 kehabisan pekerjaan lagi -> Masuk ke algoritma Work Stealing...")
    stolen_item = worker1.steal()
    if stolen_item:
        print_success(f"Worker #2 BERHASIL MENCURI dari Worker #1 Head (FIFO Steal): {stolen_item.name}")
    
    print("\n--- Sisa Pekerjaan di Antrean ---")
    print_info("Worker #1 Remaining Deque", [w.name for w in worker1.local_deque])
    print_info("Worker #2 Remaining Deque", [w.name for w in worker2.local_deque])

# ==============================================================================
# 4. SIMULASI: Interlocked CAS vs Monitor Lock (Benchmark Ringan)
# ==============================================================================
def run_interlocked_vs_monitor_demo():
    print_header("4. Synchronization Primitives: Interlocked.Increment vs Monitor (lock)")
    print(f"{Colors.GRAY}Membandingkan CPU-level Atomic CAS (CMPXCHG) vs User/Kernel Transition Mutex.{Colors.RESET}\n")

    iterations = 100_000

    # 1. Benchmark Standard Lock (Monitor Simulator)
    lock_obj = threading.Lock()
    counter_lock = 0
    t0 = time.perf_counter()
    for _ in range(iterations):
        with lock_obj:
            counter_lock += 1
    t_lock = (time.perf_counter() - t0) * 1000

    # 2. Benchmark Atomic Emulation (Interlocked)
    # Di Python, GIL/fast primitive memodelkan overhead tanpa context switch
    counter_atomic = 0
    t0 = time.perf_counter()
    for _ in range(iterations):
        # Simulasi interlocked atomic hardware instruction
        counter_atomic += 1
    t_atomic = (time.perf_counter() - t0) * 1000

    print_info("Iterasi", f"{iterations:,} ops")
    print_info("Monitor (lock) Time", f"{t_lock:.2f} ms (Ada enter/exit lock contention)")
    print_info("Interlocked (Atomic) Time", f"{t_atomic:.2f} ms (Single CPU opcode)")
    print_success(f"Interlocked ~{t_lock / max(t_atomic, 0.0001):.1f}x lebih efisien tanpa kernel synchronization barrier!")

# ==============================================================================
# MENU UTAMA INTERAKTIF
# ==============================================================================
def display_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}╔═══════════════════════════════════════════════════════════════════════╗
║         .NET CLR CONCURRENCY & ASYNC INTERNALS SIMULATOR              ║
║         BAB-05: Asynchronous, Concurrency & Multithreading            ║
╚═══════════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)

def main_menu():
    display_banner()
    while True:
        print(f"\n{Colors.BOLD}PILIH MODUL SIMULASI:{Colors.RESET}")
        print(f" {Colors.GREEN}1.{Colors.RESET} Task vs ValueTask & IAsyncStateMachine (GC Allocation)")
        print(f" {Colors.GREEN}2.{Colors.RESET} SynchronizationContext & ConfigureAwait(false)")
        print(f" {Colors.GREEN}3.{Colors.RESET} CLR ThreadPool Work-Stealing Algorithm")
        print(f" {Colors.GREEN}4.{Colors.RESET} Interlocked vs Monitor Lock Primitives")
        print(f" {Colors.GREEN}5.{Colors.RESET} Jalankan SEMUA Modul Sekaligus")
        print(f" {Colors.RED}0.{Colors.RESET} Keluar")

        try:
            choice = input(f"\n{Colors.YELLOW}Masukkan pilihan [0-5]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            run_task_vs_valuetask_demo()
        elif choice == "2":
            run_sync_context_demo()
        elif choice == "3":
            run_work_stealing_demo()
        elif choice == "4":
            run_interlocked_vs_monitor_demo()
        elif choice == "5":
            run_task_vs_valuetask_demo()
            run_sync_context_demo()
            run_work_stealing_demo()
            run_interlocked_vs_monitor_demo()
        elif choice == "0":
            print(f"\n{Colors.CYAN}Simulasi selesai. Tetap eksplorasi low-level internals .NET!{Colors.RESET}\n")
            break
        else:
            print_warning("Pilihan tidak valid, silakan coba lagi.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Mode non-interaktif untuk automated CI/testing
        display_banner()
        run_task_vs_valuetask_demo()
        run_sync_context_demo()
        run_work_stealing_demo()
        run_interlocked_vs_monitor_demo()
    else:
        main_menu()

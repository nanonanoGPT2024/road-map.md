#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur Runtime & Execution Model Backend
Topik: BAB-02 - Bahasa Pemrograman dan Runtime Execution
"""

import sys
import time
import queue
import threading
from typing import List, Dict, Any

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{YELLOW} [SIMULASI] {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


# ---------------------------------------------------------------------------
# Modul 1: Simulasi Compilation & Execution Paradigm (Interpreted vs JIT vs AOT)
# ---------------------------------------------------------------------------
def simulate_execution_paradigms() -> None:
    print_header("1. Paradigma Eksekusi: Interpreted vs JIT vs AOT")
    print(f"{BLUE}Mengukur latensi eksekusi simulasi untuk 100.000 instruksi bytecode:{RESET}\n")

    iterations = 100_000

    # 1. Pure Interpreted
    print(f"[{YELLOW}RUNNING{RESET}] 1. Pure Interpreted (evaluasi opcode per baris)...")
    start = time.perf_counter()
    val = 0
    # Simulasi overhead dynamic dispatch
    for i in range(iterations):
        val = (val + i) % 1000
    interpreted_duration = (time.perf_counter() - start) * 1000
    print(f" -> Interpreted Time : {RED}{interpreted_duration:.2f} ms{RESET} (Warmup cepat, eksekusi lambat)\n")

    # 2. JIT (Just-In-Time Compilation)
    print(f"[{YELLOW}RUNNING{RESET}] 2. JIT Compiler (Hotspot detection + deopt/opt profiling)...")
    start = time.perf_counter()
    # Fase warmup/tracing
    val = 0
    warmup_threshold = 20_000
    for i in range(warmup_threshold):
        val = (val + i) % 1000
    # Fase native compiled loop execution (simulasi faktor akselerasi 4x)
    fast_accel = (iterations - warmup_threshold) // 4
    for i in range(fast_accel):
        val = (val + i) % 1000
    jit_duration = (time.perf_counter() - start) * 1000
    print(f" -> JIT Compiled Time: {YELLOW}{jit_duration:.2f} ms{RESET} (Overhead warmup, eksekusi native setelah hotspot)\n")

    # 3. AOT (Ahead-Of-Time Native Machine Code)
    print(f"[{YELLOW}RUNNING{RESET}] 3. AOT Native Binary (Direct assembly, zero runtime overhead)...")
    start = time.perf_counter()
    # Simulasi eksekusi native assembly langsung
    fast_aot = iterations // 8
    for i in range(fast_aot):
        val = (val + i) % 1000
    aot_duration = (time.perf_counter() - start) * 1000
    print(f" -> AOT Native Time  : {GREEN}{aot_duration:.2f} ms{RESET} (Cold-start instan, peak performance konstan)\n")


# ---------------------------------------------------------------------------
# Modul 2: Simulasi Memory Management & Tracing Garbage Collection
# ---------------------------------------------------------------------------
class MemoryBlock:
    def __init__(self, block_id: str, size_kb: int):
        self.block_id = block_id
        self.size_kb = size_kb
        self.ref_count = 0
        self.marked = False

    def add_reference(self) -> None:
        self.ref_count += 1

    def remove_reference(self) -> None:
        self.ref_count = max(0, self.ref_count - 1)


class SimulatedHeap:
    def __init__(self):
        self.heap: Dict[str, MemoryBlock] = {}
        self.root_set: List[str] = []

    def allocate(self, block_id: str, size_kb: int) -> None:
        block = MemoryBlock(block_id, size_kb)
        self.heap[block_id] = block
        print(f" {GREEN}[ALLOC]{RESET} Heap memuat '{block_id}' ({size_kb} KB)")

    def add_root_pointer(self, block_id: str) -> None:
        if block_id in self.heap:
            self.root_set.append(block_id)
            self.heap[block_id].add_reference()
            print(f" {BLUE}[POINTER]{RESET} Stack pointer menunjuk ke Root: '{block_id}'")

    def run_mark_and_sweep(self) -> None:
        print(f"\n{BOLD}{MAGENTA}[GC START]{RESET} Memulai Tracing Mark-and-Sweep...")
        # 1. Mark Phase
        for root in self.root_set:
            if root in self.heap:
                self.heap[root].marked = True
                print(f"   -> Mark phase: '{root}' is reachable (LIVE)")

        # 2. Sweep Phase
        reclaimed_size = 0
        dead_blocks = []
        for b_id, block in self.heap.items():
            if not block.marked:
                dead_blocks.append(b_id)
                reclaimed_size += block.size_kb
            else:
                block.marked = False  # Reset flag

        for dead in dead_blocks:
            del self.heap[dead]
            print(f"   -> Sweep phase: Reclaiming dead memory '{dead}'")

        print(f"{GREEN}[GC DONE]{RESET} Berhasil membebaskan {reclaimed_size} KB. Objek aktif di heap: {len(self.heap)}\n")


def simulate_memory_gc() -> None:
    print_header("2. Manajemen Memori: Reference Counting & Tracing GC")
    heap = SimulatedHeap()

    # Alokasi beberapa objek di heap
    heap.allocate("SessionToken_Auth", 64)
    heap.allocate("Cache_Response_Temp", 512)
    heap.allocate("ConnectionPool_DB", 256)
    heap.allocate("LeakedObject_Cycle", 128)

    # Tambahkan root reference hanya ke 2 objek
    heap.add_root_pointer("SessionToken_Auth")
    heap.add_root_pointer("ConnectionPool_DB")

    # Jalankan simulasi GC
    heap.run_mark_and_sweep()


# ---------------------------------------------------------------------------
# Modul 3: Simulasi Concurrency Execution Model (Thread Pool vs Event Loop)
# ---------------------------------------------------------------------------
def simulate_concurrency_models() -> None:
    print_header("3. Concurrency Runtime: Multi-Threaded vs Event-Driven Loop")
    print(f"{BLUE}Simulasi pemrosesan 5 request I/O bound berlatensi 50ms:{RESET}\n")

    requests = [f"Req-{i+1}" for i in range(5)]

    # 1. Multi-Threaded Model (Worker Thread per Connection)
    print(f"[{BOLD}MODEL A{RESET}] Worker Thread Pool (Pre-fork / OS Thread Concurrency)")
    start_threads = time.perf_counter()

    def worker_job(req_name: str) -> None:
        time.sleep(0.05)  # Simulasi I/O socket
        print(f"  {CYAN}* Thread [{threading.current_thread().name}]{RESET} selesai memproses {req_name}")

    threads = []
    for r in requests:
        t = threading.Thread(target=worker_job, args=(r,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    thread_duration = (time.perf_counter() - start_threads) * 1000
    print(f"  {GREEN}Total Thread Duration: {thread_duration:.2f} ms{RESET} (Tiap thread butuh alokasi stack 2MB-8MB)\n")

    # 2. Event-Driven Cooperative Event Loop Simulation
    print(f"[{BOLD}MODEL B{RESET}] Single-Threaded Event Loop (Non-blocking I/O demultiplexer)")
    start_loop = time.perf_counter()
    event_queue: queue.Queue = queue.Queue()

    for r in requests:
        event_queue.put((r, time.time() + 0.05))

    completed = 0
    while completed < len(requests):
        try:
            req_name, target_time = event_queue.get_nowait()
            if time.time() >= target_time:
                print(f"  {MAGENTA}* EventLoop [Poll Phase]{RESET} Callback I/O siap untuk {req_name}")
                completed += 1
            else:
                event_queue.put((req_name, target_time))
                time.sleep(0.005)
        except queue.Empty:
            time.sleep(0.005)

    loop_duration = (time.perf_counter() - start_loop) * 1000
    print(f"  {GREEN}Total Event Loop Duration: {loop_duration:.2f} ms{RESET} (Low memory footprint, Zero thread context switch)\n")


# ---------------------------------------------------------------------------
# Menu Interaktif CLI
# ---------------------------------------------------------------------------
def interactive_menu() -> None:
    while True:
        print(f"\n{BOLD}{GREEN}=== SIMULATOR RUNTIME EXECUTION BACKEND ==={RESET}")
        print("1. Simulasi Paradigma Kompilasi (Interpreted vs JIT vs AOT)")
        print("2. Simulasi Alokasi Memori & Tracing Garbage Collector")
        print("3. Simulasi Concurrency Runtime (Thread Pool vs Event Loop)")
        print("4. Jalankan Seluruh Simulasi (Benchmark Mode)")
        print("5. Keluar")
        choice = input(f"{BOLD}Pilih menu [1-5]: {RESET}").strip()

        if choice == "1":
            simulate_execution_paradigms()
        elif choice == "2":
            simulate_memory_gc()
        elif choice == "3":
            simulate_concurrency_models()
        elif choice == "4":
            simulate_execution_paradigms()
            simulate_memory_gc()
            simulate_concurrency_models()
            print(f"{BOLD}{GREEN}Semua modul simulasi sukses dijalankan!{RESET}\n")
        elif choice == "5":
            print(f"{YELLOW}Menutup simulator runtime. Sampai jumpa!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1 - 5.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan argumen '--batch' atau non-interaktif, jalankan mode batch
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        simulate_execution_paradigms()
        simulate_memory_gc()
        simulate_concurrency_models()
    else:
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan oleh user.{RESET}")
            sys.exit(0)

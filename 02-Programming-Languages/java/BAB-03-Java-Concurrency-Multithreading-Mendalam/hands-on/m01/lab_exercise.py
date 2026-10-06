#!/usr/bin/env python3
"""
Lab Exercise: Java Concurrency & Multithreading In-Depth Simulation
Simulasi Teknis Mandiri Konsep Fondasi Multithreading & Memory Model Java:
- Race Condition & Atomic vs Non-Atomic Updates
- Java Memory Model (JMM): Visibility & Volatile Barrier Simulation
- Monitor Lock Pattern (Intrinsic Locks: synchronized, wait, notifyAll)
- Java Thread Lifecycle State Machine Visualization
"""

import sys
import time
import threading
from typing import List

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================
   JAVA CONCURRENCY & MULTITHREADING LAB SIMULATOR (CLI)
   BAB-03: Deep-Dive Core Synchronization & Memory Model
========================================================================{RESET}
"""
    print(banner)


# --- Simulation 1: Race Condition vs Synchronized (Monitor) vs Atomic ---
class CounterBenchmark:
    def __init__(self, target_iterations: int = 100_000, num_threads: int = 4):
        self.iterations = target_iterations
        self.num_threads = num_threads
        self.unsafe_val = 0
        self.sync_val = 0
        self.lock = threading.Lock()

    def run_unsafe(self):
        self.unsafe_val = 0

        def worker():
            for _ in range(self.iterations):
                # Simulated non-atomic read-modify-write (Java: count++)
                current = self.unsafe_val
                time.sleep(0.000001)  # Force thread context switch
                self.unsafe_val = current + 1

        threads = [threading.Thread(target=worker) for _ in range(self.num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return self.unsafe_val

    def run_synchronized(self):
        self.sync_val = 0

        def worker():
            for _ in range(self.iterations):
                # Simulating Java synchronized(this) { count++; }
                with self.lock:
                    current = self.sync_val
                    time.sleep(0.000001)
                    self.sync_val = current + 1

        threads = [threading.Thread(target=worker) for _ in range(self.num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return self.sync_val


def demo_race_condition():
    print(f"\n{YELLOW}{BOLD}[SIMULATION 1] Race Condition vs Java Intrinsic Lock (Synchronized){RESET}")
    print(f"{WHITE}Mensimulasikan 4 thread yang serentak melakukan operasi increment non-atomic (count++).{RESET}")
    bench = CounterBenchmark(target_iterations=500, num_threads=4)
    expected = 500 * 4

    print(f"\n{BLUE}-> Menjalankan Unsynchronized Counter (Simulasi Java plain field)...{RESET}")
    start = time.perf_counter()
    res_unsafe = bench.run_unsafe()
    elapsed_unsafe = time.perf_counter() - start
    print(f"   Hasil Akhir: {RED}{res_unsafe}{RESET} / Expected: {GREEN}{expected}{RESET}")
    if res_unsafe < expected:
        diff = expected - res_unsafe
        print(f"   {RED}{BOLD}[DATA LOSS DETECTED]{RESET} Terjadi race condition! Kehilangan {diff} pembaruan.")
    print(f"   Waktu eksekusi: {elapsed_unsafe:.4f}s")

    print(f"\n{BLUE}-> Menjalankan Synchronized Counter (Simulasi Java synchronized block)...{RESET}")
    start = time.perf_counter()
    res_sync = bench.run_synchronized()
    elapsed_sync = time.perf_counter() - start
    print(f"   Hasil Akhir: {GREEN}{res_sync}{RESET} / Expected: {GREEN}{expected}{RESET}")
    print(f"   {GREEN}{BOLD}[THREAD-SAFE]{RESET} Mutual Exclusion terjaga tanpa data race.")
    print(f"   Waktu eksekusi: {elapsed_sync:.4f}s (overhead locking)")


# --- Simulation 2: Java Memory Model (JMM) Volatile Visibility ---
class JMMVisibilitySimulation:
    def __init__(self):
        self.flag_non_volatile = False
        self.flag_volatile = False
        self.counter = 0

    def run_volatile_simulation(self):
        print(f"\n{YELLOW}{BOLD}[SIMULATION 2] Java Memory Model: Volatile & Happens-Before Guarantee{RESET}")
        print(f"{WHITE}Simulasi visibility thread cache vs CPU memory barrier (volatile write/read).{RESET}")

        stop_requested = False

        def worker_thread():
            local_counter = 0
            # Simulating thread reading volatile flag
            while not stop_requested:
                local_counter += 1
                time.sleep(0.005)
            print(f"   {GREEN}[WorkerThread]{RESET} Menerima sinyal stop! Local loops: {local_counter}")

        worker = threading.Thread(target=worker_thread, name="Worker-1")
        print(f"   {CYAN}[MainThread]{RESET} Memulai worker thread (looping active)...")
        worker.start()

        time.sleep(0.05)
        print(f"   {CYAN}[MainThread]{RESET} Mengirim sinyal stop_requested = True (Memory Barrier Flush)")
        stop_requested = True
        worker.join(timeout=1.0)

        if not worker.is_alive():
            print(f"   {GREEN}{BOLD}[SUKSES]{RESET} Visibility terjadi: Worker mendeteksi perubahan flag secara realtime.")
        else:
            print(f"   {RED}{BOLD}[TIMEOUT]{RESET} Worker thread stuck karena visibility issue.")


# --- Simulation 3: Java Monitor Pattern (wait / notifyAll) ---
class JavaMonitorQueue:
    def __init__(self, capacity: int = 3):
        self.capacity = capacity
        self.queue: List[str] = []
        self.condition = threading.Condition()

    def put(self, item: str, producer_name: str):
        # Simulating Java: synchronized(this) { while(isFull()) wait(); ... notifyAll(); }
        with self.condition:
            while len(self.queue) >= self.capacity:
                print(f"   {YELLOW}[{producer_name}]{RESET} Buffer penuh ({len(self.queue)}/{self.capacity}). Memanggil {MAGENTA}wait(){RESET}...")
                self.condition.wait()
            self.queue.append(item)
            print(f"   {GREEN}[{producer_name}]{RESET} Memproduksi: {BOLD}{item}{RESET} | Buffer: {self.queue}")
            self.condition.notify_all()

    def take(self, consumer_name: str) -> str:
        # Simulating Java: synchronized(this) { while(isEmpty()) wait(); ... notifyAll(); }
        with self.condition:
            while len(self.queue) == 0:
                print(f"   {CYAN}[{consumer_name}]{RESET} Buffer kosong. Memanggil {MAGENTA}wait(){RESET}...")
                self.condition.wait()
            item = self.queue.pop(0)
            print(f"   {BLUE}[{consumer_name}]{RESET} Mengonsumsi: {BOLD}{item}{RESET} | Buffer: {self.queue}")
            self.condition.notify_all()
            return item


def demo_monitor_pattern():
    print(f"\n{YELLOW}{BOLD}[SIMULATION 3] Java Monitor Pattern (wait/notifyAll Producer-Consumer){RESET}")
    print(f"{WHITE}Simulasi BoundedBuffer menggunakan intrinsic condition queue.{RESET}\n")

    monitor = JavaMonitorQueue(capacity=2)
    items_to_produce = [f"Data-{i}" for i in range(1, 5)]

    def producer():
        for it in items_to_produce:
            monitor.put(it, "Producer-1")
            time.sleep(0.03)

    def consumer():
        for _ in range(len(items_to_produce)):
            time.sleep(0.06)
            monitor.take("Consumer-1")

    p = threading.Thread(target=producer)
    c = threading.Thread(target=consumer)
    p.start()
    c.start()
    p.join()
    c.join()
    print(f"\n{GREEN}{BOLD}[SELESAI]{RESET} Monitor pattern berhasil mengkoordinasikan producer-consumer tanpa deadlock.")


# --- Simulation 4: Java Thread Lifecycle State Machine ---
def demo_thread_lifecycle():
    print(f"\n{YELLOW}{BOLD}[SIMULATION 4] Java Thread State Machine (Thread.State){RESET}")
    print(f"{WHITE}Visualisasi transisi state Java: NEW -> RUNNABLE -> TIMED_WAITING -> TERMINATED{RESET}\n")

    def sample_task():
        print(f"   [Thread Target] Status: {GREEN}RUNNABLE{RESET} (Mengeksekusi bytecode)")
        print(f"   [Thread Target] Masuk ke {MAGENTA}TIMED_WAITING{RESET} (via Thread.sleep)")
        time.sleep(0.1)
        print(f"   [Thread Target] Selesai sleep, kembali ke {GREEN}RUNNABLE{RESET}")

    t = threading.Thread(target=sample_task)
    print(f"1. Thread diinstansiasi: State = {CYAN}NEW{RESET} (Belum start)")

    t.start()
    print(f"2. Thread.start() dipanggil: State = {GREEN}RUNNABLE{RESET}")

    time.sleep(0.03)
    if t.is_alive():
        print(f"3. Sedang sleep/eksekusi: State = {MAGENTA}TIMED_WAITING / RUNNABLE{RESET}")

    t.join()
    print(f"4. Thread selesai run(): State = {RED}TERMINATED{RESET}")


# --- Interactive Menu ---
def interactive_menu():
    while True:
        print_banner()
        print(f"{BOLD}Pilih Modul Simulasi Concurrency:{RESET}")
        print(f"  {CYAN}[1]{RESET} Race Condition vs Synchronized Lock (Critical Section)")
        print(f"  {CYAN}[2]{RESET} Java Memory Model (JMM): Visibility & Memory Barrier")
        print(f"  {CYAN}[3]{RESET} Java Intrinsic Monitor Pattern (wait / notifyAll)")
        print(f"  {CYAN}[4]{RESET} Thread State Lifecycle (NEW -> RUNNABLE -> TERMINATED)")
        print(f"  {CYAN}[5]{RESET} Jalankan SEMUA Simulasi Berurutan (Automated Suite)")
        print(f"  {RED}[0]{RESET} Keluar")

        try:
            choice = input(f"\n{BOLD}Pilihan Anda (0-5): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            demo_race_condition()
        elif choice == "2":
            JMMVisibilitySimulation().run_volatile_simulation()
        elif choice == "3":
            demo_monitor_pattern()
        elif choice == "4":
            demo_thread_lifecycle()
        elif choice == "5":
            demo_race_condition()
            time.sleep(0.5)
            JMMVisibilitySimulation().run_volatile_simulation()
            time.sleep(0.5)
            demo_monitor_pattern()
            time.sleep(0.5)
            demo_thread_lifecycle()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah menjalankan Java Concurrency Lab.{RESET}")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid, silakan ulangi.{RESET}")

        input(f"\n{WHITE}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    # If run in non-interactive mode (e.g. piped or automated test), run suite
    if not sys.stdin.isatty():
        print_banner()
        demo_race_condition()
        JMMVisibilitySimulation().run_volatile_simulation()
        demo_monitor_pattern()
        demo_thread_lifecycle()
    else:
        interactive_menu()

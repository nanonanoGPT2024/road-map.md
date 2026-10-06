#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Interaktif Konsep Konkurensi & Paralelisme C++
Topik: BAB-06 Concurrent & Parallel Systems (C++11 s.d. C++20/23)

Materi yang disimulasikan:
1. std::thread vs std::jthread (RAII auto-joining & std::stop_token cancellation)
2. std::mutex, std::lock_guard, and std::scoped_lock (Deadlock Avoidance)
3. std::atomic & Memory Ordering Semantics (Sequential Consistency vs Relaxed)
4. Thread-Safe Bounded Blocking Queue (std::condition_variable pattern)
5. Cache Line Contention & False Sharing (hardware_destructive_interference_size)
"""

import sys
import time
import threading
import queue
import random
from dataclasses import dataclass
from typing import List, Optional

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


def header(title: str):
    line = "=" * 68
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" [*] {title}")
    print(f"{line}{CLR_RESET}\n")


def log_step(thread_name: str, color: str, msg: str):
    timestamp = time.strftime("%H:%M:%S")
    print(f" {CLR_RESET}[{timestamp}] {color}[{thread_name:<14}]{CLR_RESET} {msg}")


# ==============================================================================
# 1. Simulasi C++20 std::jthread & std::stop_token
# ==============================================================================
class StopToken:
    """Simulasi std::stop_token di C++20."""
    def __init__(self):
        self._stop_requested = threading.Event()

    def stop_requested(self) -> bool:
        return self._stop_requested.is_set()

    def request_stop(self) -> bool:
        if not self._stop_requested.is_set():
            self._stop_requested.set()
            return True
        return False


class JThreadSim:
    """Simulasi std::jthread dengan RAII auto-request_stop dan auto-join."""
    def __init__(self, target, name: str):
        self.name = name
        self.stop_token = StopToken()
        self._thread = threading.Thread(
            target=target,
            args=(self.stop_token,),
            name=name
        )

    def start(self):
        self._thread.start()

    def join(self):
        if self._thread.is_alive():
            self._thread.join()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Destruktor RAII std::jthread: request_stop() lalu join()
        log_step("JThread-RAII", CLR_MAGENTA, f"Destruktor dipanggil: auto request_stop() -> join() untuk [{self.name}]")
        self.stop_token.request_stop()
        self.join()
        log_step("JThread-RAII", CLR_GREEN, f"Thread [{self.name}] berhasil di-join secara aman.")


def demo_jthread():
    header("Modul 1: Simulasi C++20 std::jthread & Cooperative Cancellation (stop_token)")
    print(f"{CLR_YELLOW}Penjelasan: std::jthread otomatis mengirim request_stop() dan join() saat keluar scope (RAII).{CLR_RESET}\n")

    def worker_loop(st: StopToken):
        iteration = 0
        while not st.stop_requested():
            iteration += 1
            log_step("Worker-JThread", CLR_BLUE, f"Memproses batch data ke-{iteration}...")
            time.sleep(0.15)
        log_step("Worker-JThread", CLR_YELLOW, "stop_token mendeteksi stop_requested! Membersihkan alokasi...")
        time.sleep(0.1)
        log_step("Worker-JThread", CLR_GREEN, "Worker keluar dengan graceful cleanup.")

    print(f"{CLR_BOLD}>> Memasuki scope lokal (menguji RAII destructor)...{CLR_RESET}")
    with JThreadSim(worker_loop, name="worker-01") as jt:
        time.sleep(0.5)
        print(f" {CLR_YELLOW}[Scope Main] Selesai melakukan operasi utama, keluar dari scope...{CLR_RESET}")
    print(f"{CLR_BOLD}>> Berhasil keluar scope tanpa std::terminate error!{CLR_RESET}\n")


# ==============================================================================
# 2. Simulasi Deadlock Avoidance: std::scoped_lock vs Unordered Locks
# ==============================================================================
def demo_deadlock_avoidance():
    header("Modul 2: Deadlock Prevention dengan std::scoped_lock (Deadlock-Free Algorithm)")
    print(f"{CLR_YELLOW}Penjelasan: Penguncian multi-mutex tanpa urutan konsisten dapat memicu circular wait deadlock.")
    print(f"std::scoped_lock (C++17) menggunakan algoritma variadic deadlock avoidance (mirip std::lock).{CLR_RESET}\n")

    res_a = threading.Lock()
    res_b = threading.Lock()

    def safe_scoped_lock_transfer(tx_id: int, lock1: threading.Lock, lock2: threading.Lock, reverse: bool):
        # Simulasi std::scoped_lock: urutan akuisisi berbasis id pointer/resource
        first, second = (lock1, lock2) if not reverse else (lock2, lock1)
        # Sesuai std::scoped_lock: locking strictly ordered atau try_lock deadlock-avoidance
        ordered_first, ordered_second = (lock1, lock2) if id(lock1) < id(lock2) else (lock2, lock1)

        tname = f"Tx-{tx_id}"
        log_step(tname, CLR_CYAN, f"Meminta std::scoped_lock(res_A, res_B)...")
        with ordered_first:
            log_step(tname, CLR_CYAN, f"Mengunci resource prioritas 1 (ID: {id(ordered_first) % 1000})")
            time.sleep(0.05)
            with ordered_second:
                log_step(tname, CLR_GREEN, f"Berhasil mengunci kedua mutex secara atomik & deadlock-free! Melakukan transfer dana...")
                time.sleep(0.1)
        log_step(tname, CLR_RESET, "Kedua mutex dirilis (RAII unlock).")

    t1 = threading.Thread(target=safe_scoped_lock_transfer, args=(1, res_a, res_b, False))
    t2 = threading.Thread(target=safe_scoped_lock_transfer, args=(2, res_a, res_b, True))

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print(f"\n{CLR_GREEN}{CLR_BOLD}[OK] Tidak ada circular wait deadlock yang terjadi!{CLR_RESET}")


# ==============================================================================
# 3. Simulasi std::atomic & Memory Ordering Semantics
# ==============================================================================
def demo_atomic_memory_order():
    header("Modul 3: std::atomic & Memory Ordering Semantics")
    print(f"{CLR_YELLOW}Penjelasan Memory Orders:")
    print(f" - memory_order_relaxed: Hanya menjamin atomicity operasi tanpa sinkronisasi visibilitas cache instruction.")
    print(f" - memory_order_release / acquire: Menjamin instruksi store/load tidak di-reorder melintasi barrier.")
    print(f" - memory_order_seq_cst: Sequential Consistency (default di C++ std::atomic).{CLR_RESET}\n")

    class AtomicSimulator:
        def __init__(self, initial_value: int = 0):
            self._val = initial_value
            self._lock = threading.Lock()
            self.read_count = 0
            self.write_count = 0

        def fetch_add(self, delta: int, order: str) -> int:
            with self._lock:
                old = self._val
                self._val += delta
                self.write_count += 1
                return old

        def load(self, order: str) -> int:
            with self._lock:
                self.read_count += 1
                return self._val

    shared_counter = AtomicSimulator(0)
    num_threads = 4
    increments_per_thread = 250

    def atomic_worker(worker_id: int):
        for _ in range(increments_per_thread):
            shared_counter.fetch_add(1, order="memory_order_relaxed")

    threads = [threading.Thread(target=atomic_worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = num_threads * increments_per_thread
    actual = shared_counter.load("memory_order_seq_cst")
    print(f" {CLR_BOLD}Atomic Result Analysis:{CLR_RESET}")
    print(f"  - Total Workers      : {CLR_CYAN}{num_threads}{CLR_RESET}")
    print(f"  - Increments/Worker  : {CLR_CYAN}{increments_per_thread}{CLR_RESET}")
    print(f"  - Expected Counter   : {CLR_GREEN}{expected}{CLR_RESET}")
    print(f"  - Actual Read Value  : {CLR_GREEN if actual == expected else CLR_RED}{actual}{CLR_RESET}")
    print(f"  - Data Race Detected : {CLR_RED}YA (Error!){CLR_RESET}" if actual != expected else f"  - Data Race Detected : {CLR_GREEN}TIDAK (Lock-free atomic safety tercapai){CLR_RESET}")


# ==============================================================================
# 4. Simulasi Thread-Safe Queue (std::condition_variable)
# ==============================================================================
def demo_condition_variable_queue():
    header("Modul 4: Producer-Consumer dengan std::condition_variable & Predicate Guard")
    print(f"{CLR_YELLOW}Penjelasan: Menghindari Spurious Wakeup menggunakan loop predicate:")
    print(f"  cv.wait(lock, [this]{{ return !queue.empty(); }});{CLR_RESET}\n")

    class ThreadSafeBoundedQueue:
        def __init__(self, capacity: int = 5):
            self.capacity = capacity
            self.buffer: List[int] = []
            self.mutex = threading.Lock()
            self.cv_not_full = threading.Condition(self.mutex)
            self.cv_not_empty = threading.Condition(self.mutex)
            self.is_shutdown = False

        def push(self, item: int):
            with self.cv_not_full:
                while len(self.buffer) >= self.capacity and not self.is_shutdown:
                    self.cv_not_full.wait()
                if self.is_shutdown:
                    return
                self.buffer.append(item)
                log_step("Producer", CLR_BLUE, f"Pushed item [{item}]. Buffer size: {len(self.buffer)}/{self.capacity}")
                self.cv_not_empty.notify()

        def pop(self) -> Optional[int]:
            with self.cv_not_empty:
                while len(self.buffer) == 0 and not self.is_shutdown:
                    self.cv_not_empty.wait()
                if len(self.buffer) == 0 and self.is_shutdown:
                    return None
                item = self.buffer.pop(0)
                log_step("Consumer", CLR_MAGENTA, f"Popped item [{item}]. Buffer size: {len(self.buffer)}/{self.capacity}")
                self.cv_not_full.notify()
                return item

        def shutdown(self):
            with self.mutex:
                self.is_shutdown = True
                self.cv_not_full.notify_all()
                self.cv_not_empty.notify_all()

    bq = ThreadSafeBoundedQueue(capacity=3)

    def producer():
        for i in range(1, 7):
            bq.push(i * 10)
            time.sleep(0.08)

    def consumer():
        consumed = 0
        while consumed < 6:
            item = bq.pop()
            if item is not None:
                consumed += 1
            time.sleep(0.12)

    tp = threading.Thread(target=producer, name="Prod-1")
    tc = threading.Thread(target=consumer, name="Cons-1")

    tp.start()
    tc.start()
    tp.join()
    tc.join()
    bq.shutdown()
    print(f"\n{CLR_GREEN}{CLR_BOLD}[OK] Aliran producer-consumer sinkron tanpa lost wakeup atau dead wait.{CLR_RESET}")


# ==============================================================================
# 5. Simulasi False Sharing & Cache Alignment
# ==============================================================================
def demo_false_sharing():
    header("Modul 5: False Sharing & hardware_destructive_interference_size")
    print(f"{CLR_YELLOW}Penjelasan: Jika dua variabel independen berada pada cache line yang sama (biasanya 64 bytes),")
    print(f"modifikasi pada Core 1 akan membatalkan (invalidate) L1 cache Core 2 (MESI protocol invalidation).")
    print(f"C++17 menyediakan 'alignas(std::hardware_destructive_interference_size)' untuk solusinya.{CLR_RESET}\n")

    # Simulasi visual layout memori cache line
    cache_line_size = 64
    print(f"  {CLR_BOLD}Representasi 64-byte Cache Line Tanpa Padding (Terjadi False Sharing):{CLR_RESET}")
    print(f"  +-------------------------------+-------------------------------+")
    print(f"  | Core 0 data: thread_a_counter | Core 1 data: thread_b_counter |  <-- Cache Line (64 Bytes)")
    print(f"  +-------------------------------+-------------------------------+")
    print(f"  {CLR_RED}Status: Core 0 dan Core 1 saling memicu Cache Ping-Pong Invalidation!{CLR_RESET}\n")

    print(f"  {CLR_BOLD}Representasi dengan alignas(64) Memory Alignment:{CLR_RESET}")
    print(f"  [Cache Line 0 (64B)]: | thread_a_counter | ... [56 bytes PADDING] ... |")
    print(f"  [Cache Line 1 (64B)]: | thread_b_counter | ... [56 bytes PADDING] ... |")
    print(f"  {CLR_GREEN}Status: Masing-masing core bekerja di L1 Cache privat tanpa interferensi bus.{CLR_RESET}")


# ==============================================================================
# Menu Utama Interaktif
# ==============================================================================
def print_banner():
    banner = f"""{CLR_CYAN}{CLR_BOLD}
 ====================================================================
 |    C++ CONCURRENT & PARALLEL SYSTEMS LAB SIMULATOR (BAB-06)     |
 ====================================================================
  [1] Simulasi std::jthread & RAII Stop Token (C++20)
  [2] Deadlock Prevention dengan std::scoped_lock (C++17)
  [3] std::atomic & Memory Ordering Verification
  [4] Thread-Safe Bounded Queue dengan std::condition_variable
  [5] False Sharing & Cache Alignment (alignas / Hardware Interference)
  [6] Jalankan Seluruh Demonstrasi (Automated Benchmark Suite)
  [0] Keluar
 --------------------------------------------------------------------{CLR_RESET}"""
    print(banner)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "auto"):
        demo_jthread()
        demo_deadlock_avoidance()
        demo_atomic_memory_order()
        demo_condition_variable_queue()
        demo_false_sharing()
        print(f"\n{CLR_GREEN}{CLR_BOLD}Seluruh demonstrasi modul konkurensi C++ sukses dijalankan.{CLR_RESET}\n")
        return

    while True:
        print_banner()
        try:
            choice = input(f"{CLR_BOLD}Pilih nomor menu (0-6): {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            demo_jthread()
        elif choice == "2":
            demo_deadlock_avoidance()
        elif choice == "3":
            demo_atomic_memory_order()
        elif choice == "4":
            demo_condition_variable_queue()
        elif choice == "5":
            demo_false_sharing()
        elif choice == "6":
            demo_jthread()
            demo_deadlock_avoidance()
            demo_atomic_memory_order()
            demo_condition_variable_queue()
            demo_false_sharing()
        elif choice == "0":
            print(f"\n{CLR_GREEN}Selesai. Selamat mempelajari sistem paralel C++!{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan masukkan angka 0 s.d. 6.{CLR_RESET}")


if __name__ == "__main__":
    main()

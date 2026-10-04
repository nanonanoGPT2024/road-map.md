#!/usr/bin/env python3
"""
Lab Hands-on: Konkurensi POSIX Threads, Sinkronisasi, & Model Atomics
Topik: C (02-Programming-Languages) - Bab 09 Deep Dive

Script ini memodelkan dan mensimulasikan semantik teknis inti dari pemrograman
multithreaded bergaya POSIX (pthreads) dan C11 Atomics:
1. Data Race & Undefined Behavior vs Sinkronisasi Mutex (pthread_mutex_t).
2. Lock-free Atomic Compare-And-Swap (CAS) loop (C11 atomic_compare_exchange_weak).
3. POSIX Condition Variable (pthread_cond_t) Pattern untuk Producer-Consumer Pipeline.
"""

import sys
import time
import threading
from collections import deque

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"
CLR_GRAY = "\033[90m"

def log_header(title: str):
    width = 75
    print(f"\n{CLR_CYAN}{CLR_BOLD}{'=' * width}")
    print(f" {title.center(width - 2)}")
    print(f"{'=' * width}{CLR_RESET}")

def log_sub(title: str):
    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- {title} ---{CLR_RESET}")

# ============================================================================
# 1. SIMULASI ATOMIK LEVEL-HARDWARE & DATA RACE
# ============================================================================

class UnsafeCounter:
    """
    Simulasi variabel memori telanjang (raw shared memory) tanpa sinkronisasi.
    Mengakibatkan Data Race ketika diakses konkuren antar thread.
    """
    def __init__(self):
        self.value = 0

    def increment(self):
        # Sengaja mensimulasikan race condition (Read-Modify-Write non-atomik)
        # Meniru instruksi assembly non-atomik: MOV EAX, [mem]; INC EAX; MOV [mem], EAX
        curr = self.value
        time.sleep(0.000005)  # Paksa context switch preemptive
        self.value = curr + 1


class PthreadMutexCounter:
    """
    Implementasi sinkronisasi mutual exclusion standar (pthread_mutex_t).
    Mengorbankan throughput akibat lock contention & context switching overhead.
    """
    def __init__(self):
        self.value = 0
        self._mutex = threading.Lock()

    def increment(self):
        # pthread_mutex_lock(&mutex)
        with self._mutex:
            curr = self.value
            time.sleep(0.000005)
            self.value = curr + 1
        # pthread_mutex_unlock(&mutex)


class HardwareMemoryBus:
    """
    Mensimulasikan bus locking hardware (x86 LOCK prefix) untuk atomics murni.
    Digunakan untuk mendemonstrasikan semantik C11 `atomic_compare_exchange`.
    """
    _bus_lock = threading.Lock()

    @classmethod
    def compare_and_swap(cls, target_obj: 'AtomicCASCounter', expected: int, desired: int) -> bool:
        # Atomic CAS Instruction: CMPXCHG r/m32, r32
        with cls._bus_lock:
            if target_obj._raw_value == expected:
                target_obj._raw_value = desired
                return True
            return False


class AtomicCASCounter:
    """
    Simulasi Lock-Free Counter berbasis C11 Atomics / GCC __atomic_compare_exchange_n.
    Menggunakan spin-loop (optimistic concurrency) tanpa OS thread sleeping.
    """
    def __init__(self):
        self._raw_value = 0
        self.retry_count = 0
        self._retry_lock = threading.Lock()

    @property
    def value(self):
        return self._raw_value

    def increment(self):
        # C11 Lock-Free Pattern:
        # int expected = atomic_load(&counter);
        # while (!atomic_compare_exchange_weak(&counter, &expected, expected + 1));
        while True:
            expected = self._raw_value
            desired = expected + 1
            if HardwareMemoryBus.compare_and_swap(self, expected, desired):
                break
            # CAS Gagal (interleaving terjadi dari thread lain), ulangi loop
            with self._retry_lock:
                self.retry_count += 1


# ============================================================================
# 2. SINKRONISASI POSIX CONDITION VARIABLE (pthread_cond_t)
# ============================================================================

class PosixBoundedBuffer:
    """
    Implementasi thread-safe ring buffer dengan semantik strictly POSIX:
    - 1 Mutex: pthread_mutex_t
    - 2 CondVars: pthread_cond_t (cond_not_full, cond_not_empty)
    - Anti-spurious wakeup idiom: while (predikat) pthread_cond_wait(&cond, &mutex);
    """
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self.buffer = deque()
        self.mutex = threading.Lock()
        self.cond_not_empty = threading.Condition(self.mutex)
        self.cond_not_full = threading.Condition(self.mutex)
        self.closed = False

    def put(self, item: int, producer_id: int):
        # pthread_mutex_lock(&mutex)
        with self.cond_not_full:
            # POSIX Best Practice: WAJIB menggunakan WHILE loop untuk menghindari Spurious Wakeups
            while len(self.buffer) >= self.capacity and not self.closed:
                print(f"{CLR_GRAY}[P{producer_id}] Buffer PENUH ({len(self.buffer)}/{self.capacity}). "
                      f"pthread_cond_wait(&cond_not_full, &mutex)...{CLR_RESET}")
                self.cond_not_full.wait()

            if self.closed:
                return

            self.buffer.append(item)
            print(f"{CLR_GREEN}[P{producer_id}] PRODUCED: {item:03d} | "
                  f"Buffer: {list(self.buffer)} | pthread_cond_signal(&cond_not_empty){CLR_RESET}")

            # pthread_cond_signal(&cond_not_empty)
            self.cond_not_empty.notify()

    def get(self, consumer_id: int):
        # pthread_mutex_lock(&mutex)
        with self.cond_not_empty:
            while len(self.buffer) == 0 and not self.closed:
                print(f"{CLR_GRAY}[C{consumer_id}] Buffer KOSONG. "
                      f"pthread_cond_wait(&cond_not_empty, &mutex)...{CLR_RESET}")
                self.cond_not_empty.wait()

            if self.closed and len(self.buffer) == 0:
                return None

            item = self.buffer.popleft()
            print(f"{CLR_MAGENTA}[C{consumer_id}] CONSUMED: {item:03d} | "
                  f"Buffer: {list(self.buffer)} | pthread_cond_signal(&cond_not_full){CLR_RESET}")

            # pthread_cond_signal(&cond_not_full)
            self.cond_not_full.notify()
            return item

    def close(self):
        with self.mutex:
            self.closed = True
            # pthread_cond_broadcast() ke semua thread yang sedang blocked
            self.cond_not_empty.notify_all()
            self.cond_not_full.notify_all()


# ============================================================================
# 3. EXPERIMENT HARNESS & BENCHMARK SUITE
# ============================================================================

def run_counter_benchmark():
    log_sub("1. Comparative Analysis: Data Race vs Mutex vs Atomic CAS")
    
    num_threads = 8
    increments_per_thread = 200
    expected_total = num_threads * increments_per_thread

    print(f"Konfigurasi Beban Kerja: {num_threads} Pthreads, "
          f"{increments_per_thread} operasi/thread. Total Expected: {expected_total}\n")

    # A. Unsynchronized
    unsafe = UnsafeCounter()
    threads = [threading.Thread(target=lambda: [unsafe.increment() for _ in range(increments_per_thread)]) 
               for _ in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    t_unsafe = (time.perf_counter() - t0) * 1000
    err_pct = ((expected_total - unsafe.value) / expected_total) * 100

    # B. Mutex Protected
    mutex_ctr = PthreadMutexCounter()
    threads = [threading.Thread(target=lambda: [mutex_ctr.increment() for _ in range(increments_per_thread)]) 
               for _ in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    t_mutex = (time.perf_counter() - t0) * 1000

    # C. Lock-free Atomic CAS
    atomic_ctr = AtomicCASCounter()
    threads = [threading.Thread(target=lambda: [atomic_ctr.increment() for _ in range(increments_per_thread)]) 
               for _ in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    t_atomic = (time.perf_counter() - t0) * 1000

    # Output Evaluasi
    print(f"{'Metrik / Primitif':<25} | {'Hasil':<10} | {'Status Integritas':<20} | {'Waktu (ms)':<10}")
    print("-" * 75)
    print(f"{'Raw Shared Memory':<25} | {unsafe.value:<10} | "
          f"{CLR_RED}RACE DETECTED (-{err_pct:.1f}%){CLR_RESET}{'':<1} | {t_unsafe:.2f} ms")
    print(f"{'pthread_mutex_t':<25} | {mutex_ctr.value:<10} | "
          f"{CLR_GREEN}SYNCHRONIZED (OK){CLR_RESET}{'':<5} | {t_mutex:.2f} ms")
    print(f"{'C11 Atomic CAS':<25} | {atomic_ctr.value:<10} | "
          f"{CLR_GREEN}LOCK-FREE (OK){CLR_RESET}{'':<8} | {t_atomic:.2f} ms")
    print("-" * 75)
    print(f"{CLR_CYAN}Info Lock-Free CAS: Terjadi {atomic_ctr.retry_count} retries akibat thread contention.{CLR_RESET}")


def run_pipeline_simulation():
    log_sub("2. Pipeline Simulation: POSIX Condition Variables Producer-Consumer")
    
    buf_size = 4
    total_items = 12
    ring_buf = PosixBoundedBuffer(capacity=buf_size)

    def producer_worker(p_id: int, items: list):
        for val in items:
            ring_buf.put(val, p_id)
            time.sleep(0.01)

    def consumer_worker(c_id: int):
        while True:
            val = ring_buf.get(c_id)
            if val is None:
                break
            time.sleep(0.02)  # Konsumen bekerja lebih lambat dari produsen

    items = list(range(100, 100 + total_items))
    mid = len(items) // 2

    # Buat 2 Produser dan 2 Konsumen (Simulasi sistem konkurensi heterogen)
    p1 = threading.Thread(target=producer_worker, args=(1, items[:mid]))
    p2 = threading.Thread(target=producer_worker, args=(2, items[mid:]))
    c1 = threading.Thread(target=consumer_worker, args=(1,))
    c2 = threading.Thread(target=consumer_worker, args=(2,))

    print(f"Menjalankan Pipeline: Buffer Capacity={buf_size}, Items={total_items}")
    c1.start(); c2.start()
    p1.start(); p2.start()

    p1.join(); p2.join()
    ring_buf.close()
    c1.join(); c2.join()
    print(f"\n{CLR_GREEN}{CLR_BOLD}Semua thread selesai secara konsisten tanpa Deadlock / Starvation.{CLR_RESET}")


def main():
    log_header("LAB ENGINE: POSIX CONCURRENCY, SYNCHRONIZATION & ATOMICS")
    print(f"{CLR_BOLD}Lingkungan Eksekusi:{CLR_RESET} Python Standard Concurrency Engine")
    print(f"{CLR_BOLD}Objek Simulasi:{CLR_RESET} Mutex Primitives, Memory Fences, Atomic CAS & CondVars\n")

    run_counter_benchmark()
    run_pipeline_simulation()

    log_header("LAB SUMMARY & SYSTEM ARCHITECTURE INSIGHTS")
    print(f"""
1. {CLR_YELLOW}Data Race / Non-atomic RMW:{CLR_RESET}
   Operasi seperti `val++` tidak atomik di level assembly (terdiri dari LOAD, ADD, STORE).
   Tanpa sinkronisasi, CPU thread interleaving memicu hilangnya pembaruan memori (Lost Updates).

2. {CLR_YELLOW}pthread_mutex_t (Pessimistic Locking):{CLR_RESET}
   Menjamin 'Mutual Exclusion' menggunakan sistem operasi scheduler lock. Aman untuk critical
   section multi-pernyataan, tetapi menghasilkan overhead OS context switch saat contention tinggi.

3. {CLR_YELLOW}C11 Atomics / CAS (Optimistic Lock-Free):{CLR_RESET}
   Menerapkan instruksi tingkat prosesor tunggal (misal `CMPXCHG`). Meniadakan blocking kernel,
   namun memicu 'spinning' dan CAS retries di bawah perebutan akses agresif.

4. {CLR_YELLOW}POSIX pthread_cond_wait Pattern:{CLR_RESET}
   Wajib selalu dieksekusi di dalam loop `while(!condition)` untuk mencegah Spurious Wakeup,
   dan mutlak melepaskan serta mengakuisisi kembali mutex yang bersangkutan secara atomik.
""")

if __name__ == "__main__":
    main()
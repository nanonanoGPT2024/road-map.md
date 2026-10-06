#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Konkurensi C & POSIX Threads (BAB-09)
Mengilustrasikan konsep:
1. Race Condition vs Mutex (pthread_mutex_t)
2. Condition Variable (pthread_cond_t) - Pola Producer-Consumer
3. C11 Atomics & Memory Ordering Simulation (Sequential Consistency vs Relaxed)
4. POSIX Thread Barrier (pthread_barrier_t)
"""

import sys
import time
import threading
from typing import List

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"

def print_banner(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 65}")
    print(f" [*] {title}")
    print(f"{'=' * 65}{CLR_RESET}\n")

# ==============================================================================
# MODUL 1: Race Condition vs POSIX Mutex Simulation
# ==============================================================================
class MutexDemo:
    def __init__(self):
        self.counter_unsafe = 0
        self.counter_safe = 0
        self.lock = threading.Lock()
        self.iterations = 25000

    def _worker_unsafe(self):
        for _ in range(self.iterations):
            # Simulasi operasi Read-Modify-Write non-atomik di C:
            # temp = counter; temp = temp + 1; counter = temp;
            val = self.counter_unsafe
            time.sleep(0.000001)
            self.counter_unsafe = val + 1

    def _worker_safe(self):
        for _ in range(self.iterations):
            # Simulasi pthread_mutex_lock(&lock) & pthread_mutex_unlock(&lock)
            with self.lock:
                val = self.counter_safe
                self.counter_safe = val + 1

    def run(self):
        print_banner("DEMO 1: Data Race vs Mutex (pthread_mutex_t)")
        target = self.iterations * 4
        print(f"{CLR_YELLOW}[INFO]{CLR_RESET} Menjalankan 4 thread dengan target akhir: {CLR_BOLD}{target:,}{CLR_RESET}")

        # Jalankan Unsafe
        print(f"\n{CLR_BLUE}--- Menjalankan Operasi Non-Thread-Safe (Tanpa Mutex) ---{CLR_RESET}")
        threads_unsafe = [threading.Thread(target=self._worker_unsafe) for _ in range(4)]
        t0 = time.time()
        for t in threads_unsafe:
            t.start()
        for t in threads_unsafe:
            t.join()
        dur_unsafe = time.time() - t0
        loss = target - self.counter_unsafe
        print(f"Hasil Unsafe Counter : {CLR_RED}{self.counter_unsafe:,}{CLR_RESET} (Kehilangan {loss:,} updates)")
        print(f"Waktu Eksekusi       : {dur_unsafe:.4f} detik")

        # Jalankan Safe
        print(f"\n{CLR_BLUE}--- Menjalankan Operasi Thread-Safe (Dengan Mutex) ---{CLR_RESET}")
        threads_safe = [threading.Thread(target=self._worker_safe) for _ in range(4)]
        t0 = time.time()
        for t in threads_safe:
            t.start()
        for t in threads_safe:
            t.join()
        dur_safe = time.time() - t0
        print(f"Hasil Safe Counter   : {CLR_GREEN}{self.counter_safe:,}{CLR_RESET} (100% Akurat)")
        print(f"Waktu Eksekusi       : {dur_safe:.4f} detik")

# ==============================================================================
# MODUL 2: Condition Variable (pthread_cond_t) - Producer / Consumer
# ==============================================================================
class CondVarDemo:
    def __init__(self, capacity=5):
        self.capacity = capacity
        self.queue: List[int] = []
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
        self.done = False

    def producer(self, pid: int, count: int):
        for i in range(count):
            item = pid * 100 + i
            with self.lock:
                # Pola C: while (is_full) pthread_cond_wait(&not_full, &mutex);
                while len(self.queue) >= self.capacity:
                    print(f"  {CLR_YELLOW}[PRODUCER-{pid}]{CLR_RESET} Buffer penuh ({len(self.queue)}/{self.capacity}). Menunggu signal...")
                    self.not_full.wait()
                
                self.queue.append(item)
                print(f"  {CLR_GREEN}[PRODUCER-{pid}]{CLR_RESET} Menaruh item {item:03d} -> Buffer: {len(self.queue)}/{self.capacity}")
                # Pola C: pthread_cond_signal(&not_empty);
                self.not_empty.notify()
            time.sleep(0.04)

    def consumer(self, cid: int):
        while True:
            with self.lock:
                # Pola C: while (is_empty && !done) pthread_cond_wait(&not_empty, &mutex);
                while len(self.queue) == 0 and not self.done:
                    print(f"  {CLR_MAGENTA}[CONSUMER-{cid}]{CLR_RESET} Buffer kosong. Menunggu items...")
                    self.not_empty.wait()

                if len(self.queue) == 0 and self.done:
                    break

                item = self.queue.pop(0)
                print(f"  {CLR_CYAN}[CONSUMER-{cid}]{CLR_RESET} Mengambil item {item:03d} <- Buffer sisa: {len(self.queue)}/{self.capacity}")
                # Pola C: pthread_cond_signal(&not_full);
                self.not_full.notify()
            time.sleep(0.07)

    def run(self):
        print_banner("DEMO 2: Condition Variables (pthread_cond_wait / signal)")
        print(f"{CLR_YELLOW}[INFO]{CLR_RESET} Kapasitas Bounded Buffer: {self.capacity}")
        c1 = threading.Thread(target=self.consumer, args=(1,))
        c2 = threading.Thread(target=self.consumer, args=(2,))
        p1 = threading.Thread(target=self.producer, args=(1, 6))
        p2 = threading.Thread(target=self.producer, args=(2, 6))

        c1.start()
        c2.start()
        p1.start()
        p2.start()

        p1.join()
        p2.join()

        with self.lock:
            self.done = True
            # Pola C: pthread_cond_broadcast(&not_empty);
            self.not_empty.notify_all()

        c1.join()
        c2.join()
        print(f"{CLR_GREEN}[SUKSES]{CLR_RESET} Seluruh transaksi Producer-Consumer selesai secara sinkron!")

# ==============================================================================
# MODUL 3: C11 Atomics & Memory Ordering Emulation
# ==============================================================================
class AtomicsDemo:
    def __init__(self):
        self.atomic_val = 0
        self.lock = threading.Lock()

    def fetch_add(self, delta: int, order: str) -> int:
        """Simulasi C11: atomic_fetch_add_explicit(&val, delta, memory_order_*)"""
        with self.lock:
            prev = self.atomic_val
            self.atomic_val += delta
            # Memberikan representasi instruksi hardware (LOCK XADD pada x86-64)
            return prev

    def run(self):
        print_banner("DEMO 3: C11 Atomics (stdatomic.h) & Memory Orders")
        orders = [
            ("memory_order_relaxed", "Tidak ada ordering barrier; hanya atomisitas operasi."),
            ("memory_order_acquire", "Sinkronisasi load; menjamin instruksi setelahnya tidak dipindahkan ke atas."),
            ("memory_order_release", "Sinkronisasi store; menjamin instruksi sebelumnya selesai sebelum store."),
            ("memory_order_seq_cst", "Total Globally Consistent Order (Default C11 atomics).")
        ]

        print(f"{CLR_BOLD}Daftar Model Memori C11:{CLR_RESET}")
        for ord_name, desc in orders:
            print(f"  * {CLR_GREEN}{ord_name:<23}{CLR_RESET}: {desc}")

        print(f"\n{CLR_BLUE}Simulasi 8 Worker memanggil atomic_fetch_add_explicit():{CLR_RESET}")
        self.atomic_val = 0
        
        def worker(tid: int):
            for _ in range(500):
                self.fetch_add(1, "memory_order_seq_cst")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print(f"Nilai akhir C11 _Atomic int : {CLR_GREEN}{self.atomic_val}{CLR_RESET} (Ekspektasi: 4000)")

# ==============================================================================
# MODUL 4: POSIX Barrier Simulation (pthread_barrier_t)
# ==============================================================================
class BarrierDemo:
    def __init__(self, num_threads=4):
        self.num_threads = num_threads
        self.barrier = threading.Barrier(num_threads)

    def worker(self, tid: int):
        print(f"  {CLR_YELLOW}[Thread-{tid}]{CLR_RESET} Fase 1: Membaca chunk data memori...")
        time.sleep(0.03 * (tid + 1))
        print(f"  {CLR_CYAN}[Thread-{tid}]{CLR_RESET} Mencapai pthread_barrier_wait(). Menunggu rekan thread lain...")
        
        # Pola C: pthread_barrier_wait(&barrier)
        self.barrier.wait()
        
        print(f"  {CLR_GREEN}[Thread-{tid}]{CLR_RESET} Fase 2: Melewati barrier! Memulai proses komputasi paralel.")

    def run(self):
        print_banner("DEMO 4: POSIX Thread Barrier (pthread_barrier_wait)")
        print(f"{CLR_YELLOW}[INFO]{CLR_RESET} Menginisialisasi barrier untuk {self.num_threads} threads.")
        threads = [threading.Thread(target=self.worker, args=(i,)) for i in range(self.num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print(f"{CLR_GREEN}[SUKSES]{CLR_RESET} Seluruh thread melewati barrier secara bersamaan!")

# ==============================================================================
# CLI MENU & MAIN CONTROLLER
# ==============================================================================
def print_menu():
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}  LAB INTERAKTIF: KONKURENSI & POSIX THREADS C (BAB-09){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}")
    print(f"  {CLR_GREEN}[1]{CLR_RESET} Simulasi Race Condition vs Mutex (pthread_mutex_t)")
    print(f"  {CLR_GREEN}[2]{CLR_RESET} Simulasi Condition Variables (Producer-Consumer)")
    print(f"  {CLR_GREEN}[3]{CLR_RESET} Simulasi C11 Atomics & Memory Ordering Semantics")
    print(f"  {CLR_GREEN}[4]{CLR_RESET} Simulasi POSIX Barrier Synchronization (pthread_barrier_t)")
    print(f"  {CLR_GREEN}[5]{CLR_RESET} Jalankan SEMUA Modul Simulasi Berurutan")
    print(f"  {CLR_RED}[0]{CLR_RESET} Keluar")
    print(f"{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}")

def main():
    # Jika dijalankan non-interaktif dengan argumen CLI (misal 'all' atau 'test')
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("all", "--all", "-a", "run"):
        MutexDemo().run()
        CondVarDemo().run()
        AtomicsDemo().run()
        BarrierDemo().run()
        print(f"\n{CLR_BOLD}{CLR_GREEN}[+] Semua simulasi konkurensi selesai dijalankan.{CLR_RESET}\n")
        return

    while True:
        try:
            print_menu()
            choice = input(f"{CLR_BOLD}Pilih opsi (0-5) > {CLR_RESET}").strip()
            if choice == "1":
                MutexDemo().run()
            elif choice == "2":
                CondVarDemo().run()
            elif choice == "3":
                AtomicsDemo().run()
            elif choice == "4":
                BarrierDemo().run()
            elif choice == "5":
                MutexDemo().run()
                CondVarDemo().run()
                AtomicsDemo().run()
                BarrierDemo().run()
                print(f"\n{CLR_BOLD}{CLR_GREEN}[+] Selesai menjalankan seluruh modul simulasi.{CLR_RESET}")
            elif choice in ("0", "q", "exit"):
                print(f"{CLR_YELLOW}Keluar dari lab konkurensi C. Sampai jumpa!{CLR_RESET}\n")
                break
            else:
                print(f"{CLR_RED}[!] Pilihan tidak valid. Silakan coba lagi.{CLR_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CLR_YELLOW}Operasi dibatalkan oleh pengguna. Keluar.{CLR_RESET}\n")
            break

if __name__ == "__main__":
    main()

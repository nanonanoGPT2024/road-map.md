#!/usr/bin/env python3
"""
Ruby Concurrency & Parallelism Deep-Dive Simulator
==================================================
Topik: BAB-05 Concurrency, Parallelism & Multi-Threading di Ruby
Materi yang disimulasikan:
  1. MRI GVL (Global VM Lock): Mengapa Ruby Threads cocok untuk I/O tapi terhambat pada CPU-bound.
  2. Ruby Fibers: Cooperative lightweight coroutines (manual yield/resume tanpa OS overhead).
  3. Ruby 3 Ractors: Actor-model message passing & memory isolation untuk true parallelism tanpa GVL.

Dijalankan secara mandiri dengan Python 3 murni (Standard Library).
"""

import sys
import time
import threading
import queue
from typing import List, Dict, Any

# ANSI Color Codes untuk Terminal Output Interaktif
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 72}{RESET}")
    print(f"{BOLD}{WHITE}{title.center(72)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 72}{RESET}\n")


def subheader(title: str) -> None:
    print(f"{BOLD}{YELLOW}>>> {title}{RESET}")


# ==============================================================================
# 1. SIMULASI MRI GVL (GLOBAL VM LOCK) & THREADS
# ==============================================================================
class RubyGVLSimulator:
    """
    Mensimulasikan perilaku MRI (CRuby) GVL:
    - Hanya 1 thread Ruby yang dapat mengeksekusi bytecode pada satu saat.
    - Operasi I/O (blocking) melepas GVL, sehingga thread lain bisa berjalan.
    - Operasi CPU-bound berebut GVL (preemptive time-slice switching, bukan parallel).
    """

    def __init__(self):
        self.gvl_lock = threading.Lock()
        self.log_lock = threading.Lock()

    def log(self, thread_name: str, message: str, color: str = WHITE) -> None:
        with self.log_lock:
            ts = time.strftime("%H:%M:%S")
            print(f"[{DIM}{ts}{RESET}] {color}[Ruby Thread: {thread_name}]{RESET} {message}")

    def simulate_cpu_bound_task(self, thread_id: int, iterations: int = 3) -> None:
        name = f"worker-{thread_id}"
        self.log(name, f"Memulai kalkulasi CPU-bound ({iterations} siklus)...", CYAN)
        for i in range(1, iterations + 1):
            # Memperoleh GVL untuk mengeksekusi bytecode Ruby
            with self.gvl_lock:
                self.log(name, f"Memperoleh {RED}GVL Lock{RESET} -> Mengeksekusi loop #{i}", GREEN)
                # Simulasi kerja CPU
                end = time.time() + 0.08
                while time.time() < end:
                    pass
                self.log(name, f"Preempted / Melepas {RED}GVL Lock{RESET} setelah slice #{i}", YELLOW)
            time.sleep(0.01)  # Context switch window
        self.log(name, "Kalkulasi CPU-bound selesai!", MAGENTA)

    def simulate_io_bound_task(self, thread_id: int, wait_sec: float = 0.2) -> None:
        name = f"io-worker-{thread_id}"
        with self.gvl_lock:
            self.log(name, f"Menginisiasi Socket/Disk I/O ({wait_sec}s)...", BLUE)
            self.log(name, f"{YELLOW}[GVL RELEASED]{RESET} Melepas GVL karena entering I/O wait", YELLOW)

        # I/O wait berjalan di luar GVL (OS thread sleeping / waiting socket)
        time.sleep(wait_sec)

        with self.gvl_lock:
            self.log(name, f"{GREEN}[GVL RE-ACQUIRED]{RESET} I/O selesai, memproses response", GREEN)
        self.log(name, "Tugas I/O beres!", MAGENTA)


# ==============================================================================
# 2. SIMULASI RUBY FIBERS (COOPERATIVE CONCURRENCY / COROUTINES)
# ==============================================================================
class RubyFiberSimulator:
    """
    Mensimulasikan Fiber di Ruby:
    - Cooperative multitasking: fiber tidak di-preempt oleh scheduler secara paksa.
    - Fiber secara sadar memanggil `Fiber.yield` untuk menyerahkan kontrol.
    - Caller melanjutkan eksekusi dengan `fiber.resume`.
    """

    def __init__(self, name: str):
        self.name = name
        self.state = "created"
        self._gen = None

    def _coroutine_body(self):
        print(f"  {CYAN}* Fiber [{self.name}]: Aktif (Tahap 1) - Inisialisasi resource{RESET}")
        yield "Step-1: Resource Siap"

        print(f"  {CYAN}* Fiber [{self.name}]: Melakukan parsing parser batch 1{RESET}")
        yield "Step-2: Parsing Batch 1 Selesai"

        print(f"  {CYAN}* Fiber [{self.name}]: Finalisasi transformasi data dan cleanup{RESET}")
        self.state = "dead"
        return "Step-3: Selesai (Terminated)"

    def resume(self) -> Any:
        if self.state == "dead":
            raise RuntimeError(f"FiberError: dead fiber called for [{self.name}]")

        if self._gen is None:
            self._gen = self._coroutine_body()
            self.state = "resumed"

        try:
            val = next(self._gen)
            self.state = "suspended"
            return val
        except StopIteration as e:
            self.state = "dead"
            return e.value


# ==============================================================================
# 3. SIMULASI RUBY 3 RACTORS (ACTOR MODEL & SHARE-NOTHING PARALLELISM)
# ==============================================================================
class RubyRactorSimulator:
    """
    Mensimulasikan Ractor (Ruby 3):
    - Share-nothing architecture: tidak berbagi state mutable secara sembarangan.
    - Komunikasi aman via message passing (take / send).
    - Berjalan parallel secara nyata di OS Thread terpisah tanpa terhambat GVL global.
    """

    def __init__(self, ractor_id: int):
        self.id = ractor_id
        self.inbox = queue.Queue()
        self.outbox = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = True
        self._thread.start()

    def _run(self) -> None:
        while self._running:
            try:
                msg = self.inbox.get(timeout=0.1)
                if msg == "__TERMINATE__":
                    break
                # Ractor memproses pesan dalam isolasi total
                res = f"Ractor #{self.id} mentransformasikan: '{msg.upper()}' (Length: {len(msg)})"
                time.sleep(0.05)
                self.outbox.put(res)
            except queue.Empty:
                continue

    def send(self, data: str) -> None:
        """Kirim pesan ke mailbox Ractor (Ractor#send)"""
        self.inbox.put(data)

    def take(self, timeout: float = 1.0) -> str:
        """Mengambil hasil kalkulasi dari Ractor (Ractor.take)"""
        return self.outbox.get(timeout=timeout)

    def terminate(self) -> None:
        self.inbox.put("__TERMINATE__")
        self._thread.join()


# ==============================================================================
# INTERACTIVE CLI DEMO & BENCHMARK
# ==============================================================================
def demo_gvl():
    header("DEMO 1: SIMULASI MRI GVL (GLOBAL VM LOCK)")
    print(f"{WHITE}Perhatikan bagaimana worker CPU-bound harus bergantian mendapatkan GVL,{RESET}")
    print(f"{WHITE}sedangkan I/O-bound melepaskan GVL sehingga worker lain dapat berjalan.{RESET}\n")

    sim = RubyGVLSimulator()
    threads = []

    # Jalankan 2 CPU threads dan 1 I/O thread
    t_cpu1 = threading.Thread(target=sim.simulate_cpu_bound_task, args=(1, 2))
    t_cpu2 = threading.Thread(target=sim.simulate_cpu_bound_task, args=(2, 2))
    t_io = threading.Thread(target=sim.simulate_io_bound_task, args=(3, 0.15))

    threads.extend([t_cpu1, t_cpu2, t_io])

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    print(f"\n{BOLD}{GREEN}[GVL Demo Selesai] Total durasi eksekusi: {elapsed:.3f}s{RESET}")


def demo_fibers():
    header("DEMO 2: SIMULASI RUBY FIBERS (COOPERATIVE SCHEDULING)")
    print(f"{WHITE}Fiber berjalan secara kooperatif di dalam single thread tanpa preemptive switch.{RESET}")
    print(f"{WHITE}Kontrol berpindah hanya saat Fiber melakukan yield.{RESET}\n")

    fiber_a = RubyFiberSimulator("Fiber-DataIngest")
    fiber_b = RubyFiberSimulator("Fiber-Indexer")

    print(f"{BOLD}[Main Thread]{RESET} Memulai orkestrasi 2 Fiber:")

    for step in range(1, 4):
        print(f"\n{YELLOW}--- Putaran Orkestrasi #{step} ---{RESET}")
        val_a = fiber_a.resume()
        print(f"  {MAGENTA}<- Result from Fiber-A: {val_a} (State: {fiber_a.state}){RESET}")

        val_b = fiber_b.resume()
        print(f"  {BLUE}<- Result from Fiber-B: {val_b} (State: {fiber_b.state}){RESET}")

    print(f"\n{BOLD}{GREEN}[Fiber Demo Selesai] Cooperative switching berjalan deterministik!{RESET}")


def demo_ractors():
    header("DEMO 3: SIMULASI RUBY 3 RACTORS (ACTOR MODEL)")
    print(f"{WHITE}Ractors memiliki mailbox terisolasi dan mengeksekusi komputasi secara paralel{RESET}")
    print(f"{WHITE}tanpa saling mengunci variabel memori global (No Shared Mutable State).{RESET}\n")

    ractor1 = RubyRactorSimulator(1)
    ractor2 = RubyRactorSimulator(2)

    messages = [
        "ruby concurrency is expressive",
        "ractors unlock true multi-core parallel ruby",
        "fiber scheduler handles 100k connections",
        "gvl prevents memory corruption in mri",
    ]

    print(f"{BOLD}[Main Process]{RESET} Mengirim payload data ke Ractor Pool...")
    ractor1.send(messages[0])
    ractor2.send(messages[1])
    ractor1.send(messages[2])
    ractor2.send(messages[3])

    print(f"\n{BOLD}[Main Process]{RESET} Mengambil (take) hasil pemrosesan Ractor:")
    for _ in range(2):
        print(f"  {GREEN}<< Output Ractor 1:{RESET} {ractor1.take()}")
        print(f"  {CYAN}<< Output Ractor 2:{RESET} {ractor2.take()}")

    ractor1.terminate()
    ractor2.terminate()
    print(f"\n{BOLD}{GREEN}[Ractor Demo Selesai] Message passing berhasil tanpa race condition!{RESET}")


def show_comparison_matrix():
    header("RUBY CONCURRENCY MODEL COMPARISON TABLE")
    table = f"""{BOLD}
+-------------------+--------------------+--------------------+-----------------------+
| Fitur / Dimensi   | Thread (MRI)       | Fiber              | Ractor (Ruby 3+)      |
+-------------------+--------------------+--------------------+-----------------------+
{RESET}| Scheduling        | Preemptive (OS)    | Cooperative (User) | Preemptive / Parallel |
| Multi-core CPU    | Tidak (GVL Bound)  | Tidak (Single thr) | Ya (True Parallelism) |
| Memory Isolation  | Shared Memory      | Shared Memory      | Isolated (Immutable)  |
| Memory Overhead   | Sedang (~1MB stack)| Sangat Rendah (4KB)| Sedang-Tinggi         |
| Cocok untuk       | I/O-bound (Web/DB) | High-I/O Web Server| CPU-intensive Tasks   |
| Primitive Sync    | Mutex / Queue      | yield / resume     | send / take (Mailbox) |
+-------------------+--------------------+--------------------+-----------------------+
"""
    print(table)


def run_interactive_menu():
    while True:
        header("LAB SIMULATOR: RUBY CONCURRENCY & PARALLELISM")
        print(f"  {BOLD}1.{RESET} Jalankan Simulasi MRI GVL (Threads & Preemption)")
        print(f"  {BOLD}2.{RESET} Jalankan Simulasi Ruby Fibers (Cooperative Coroutines)")
        print(f"  {BOLD}3.{RESET} Jalankan Simulasi Ruby 3 Ractors (Actor Model)")
        print(f"  {BOLD}4.{RESET} Tampilkan Tabel Perbandingan Komprehensif")
        print(f"  {BOLD}5.{RESET} Jalankan Seluruh Demonstrasi (Automated Suite)")
        print(f"  {BOLD}0.{RESET} Keluar")
        print(f"{CYAN}{'-' * 72}{RESET}")

        try:
            choice = input(f"{BOLD}{WHITE}Pilih opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan.{RESET}")
            break

        if choice == "1":
            demo_gvl()
        elif choice == "2":
            demo_fibers()
        elif choice == "3":
            demo_ractors()
        elif choice == "4":
            show_comparison_matrix()
        elif choice == "5":
            demo_gvl()
            demo_fibers()
            demo_ractors()
            show_comparison_matrix()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah mempelajari arsitektur konkurensi Ruby! Salam koding.{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")

        time.sleep(0.5)


if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif (misal via pipe), jalankan full demo otomatis
    if not sys.stdin.isatty():
        demo_gvl()
        demo_fibers()
        demo_ractors()
        show_comparison_matrix()
    else:
        run_interactive_menu()

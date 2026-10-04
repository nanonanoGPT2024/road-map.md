#!/usr/bin/env python3
"""
Lab: Go Runtime Internals - GMP Scheduler & Work-Stealing Simulation
Bab 10: Modul 02 Deep Dive (Golang Concurrency & Runtime Architecture)

Deskripsi:
Skrip ini mensimulasikan mekanisme scheduler internal Go Runtime:
- G (Goroutine): Unit eksekusi independen dan lightweight.
- M (Machine): OS Thread riil yang mengeksekusi instruksi.
- P (Processor): Resource logis (GOMAXPROCS) yang memegang Local Run Queue (LRQ).
- GRQ (Global Run Queue) & Work-Stealing Algorithm saat P kehabisan G.
"""

import sys
import time
import random
import threading
from collections import deque
from enum import Enum

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[1;36m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_RED = "\033[1;31m"
CLR_MAGENTA = "\033[1;35m"
CLR_DIM = "\033[2m"

class GState(Enum):
    IDLE = "Gidle"
    RUNNABLE = "Grunnable"
    RUNNING = "Grunning"
    DEAD = "Gdead"

class Goroutine:
    """Representasi runtime 'G' dalam Go runtime."""
    def __init__(self, gid: int, task_name: str, total_steps: int):
        self.gid = gid
        self.task_name = task_name
        self.total_steps = total_steps
        self.remaining_steps = total_steps
        self.state = GState.IDLE

    def execute_slice(self, steps: int = 1) -> bool:
        """Mengeksekusi time-slice dari G. Mengembalikan True jika tugas selesai."""
        executed = min(self.remaining_steps, steps)
        self.remaining_steps -= executed
        time.sleep(0.015 * executed)  # Simulasi compute latency
        if self.remaining_steps <= 0:
            self.state = GState.DEAD
            return True
        return False

class Processor:
    """Representasi 'P' (Logical Processor / Context). Memiliki Local Run Queue (LRQ)."""
    def __init__(self, pid: int, capacity: int = 256):
        self.pid = pid
        self.lrq = deque(maxlen=capacity)
        self.lock = threading.Lock()
        self.sched_tick = 0

    def push_runnable(self, g: Goroutine):
        with self.lock:
            g.state = GState.RUNNABLE
            self.lrq.append(g)

    def pop_runnable(self) -> Goroutine | None:
        with self.lock:
            if self.lrq:
                g = self.lrq.popleft()
                return g
            return None

    def steal_half(self) -> list[Goroutine]:
        """Algoritma Work-Stealing: Mencuri separuh isi LRQ dari P lain."""
        with self.lock:
            stolen_count = len(self.lrq) // 2
            stolen = []
            for _ in range(stolen_count):
                stolen.append(self.lrq.pop())
            return stolen

class GoScheduler:
    """GMP Scheduler yang mengelola koordinasi antara Machine (M), Processor (P), dan Goroutine (G)."""
    def __init__(self, gomaxprocs: int):
        self.gomaxprocs = gomaxprocs
        self.processors = [Processor(pid=i) for i in range(gomaxprocs)]
        self.global_queue = deque()
        self.grq_lock = threading.Lock()
        self.is_active = True
        self.completed_g_count = 0
        self.completed_lock = threading.Lock()

    def submit_to_grq(self, g: Goroutine):
        """Memasukkan G baru ke Global Run Queue."""
        with self.grq_lock:
            g.state = GState.RUNNABLE
            self.global_queue.append(g)

    def find_runnable_g(self, p: Processor) -> Goroutine | None:
        """
        Urutan pencarian G oleh P (Aturan Go Runtime):
        1. Setiap 61 tick, periksa Global Run Queue (mencegah starvation).
        2. Periksa LRQ lokal milik P.
        3. Periksa Global Run Queue jika LRQ lokal kosong.
        4. Coba lakukan Work-Stealing dari P lain.
        """
        p.sched_tick += 1

        # 1. Cek GRQ periodik
        if p.sched_tick % 61 == 0:
            with self.grq_lock:
                if self.global_queue:
                    return self.global_queue.popleft()

        # 2. Cek LRQ
        g = p.pop_runnable()
        if g:
            return g

        # 3. Cek GRQ
        with self.grq_lock:
            if self.global_queue:
                return self.global_queue.popleft()

        # 4. Work Stealing: Iterasi random ke P lain
        other_ps = [other for other in self.processors if other.pid != p.pid]
        random.shuffle(other_ps)
        for target_p in other_ps:
            stolen_batch = target_p.steal_half()
            if stolen_batch:
                print(f"{CLR_MAGENTA}[WORK STEAL]{CLR_RESET} P{p.pid} mencuri {len(stolen_batch)} G dari P{target_p.pid}")
                victim_g = stolen_batch.pop(0)
                # Masukkan sisa hasil curian ke queue lokal
                for rem in stolen_batch:
                    p.push_runnable(rem)
                return victim_g

        return None

    def worker_m(self, mid: int, p: Processor):
        """Siklus hidup thread M yang terikat pada konteks P."""
        while self.is_active:
            g = self.find_runnable_g(p)
            if not g:
                time.sleep(0.005)  # M masuk fase idle polling/sysmon sleep
                continue

            g.state = GState.RUNNING
            print(f"{CLR_CYAN}[EXEC]{CLR_RESET} M{mid} (P{p.pid}) mengeksekusi G{g.gid:02d} [{g.task_name}] "
                  f"(Sisa beban: {g.remaining_steps})")

            # Simulasi eksekusi kooperatif time-slicing
            finished = g.execute_slice(steps=2)

            if finished:
                print(f"{CLR_GREEN}[DONE]{CLR_RESET} G{g.gid:02d} [{g.task_name}] selesai dieksekusi.")
                with self.completed_lock:
                    self.completed_g_count += 1
            else:
                # Preempt / requeue ke LRQ lokal
                p.push_runnable(g)

    def print_runtime_trace(self):
        """Menampilkan metrik internal runtime menyerupai GODEBUG=schedtrace=1000."""
        with self.grq_lock:
            grq_len = len(self.global_queue)
        lrq_status = " | ".join([f"P{p.pid}_len={len(p.lrq)}" for p in self.processors])
        print(f"{CLR_DIM}[TRACE] GRQ_len={grq_len} | {lrq_status}{CLR_RESET}")


def run_lab():
    print(f"{CLR_YELLOW}=== LAB HANDS-ON: SIMULASI GO RUNTIME GMP SCHEDULER ==={CLR_RESET}")
    print("Menguji Local/Global Run Queue, Preemption, dan Work-Stealing Paradigm.\n")

    GOMAXPROCS = 2
    sched = GoScheduler(gomaxprocs=GOMAXPROCS)

    # Inisialisasi thread M untuk masing-masing P
    threads = []
    for i in range(GOMAXPROCS):
        p = sched.processors[i]
        t = threading.Thread(target=sched.worker_m, args=(i, p), daemon=True)
        threads.append(t)
        t.start()

    # Skenario: Load Imbalance
    # P0 dimuati secara padat dengan Goroutines, P1 dibiarkan kosong untuk memicu Work-Stealing
    total_tasks = 12
    print(f"{CLR_YELLOW}[SETUP]{CLR_RESET} Menginjeksi {total_tasks} Goroutine ke P0 secara masif...")
    p0 = sched.processors[0]
    for gid in range(1, total_tasks + 1):
        work_load = random.randint(2, 6)
        task_name = f"micro_svc_{gid}"
        g = Goroutine(gid, task_name, work_load)
        p0.push_runnable(g)

    # Tambahkan 2 Goroutine langsung ke Global Run Queue
    sched.submit_to_grq(Goroutine(gid=98, task_name="sys_cleanup", total_steps=3))
    sched.submit_to_grq(Goroutine(gid=99, task_name="bg_metric", total_steps=2))
    expected_completed = total_tasks + 2

    # Monitoring loop
    while True:
        sched.print_runtime_trace()
        time.sleep(0.08)
        with sched.completed_lock:
            if sched.completed_g_count >= expected_completed:
                break

    sched.is_active = False
    print(f"\n{CLR_GREEN}=== SIMULASI SCHEDULER SELESAI ==={CLR_RESET}")
    print(f"Total G selesai dieksekusi: {sched.completed_g_count}/{expected_completed}")
    print(f"Status: Seluruh Work-Stealing dan Run-Queue balancing berhasil dieksekusi dengan aman.")


if __name__ == "__main__":
    try:
        run_lab()
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}[ABORT]{CLR_RESET} Simulasi dihentikan.")
        sys.exit(0)
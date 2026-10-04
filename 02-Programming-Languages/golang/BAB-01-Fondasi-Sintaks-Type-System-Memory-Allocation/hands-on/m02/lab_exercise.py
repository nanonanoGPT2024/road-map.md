#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Architecture Deep Dive (M:P:G Scheduler & Work-Stealing)
Bab 01 - Modul 02: Go Internals & Concurrency Model

Deskripsi:
Simulasi akurat dari Go Scheduler (runtime/proc.go).
Memodelkan interaksi antara:
 - G (Goroutine): Stack eksekusi ringan & instruction counter.
 - M (Machine / OS Thread): Worker thread aktual yang mengeksekusi instruksi.
 - P (Processor / Logical Context): Token sumber daya eksekusi (GOMAXPROCS) dengan Local Run Queue (LRQ).
 - GRQ (Global Run Queue): Antrean fallback dengan penguncian sinkron.
 - Work-Stealing: P mencuri separuh beban kerja dari LRQ milik P lain jika kosong.
 - Sysmon / Fairness: Pengecekan berkala ke GRQ setiap interval tertentu untuk mencegah kelaparan (starvation).
"""

import collections
import random
import sys
import threading
import time
from typing import Deque, List, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_BG_BLACK = "\033[40m"


class GoroutineState:
    IDLE = "_Gidle"
    RUNNABLE = "_Grunnable"
    RUNNING = "_Grunning"
    DEAD = "_Gdead"


class Goroutine:
    """
    Representasi struktur runtime.g di Go.
    Menyimpan ID, total siklus CPU yang dibutuhkan, sisa instruksi, dan state eksekusi.
    """
    def __init__(self, g_id: int, total_ticks: int):
        self.id = g_id
        self.total_ticks = total_ticks
        self.remaining_ticks = total_ticks
        self.state = GoroutineState.RUNNABLE
        self.assigned_p: Optional[int] = None

    def execute_slice(self, ticks: int) -> int:
        """Mengeksekusi kuantum waktu instruksi (ticks). Mengembalikan ticks yang terkonsumsi."""
        exec_ticks = min(self.remaining_ticks, ticks)
        self.remaining_ticks -= exec_ticks
        if self.remaining_ticks == 0:
            self.state = GoroutineState.DEAD
        return exec_ticks


class Processor:
    """
    Representasi struktur runtime.p di Go.
    Menyediakan konteks eksekusi berkapasitas LRQ (Local Run Queue).
    """
    def __init__(self, p_id: int, max_lrq_size: int = 8):
        self.id = p_id
        self.lrq: Deque[Goroutine] = collections.deque(maxlen=max_lrq_size)
        self.current_g: Optional[Goroutine] = None
        self.sched_ticks: int = 0
        self.lock = threading.Lock()

    def push_runnable(self, g: Goroutine) -> bool:
        """Memasukkan G ke LRQ lokal. Mengembalikan False jika LRQ penuh (overflow ke GRQ)."""
        with self.lock:
            if len(self.lrq) < self.lrq.maxlen:
                g.assigned_p = self.id
                g.state = GoroutineState.RUNNABLE
                self.lrq.append(g)
                return True
            return False

    def pop_runnable(self) -> Optional[Goroutine]:
        """Mengambil G terdepan dari LRQ."""
        with self.lock:
            if self.lrq:
                return self.lrq.popleft()
            return None

    def steal_half_from(self, target_p: "Processor") -> List[Goroutine]:
        """
        Algoritma Work-Stealing (runtime.stealWork):
        Mencuri separuh isi antrean dari LRQ milik P lain secara thread-safe.
        """
        stolen: List[Goroutine] = []
        with target_p.lock:
            total = len(target_p.lrq)
            if total > 0:
                count = (total + 1) // 2
                for _ in range(count):
                    g = target_p.lrq.popleft()
                    g.assigned_p = self.id
                    stolen.append(g)
        if stolen:
            with self.lock:
                for g in stolen:
                    self.lrq.append(g)
        return stolen


class Machine(threading.Thread):
    """
    Representasi struktur runtime.m di Go.
    OS Thread yang terikat dengan P untuk mengeksekusi G yang tersedia.
    """
    def __init__(self, m_id: int, sched_ref: "GoRuntimeScheduler"):
        super().__init__(daemon=True)
        self.id = m_id
        self.sched = sched_ref
        self.active_p: Optional[Processor] = None
        self.is_running = True
        self.completed_g_count = 0

    def run(self):
        while self.is_running:
            if not self.active_p:
                time.sleep(0.01)
                continue

            g = self.sched.schedule(self.active_p)
            if g:
                self.execute_g(g)
            else:
                # Polling backoff jika tidak ada pekerjaan yang dapat dijadwalkan
                time.sleep(0.005)

    def execute_g(self, g: Goroutine):
        """Menjalankan goroutine untuk durasi satu kuantum penjadwalan (preemptive quantum)."""
        self.active_p.current_g = g
        g.state = GoroutineState.RUNNING

        quantum = 3  # Kuantum penjadwalan simulated ticks
        consumed = g.execute_slice(quantum)
        time.sleep(0.02 * consumed)  # Simulasi konsumsi siklus CPU fisik

        if g.state == GoroutineState.DEAD:
            self.completed_g_count += 1
            self.sched.log_event(
                f"{CLR_GREEN}[DONE]{CLR_RESET} M{self.id}/P{self.active_p.id} selesai mengeksekusi "
                f"G{g.id} (total={g.total_ticks} ticks)"
            )
            self.active_p.current_g = None
        else:
            # Preemption: Kuantum habis, kembalikan ke LRQ jika masih ada sisa
            g.state = GoroutineState.RUNNABLE
            if not self.active_p.push_runnable(g):
                self.sched.push_grq(g)
            self.active_p.current_g = None


class GoRuntimeScheduler:
    """
    Kordinator Runtime Go: Mengelola GOMAXPROCS (daftar P), Worker (M), dan GRQ.
    Mengimplementasikan logika pemilihan antrean runtime.findrunnable().
    """
    def __init__(self, gomaxprocs: int):
        self.gomaxprocs = gomaxprocs
        self.processors: List[Processor] = [Processor(i, max_lrq_size=4) for i in range(gomaxprocs)]
        self.machines: List[Machine] = [Machine(i, self) for i in range(gomaxprocs)]
        self.grq: Deque[Goroutine] = collections.deque()
        self.grq_lock = threading.Lock()
        self.print_lock = threading.Lock()
        self.total_spawned = 0

        # Pasangkan M ke P (1:1 mapping dasar saat idle)
        for i in range(gomaxprocs):
            self.machines[i].active_p = self.processors[i]

    def log_event(self, message: str):
        with self.print_lock:
            timestamp = time.strftime("%H:%M:%S")
            print(f"{CLR_CYAN}[{timestamp}]{CLR_RESET} {message}")

    def push_grq(self, g: Goroutine):
        """Memasukkan Goroutine ke antrean global (GRQ)."""
        with self.grq_lock:
            g.assigned_p = None
            g.state = GoroutineState.RUNNABLE
            self.grq.append(g)

    def pop_grq(self) -> Optional[Goroutine]:
        """Mengambil satu Goroutine dari antrean global (GRQ)."""
        with self.grq_lock:
            if self.grq:
                return self.grq.popleft()
            return None

    def new_goroutine(self, total_ticks: int, target_p_id: Optional[int] = None) -> Goroutine:
        """Membuat instance G baru (simulasi `go func()`)."""
        self.total_spawned += 1
        g = Goroutine(self.total_spawned, total_ticks)

        target_p = None
        if target_p_id is not None and 0 <= target_p_id < self.gomaxprocs:
            target_p = self.processors[target_p_id]
        else:
            target_p = random.choice(self.processors)

        # Coba masukkan ke LRQ target P, overflow ke GRQ
        if not target_p.push_runnable(g):
            self.push_grq(g)
            self.log_event(f"{CLR_YELLOW}[OVERFLOW]{CLR_RESET} LRQ P{target_p.id} penuh. G{g.id} dialokasikan ke GRQ.")
        else:
            self.log_event(f"{CLR_BLUE}[SPAWN]{CLR_RESET} G{g.id} (work={total_ticks}t) dimasukkan ke LRQ P{target_p.id}")
        return g

    def schedule(self, p: Processor) -> Optional[Goroutine]:
        """
        Logika penjadwalan Go runtime.schedule():
        1. Setiap tick ke-61, ambil dari GRQ untuk mencegah starvation.
        2. Coba ambil dari LRQ lokal P.
        3. Jika LRQ kosong, coba ambil dari GRQ.
        4. Jika GRQ kosong, lakukan Work-Stealing dari P lain.
        """
        p.sched_ticks += 1

        # Aturan ke-61 tick: Prioritaskan Global Queue
        if p.sched_ticks % 6 == 0:  # Diturunkan ke 6 untuk demonstrasi lab yang dinamis
            g = self.pop_grq()
            if g:
                self.log_event(f"{CLR_MAGENTA}[FAIRNESS]{CLR_RESET} P{p.id} menarik G{g.id} langsung dari GRQ")
                return g

        # Ambil dari LRQ lokal
        g = p.pop_runnable()
        if g:
            return g

        # Coba ambil dari GRQ reguler
        g = self.pop_grq()
        if g:
            return g

        # Work-Stealing: Cari target P acak yang memiliki pekerjaan berlebih
        other_indices = [i for i in range(self.gomaxprocs) if i != p.id]
        random.shuffle(other_indices)

        for target_idx in other_indices:
            target_p = self.processors[target_idx]
            stolen_batch = p.steal_half_from(target_p)
            if stolen_batch:
                self.log_event(
                    f"{CLR_YELLOW}[STEAL]{CLR_RESET} P{p.id} mencuri {len(stolen_batch)} Goroutine dari LRQ P{target_p.id}!"
                )
                return p.pop_runnable()

        return None

    def start(self):
        for m in self.machines:
            m.start()

    def stop(self):
        for m in self.machines:
            m.is_running = False
        for m in self.machines:
            m.join()

    def print_runtime_telemetry(self):
        with self.print_lock:
            print("\n" + "=" * 65)
            print(f"{CLR_BOLD}--- TELEMETRI RUNTIME GO SCHEDULER (GOMAXPROCS={self.gomaxprocs}) ---{CLR_RESET}")
            with self.grq_lock:
                grq_ids = [f"G{g.id}" for g in self.grq]
                print(f"Global Run Queue (GRQ) [{len(self.grq)} item]: {grq_ids}")

            for p in self.processors:
                with p.lock:
                    lrq_ids = [f"G{g.id}({g.remaining_ticks}t)" for g in p.lrq]
                    curr = f"G{p.current_g.id}" if p.current_g else "None"
                    print(f"P{p.id} | Running: {curr:<8} | LRQ ({len(p.lrq)}/{p.lrq.maxlen}): {lrq_ids}")
            print("=" * 65 + "\n")


def main():
    print(f"{CLR_BOLD}{CLR_GREEN}=== LAB HANDS-ON: SIMULASI GO M:P:G SCHEDULER INTERNALS ==={CLR_RESET}\n")

    # Inisialisasi scheduler dengan GOMAXPROCS = 3
    GOMAXPROCS = 3
    sched = GoRuntimeScheduler(gomaxprocs=GOMAXPROCS)
    sched.start()

    try:
        # FASE 1: Beban terdistribusi normal
        print(f"{CLR_BOLD}>>> Skenario 1: Dispatch Beban Kerja Awal...{CLR_RESET}")
        for _ in range(6):
            sched.new_goroutine(total_ticks=random.randint(4, 8))
        sched.print_runtime_telemetry()
        time.sleep(0.4)

        # FASE 2: Load Imbalance Ekstrem (Menstimulasi Work-Stealing & Overflow)
        print(f"\n{CLR_BOLD}>>> Skenario 2: Load Imbalance (Semua G dipaksa masuk ke P0)...{CLR_RESET}")
        for _ in range(8):
            # Suntikkan beban masif khusus ke P0
            sched.new_goroutine(total_ticks=random.randint(6, 12), target_p_id=0)

        # Pantau proses work stealing dan pengosongan antrean secara berkala
        for step in range(5):
            time.sleep(0.25)
            sched.print_runtime_telemetry()

        # FASE 3: Penyelesaian Seluruh Antrean
        print(f"\n{CLR_BOLD}>>> Skenario 3: Menunggu Scheduler Menyelesaikan Sisa Task...{CLR_RESET}")
        active = True
        timeout = 5.0
        start_t = time.time()
        while active and (time.time() - start_t < timeout):
            with sched.grq_lock:
                grq_empty = len(sched.grq) == 0
            lrqs_empty = all(len(p.lrq) == 0 and p.current_g is None for p in sched.processors)
            if grq_empty and lrqs_empty:
                active = False
                break
            time.sleep(0.1)

        sched.print_runtime_telemetry()
        print(f"{CLR_GREEN}{CLR_BOLD}✔ Eksekusi Selesai Tanpa Deadlock.{CLR_RESET}")
        for m in sched.machines:
            print(f"  • M{m.id} memproses total: {m.completed_g_count} Goroutine.")

    finally:
        sched.stop()
        print(f"\n{CLR_CYAN}[CLEANUP] Thread runtime berhasil di-terminate secara aman.{CLR_RESET}")


if __name__ == "__main__":
    main()
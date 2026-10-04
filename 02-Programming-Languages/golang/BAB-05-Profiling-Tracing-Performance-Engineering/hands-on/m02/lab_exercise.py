#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Deep Dive - M:N Scheduler & CSP Channels
Topic: Golang (Bab 05 - Modul 02 Deep Dive)
Description:
    Simulasi komprehensif arsitektur internal runtime Go:
    1. Model Penjadwalan GMP (G: Goroutine, M: Machine/OS Thread, P: Logical Processor).
    2. Work-Stealing Algorithm (P mencuri setengah tugas dari LRQ P lain jika kosong).
    3. Global Run Queue (GRQ) check periodik (pencegahan starvation ala Go runtime).
    4. Channel CSP (Communicating Sequential Processes) dengan lock dan ring buffer.
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional, List, Dict, Any

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"


class GState(Enum):
    """Siklus hidup goroutine internal Go runtime."""
    GIDLE = auto()
    GRUNNABLE = auto()
    GRUNNING = auto()
    GWAITING = auto()
    GDEAD = auto()


@dataclass
class Goroutine:
    """Representasi 'G' (Goroutine) dalam runtime Go."""
    gid: int
    task_fn: Callable[..., Any]
    args: tuple = field(default_factory=tuple)
    state: GState = GState.GIDLE
    name: str = "anon_g"

    def execute(self):
        self.state = GState.GRUNNING
        try:
            return self.task_fn(*self.args)
        finally:
            self.state = GState.GDEAD


class GoChannel:
    """
    Simulasi 'hchan' (Go Channel) berbasis CSP primitif.
    Mendukung buffer ring, sender/receiver wait queues, dan lock concurrency.
    """
    def __init__(self, capacity: int = 0):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity if capacity > 0 else None)
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
        self.closed = False

    def send(self, val: Any, gid: int):
        with self.lock:
            if self.closed:
                raise RuntimeError(f"G{gid}: panic: send on closed channel")
            
            # Unbuffered channel: tunggu receiver
            if self.capacity == 0:
                while len(self.buffer) >= 1 and not self.closed:
                    self.not_full.wait()
                if self.closed:
                    raise RuntimeError(f"G{gid}: panic: send on closed channel")
                self.buffer.append(val)
                self.not_empty.notify()
                return

            # Buffered channel
            while len(self.buffer) >= self.capacity and not self.closed:
                self.not_full.wait()
            if self.closed:
                raise RuntimeError(f"G{gid}: panic: send on closed channel")
            self.buffer.append(val)
            self.not_empty.notify()

    def recv(self, gid: int) -> Optional[Any]:
        with self.lock:
            while len(self.buffer) == 0:
                if self.closed:
                    return None
                self.not_empty.wait()
            val = self.buffer.popleft()
            self.not_full.notify()
            return val

    def close(self):
        with self.lock:
            self.closed = True
            self.not_full.notify_all()
            self.not_empty.notify_all()


class Processor:
    """
    Representasi 'P' (Logical Processor) dalam model GMP.
    Memiliki Local Run Queue (LRQ) dan slot 'runnext' untuk fast-path.
    """
    def __init__(self, pid: int, max_lrq: int = 256):
        self.pid = pid
        self.max_lrq = max_lrq
        self.lrq: deque = deque()
        self.runnext: Optional[Goroutine] = None
        self.lock = threading.Lock()
        self.schedtick = 0
        self.stolen_count = 0

    def push(self, g: Goroutine) -> Optional[Goroutine]:
        """Menaruh Goroutine ke slot runnext atau LRQ. Jika LRQ penuh, kembalikan overflow ke GRQ."""
        with self.lock:
            g.state = GState.GRUNNABLE
            if self.runnext is None:
                self.runnext = g
                return None
            
            # Tukar dengan runnext (Go fast-path heuristic)
            old_next = self.runnext
            self.runnext = g

            if len(self.lrq) < self.max_lrq:
                self.lrq.append(old_next)
                return None
            else:
                # Overflow: kembalikan goroutine lama ke GRQ
                return old_next

    def pop(self) -> Optional[Goroutine]:
        """Ambil Goroutine dari slot runnext terlebih dahulu, lalu LRQ."""
        with self.lock:
            if self.runnext is not None:
                g = self.runnext
                self.runnext = None
                return g
            if self.lrq:
                return self.lrq.popleft()
            return None


class GMPScheduler:
    """
    Engine Runtime Go yang mengkoordinasikan M (OS Threads), P (Processors), dan G.
    Menerapkan Work-Stealing dan pencegahan starvation Global Run Queue.
    """
    def __init__(self, num_p: int = 4):
        self.num_p = num_p
        self.processors: List[Processor] = [Processor(i, max_lrq=8) for i in range(num_p)]
        self.grq: deque = deque()  # Global Run Queue
        self.grq_lock = threading.Lock()
        self.m_threads: List[threading.Thread] = []
        self.running = False
        self.gid_counter = 1
        self.stats = {"completed": 0, "steals": 0, "grq_runs": 0}
        self.stats_lock = threading.Lock()

    def go(self, task_fn: Callable, *args, name: str = "anon") -> int:
        """Ekivalen dengan sintaks 'go func()'."""
        with self.grq_lock:
            gid = self.gid_counter
            self.gid_counter += 1

        g = Goroutine(gid=gid, task_fn=task_fn, args=args, name=name)
        # Pilih P secara pseudo-random layaknya Go newproc
        p = self.processors[random.randint(0, self.num_p - 1)]
        overflow = p.push(g)

        if overflow:
            with self.grq_lock:
                self.grq.append(overflow)

        return gid

    def _find_runnable(self, p: Processor) -> Optional[Goroutine]:
        """
        Algoritma Inti Go Runtime: findrunnable()
        1. 1/61 tick: Periksa GRQ untuk keadilan eksekusi.
        2. Periksa LRQ lokal milik P.
        3. Periksa GRQ reguler.
        4. Work-Stealing: Curi 50% goroutine dari LRQ Processor lain.
        """
        p.schedtick += 1

        # Aturan 1/61 Go: Cegah starvation goroutine di GRQ
        if p.schedtick % 61 == 0:
            with self.grq_lock:
                if self.grq:
                    with self.stats_lock:
                        self.stats["grq_runs"] += 1
                    return self.grq.popleft()

        # Ambil dari lokal P
        g = p.pop()
        if g:
            return g

        # Coba GRQ reguler jika lokal kosong
        with self.grq_lock:
            if self.grq:
                with self.stats_lock:
                    self.stats["grq_runs"] += 1
                return self.grq.popleft()

        # Work-Stealing Algorithm
        other_ps = [other for other in self.processors if other.pid != p.pid]
        random.shuffle(other_ps)

        for victim in other_ps:
            with victim.lock:
                count = len(victim.lrq)
                if count > 0:
                    steal_n = max(1, count // 2)
                    stolen = [victim.lrq.popleft() for _ in range(steal_n)]
                    victim.stolen_count += steal_n
                    with self.stats_lock:
                        self.stats["steals"] += steal_n

                    print(f"{CLR_YELLOW}[Work-Steal]{CLR_RESET} P{p.pid} mencuri {steal_n} G dari P{victim.pid}")
                    # Ambil satu untuk langsung dijalankan, sisanya masukkan LRQ p
                    res = stolen.pop(0)
                    with p.lock:
                        p.lrq.extend(stolen)
                    return res

        return None

    def _m_worker(self, p: Processor):
        """Representasi M (OS Worker Thread) yang mengikat satu P."""
        while self.running:
            g = self._find_runnable(p)
            if g:
                print(f"{CLR_CYAN}[Execute]{CLR_RESET} M-Worker on P{p.pid} running G{g.gid} ({g.name})")
                g.execute()
                with self.stats_lock:
                    self.stats["completed"] += 1
            else:
                # Polling backoff layaknya mspinning sleep di Go
                time.sleep(0.01)

    def start(self):
        """Memulai runtime & spawning M threads terikat ke setiap P."""
        self.running = True
        for p in self.processors:
            t = threading.Thread(target=self._m_worker, args=(p,), daemon=True)
            self.m_threads.append(t)
            t.start()

    def stop(self):
        """Menghentikan runtime scheduler."""
        self.running = False
        for t in self.m_threads:
            t.join(timeout=1.0)


# =====================================================================
# SIMULASI SKENARIO PRAKTIK
# =====================================================================

def worker_task(job_id: int, ch_out: GoChannel):
    """Simulasi goroutine komputasi ringan yang mengirim output ke channel."""
    time.sleep(random.uniform(0.02, 0.05))
    result = job_id * 10
    ch_out.send(result, gid=job_id)


def consumer_task(num_jobs: int, ch_in: GoChannel):
    """Simulasi consumer goroutine yang membaca dari Go channel."""
    collected = 0
    while collected < num_jobs:
        val = ch_in.recv(gid=999)
        if val is not None:
            collected += 1
            print(f"  {CLR_GREEN}↳ [Channel Receive]{CLR_RESET} Diterima value: {val} (Total: {collected}/{num_jobs})")
        else:
            break


def heavy_batch(worker_id: int, load_size: int):
    """Simulasi batch goroutine untuk memicu antrian penuh dan work-stealing."""
    accum = 0
    for _ in range(load_size):
        accum += sum(x * x for x in range(200))
    time.sleep(0.01)


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}============================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}  GO RUNTIME DEEP DIVE: GMP SCHEDULER & CSP CHANNELS LAB    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}============================================================{CLR_RESET}\n")

    # Inisialisasi runtime scheduler dengan GOMAXPROCS = 3
    gomaxprocs = 3
    print(f"{CLR_BLUE}[Init]{CLR_RESET} Menginisialisasi Go Runtime Engine dengan GOMAXPROCS = {gomaxprocs}")
    scheduler = GMPScheduler(num_p=gomaxprocs)
    scheduler.start()

    # Skenario 1: CSP Communication via GoChannel (Buffered)
    print(f"\n{CLR_BOLD}--- SKENARIO 1: Concurrency CSP via Go Channel ---{CLR_RESET}")
    data_chan = GoChannel(capacity=4)
    total_jobs = 6

    # Spawn 1 Consumer Goroutine
    scheduler.go(consumer_task, total_jobs, data_chan, name="Consumer-G")

    # Spawn multiple Producer Goroutines
    for i in range(1, total_jobs + 1):
        scheduler.go(worker_task, i, data_chan, name=f"Producer-{i}")

    # Beri waktu menyelesaikan pertukaran channel
    time.sleep(0.4)
    data_chan.close()

    # Skenario 2: Memicu Work-Stealing Algorithm
    # Memasukkan puluhan goroutine cepat ke antrean untuk memicu ketidakseimbangan LRQ
    print(f"\n{CLR_BOLD}--- SKENARIO 2: Work-Stealing & Starvation Prevention ---{CLR_RESET}")
    print("Memasukkan 20 Goroutine batch sekaligus ke salah satu Processor...")

    for i in range(20):
        scheduler.go(heavy_batch, i, 5, name=f"BatchLoad-{i}")

    # Biarkan scheduler mengosongkan antrean dan mencuri tugas antar P
    time.sleep(0.8)

    # Menghentikan Scheduler
    scheduler.stop()

    # Statistik Eksekusi Scheduler
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}============================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}                 SCHEDULER TELEMETRY REPORT                 {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}============================================================{CLR_RESET}")
    print(f"Total Goroutines Sukses Selesai : {CLR_GREEN}{scheduler.stats['completed']}{CLR_RESET}")
    print(f"Total Work-Steal Events Dispatched : {CLR_YELLOW}{scheduler.stats['steals']}{CLR_RESET}")
    print(f"Pengecekan GRQ (Pencegahan Starve): {CLR_CYAN}{scheduler.stats['grq_runs']}{CLR_RESET}")

    for p in scheduler.processors:
        print(f"  P{p.pid} -> Sisa LRQ: {len(p.lrq)} | Total Dicuri Pihak Lain: {p.stolen_count} | SchedTick: {p.schedtick}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}[SUKSES]{CLR_RESET} Simulasi Go Runtime Internal berhasil diselesaikan secara presisi.\n")


if __name__ == "__main__":
    main()
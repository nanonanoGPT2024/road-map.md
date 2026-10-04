#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Internal Deep Dive (Bab 09 - Modul 02)
Simulasi Komprehensif: Arsitektur Go Runtime GMP (Goroutine, Machine, Processor)
dengan Work-Stealing Scheduler, Local/Global Run Queues, dan Syscall Handoff.
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

# --- ANSI Formatting Constants ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAG    = "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_BG_BLK = "\033[40m"


class GState(Enum):
    IDLE = auto()
    RUNNABLE = auto()
    RUNNING = auto()
    SYSCALL = auto()
    DEAD = auto()


@dataclass
class Goroutine:
    """Representasi G (Goroutine): Unit eksekusi logis dengan lightweight stack."""
    gid: int
    work_units: int
    is_syscall: bool = False
    state: GState = GState.IDLE
    spawned_at: float = field(default_factory=time.time)


class Processor:
    """
    Representasi P (Processor): Resource logis yang dibutuhkan M untuk mengeksekusi G.
    Mengelola Local Run Queue (LRQ) berkapasitas terbatas dan slot runnext.
    """
    LRQ_CAPACITY = 4

    def __init__(self, pid: int):
        self.pid = pid
        self.runnext: Optional[Goroutine] = None
        self.runq: deque[Goroutine] = deque()
        self.lock = threading.Lock()
        self.sched_ticks = 0

    def push(self, g: Goroutine, global_q: deque, sched_lock: threading.Lock) -> None:
        """Enqueue G ke runnext/LRQ. Jika overflow, offload setengah antrean ke GRQ."""
        with self.lock:
            g.state = GState.RUNNABLE
            if self.runnext is None:
                self.runnext = g
                return

            if len(self.runq) < self.LRQ_CAPACITY:
                self.runq.append(g)
            else:
                # LRQ Penuh: Offload separuh LRQ + G ke Global Run Queue (GRQ)
                with sched_lock:
                    num_to_offload = len(self.runq) // 2
                    for _ in range(num_to_offload):
                        global_q.append(self.runq.popleft())
                    global_q.append(g)


class Machine:
    """
    Representasi M (Machine): OS Thread aktual yang mengeksekusi instruksi.
    M mengikat sebuah P untuk mengeksekusi G melalui algoritma schedule().
    """
    def __init__(self, mid: int, runtime: "GoRuntime"):
        self.mid = mid
        self.runtime = runtime
        self.p: Optional[Processor] = None
        self.running = True
        self.thread: Optional[threading.Thread] = None

    def start(self):
        self.thread = threading.Thread(target=self._m_loop, name=f"M-{self.mid}", daemon=True)
        self.thread.start()

    def _m_loop(self):
        """Main execution engine loop untuk OS Thread M."""
        while self.running and self.runtime.active:
            if not self.p:
                # Mencoba mengakuisisi P idle
                self.p = self.runtime.acquire_idle_p()
                if not self.p:
                    time.sleep(0.01)
                    continue

            # Temukan goroutine runnable menggunakan Go scheduler search pattern
            g = self.schedule()
            if g:
                self.execute(g)
            else:
                # Tidak ada kerjaan: rilis P dan parkir
                self.runtime.release_p_to_idle(self.p)
                self.p = None
                time.sleep(0.02)

    def schedule(self) -> Optional[Goroutine]:
        """
        Algoritma Penjadwalan Go:
        1. Setiap 61 tick, cek GRQ untuk mencegah kelaparan (starvation).
        2. Periksa runnext lokal.
        3. Periksa Local Run Queue (LRQ).
        4. Cek Global Run Queue (GRQ).
        5. Lakukan Work-Stealing dari P lain (curi 50% antrean).
        """
        if not self.p:
            return None

        p = self.p
        p.sched_ticks += 1

        # Rule 1: Cek GRQ periodik
        if p.sched_ticks % 61 == 0:
            with self.runtime.sched_lock:
                if self.runtime.global_runq:
                    return self.runtime.global_runq.popleft()

        # Rule 2: Prioritaskan runnext (eksploitasi cache locality)
        with p.lock:
            if p.runnext:
                g = p.runnext
                p.runnext = None
                return g

        # Rule 3: Ambil dari LRQ
        with p.lock:
            if p.runq:
                return p.runq.popleft()

        # Rule 4: Ambil dari GRQ
        with self.runtime.sched_lock:
            if self.runtime.global_runq:
                return self.runtime.global_runq.popleft()

        # Rule 5: Work-Stealing dari P target secara acak
        stolen = self.runtime.steal_work(p.pid)
        if stolen:
            return stolen

        return None

    def execute(self, g: Goroutine):
        """Simulasi eksekusi payload G dan penanganan Syscall Preemption."""
        g.state = GState.RUNNING
        
        if g.is_syscall:
            # Simulasi Syscall: M melepaskan P agar P dapat diasosiasikan dengan M lain
            self.runtime.log(f"{CLR_RED}[SYSCALL]{CLR_RESET} G{g.gid} memicu blocking syscall pada M{self.mid}. Handoff P{self.p.pid}.")
            held_p = self.p
            self.p = None
            g.state = GState.SYSCALL
            self.runtime.handoff_p(held_p)

            # Eksekusi blocking I/O di thread M saat ini
            time.sleep(g.work_units * 0.05)
            
            g.state = GState.DEAD
            self.runtime.record_completion(g)
            self.runtime.log(f"{CLR_GREEN}[SYS-RET]{CLR_RESET} G{g.gid} selesai syscall. M{self.mid} mencari P baru.")
        else:
            # Cooperative/Preemptive time slicing execution
            self.runtime.log(f"{CLR_CYAN}[EXEC]   {CLR_RESET} M{self.mid} mengeksekusi G{g.gid} via P{self.p.pid} (Beban: {g.work_units})")
            time.sleep(g.work_units * 0.02)
            g.state = GState.DEAD
            self.runtime.record_completion(g)


class GoRuntime:
    """
    Sub-sistem Orkestrator Go Runtime:
    Mengelola daftar M, P, Global Queue, Sysmon, dan mekanisme Work Stealing.
    """
    def __init__(self, gomaxprocs: int):
        self.gomaxprocs = gomaxprocs
        self.processors: List[Processor] = [Processor(i) for i in range(gomaxprocs)]
        self.idle_processors: List[Processor] = []
        self.machines: List[Machine] = []
        self.global_runq: deque[Goroutine] = deque()
        self.sched_lock = threading.Lock()
        self.active = True
        self.completed_count = 0
        self.steals_count = 0
        self.next_gid = 1

    def boot(self):
        """Inisialisasi pool P dan spawn initial Machine (M) threads."""
        self.idle_processors = list(self.processors)
        for i in range(self.gomaxprocs):
            m = Machine(mid=i, runtime=self)
            self.machines.append(m)
            m.start()

    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        sys.stdout.write(f"[{timestamp}] {message}\n")
        sys.stdout.flush()

    def acquire_idle_p(self) -> Optional[Processor]:
        with self.sched_lock:
            if self.idle_processors:
                return self.idle_processors.pop(0)
        return None

    def release_p_to_idle(self, p: Processor):
        with self.sched_lock:
            if p not in self.idle_processors:
                self.idle_processors.append(p)

    def handoff_p(self, p: Processor):
        """Handoff: Memastikan Processor yang ditinggalkan syscall segera diambil M lain."""
        with self.sched_lock:
            # Cari M tanpa P, atau spawn M baru jika semua M sedang busy
            unbound_m = next((m for m in self.machines if m.p is None), None)
            if unbound_m:
                unbound_m.p = p
            else:
                new_mid = len(self.machines)
                new_m = Machine(mid=new_mid, runtime=self)
                new_m.p = p
                self.machines.append(new_m)
                new_m.start()
                self.log(f"{CLR_MAG}[HANDOFF]{CLR_RESET} Spawn OS Thread M{new_mid} untuk mengadopsi P{p.pid}")

    def steal_work(self, thief_pid: int) -> Optional[Goroutine]:
        """Algoritma Work-Stealing: Mencuri 50% goroutine dari antrean korban acak."""
        victims = [p for p in self.processors if p.pid != thief_pid]
        random.shuffle(victims)

        for victim in victims:
            with victim.lock:
                victim_len = len(victim.runq)
                if victim_len > 0:
                    steal_count = max(1, victim_len // 2)
                    stolen_g = victim.runq.popleft()
                    
                    # Ambil sisa porsi curian ke LRQ pencuri
                    thief_p = self.processors[thief_pid]
                    with thief_p.lock:
                        for _ in range(steal_count - 1):
                            if victim.runq:
                                thief_p.runq.append(victim.runq.popleft())

                    with self.sched_lock:
                        self.steals_count += 1

                    self.log(f"{CLR_YELLOW}[STEAL]  {CLR_RESET} P{thief_pid} mencuri {steal_count} Goroutine dari P{victim.pid}")
                    return stolen_g
        return None

    def spawn_goroutine(self, work_units: int, is_syscall: bool = False):
        """Simulasi instruksi `go func()`: Membuat G baru dan mapping ke P."""
        with self.sched_lock:
            gid = self.next_gid
            self.next_gid += 1

        g = Goroutine(gid=gid, work_units=work_units, is_syscall=is_syscall)
        # Tunjuk P target (biasanya P lokal thread saat ini, disimulasikan round-robin/random)
        target_p = random.choice(self.processors)
        target_p.push(g, self.global_runq, self.sched_lock)

    def record_completion(self, g: Goroutine):
        with self.sched_lock:
            self.completed_count += 1

    def shutdown(self):
        self.active = False
        for m in self.machines:
            m.running = False


def main():
    print(f"{CLR_BOLD}{CLR_BG_BLK}{CLR_CYAN}=== SIMULASI GO RUNTIME: GMP WORK-STEALING SCHEDULER ==={CLR_RESET}")
    GOMAXPROCS = 3
    TOTAL_GOROUTINES = 14

    runtime = GoRuntime(gomaxprocs=GOMAXPROCS)
    runtime.boot()
    runtime.log(f"{CLR_BOLD}Go Runtime diinisialisasi: GOMAXPROCS={GOMAXPROCS}{CLR_RESET}\n")

    # Injeksi Goroutine dengan variasi beban komputasi dan blocking I/O (Syscall)
    workload = [
        (2, False), (3, False), (4, True),  (1, False),
        (5, False), (2, True),  (2, False), (3, False),
        (6, False), (1, False), (4, False), (2, False),
        (3, True),  (1, False)
    ]

    for units, syscall in workload:
        runtime.spawn_goroutine(work_units=units, is_syscall=syscall)
        time.sleep(0.01)

    # Monitor loop
    start_time = time.time()
    try:
        while True:
            time.sleep(0.2)
            with runtime.sched_lock:
                done = runtime.completed_count
                total_grq = len(runtime.global_runq)
            
            p_status = " | ".join([f"P{p.pid}: LRQ={len(p.runq)}" for p in runtime.processors])
            runtime.log(f"{CLR_MAG}[MONITOR]{CLR_RESET} Selesai: {done}/{TOTAL_GOROUTINES} | GRQ: {total_grq} | {p_status}")

            if done >= TOTAL_GOROUTINES:
                break
    finally:
        runtime.shutdown()

    elapsed = time.time() - start_time
    print(f"\n{CLR_BOLD}{CLR_GREEN}=== RUNTIME METRICS BENCHMARK ==={CLR_RESET}")
    print(f"Total Goroutine Dieksekusi : {CLR_BOLD}{runtime.completed_count}{CLR_RESET}")
    print(f"Total Work-Stealing Events : {CLR_YELLOW}{runtime.steals_count}{CLR_RESET}")
    print(f"Total OS Threads Tercipta  : {CLR_CYAN}{len(runtime.machines)}{CLR_RESET} (Termasuk Handoff M)")
    print(f"Total Waktu Penjadwalan    : {CLR_BOLD}{elapsed:.3f} detik{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}Status: Simulasi GMP Scheduler Berhasil Sempurna.{CLR_RESET}")


if __name__ == "__main__":
    main()
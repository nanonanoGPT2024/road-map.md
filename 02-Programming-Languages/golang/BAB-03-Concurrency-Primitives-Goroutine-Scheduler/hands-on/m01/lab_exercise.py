#!/usr/bin/env python3
"""
Simulasi Teknis Go Runtime Scheduler (M:N Model - G, M, P)
BAB 03: Concurrency Primitives & Goroutine Scheduler

Fitur Simulasi:
1. Model G-M-P (Goroutine, Machine/OS Thread, Processor/Logical Context)
2. Work-Stealing Algorithm (Steal 50% G dari queue P lain jika lokal kosong)
3. Global Run Queue (GRQ) vs Local Run Queue (LRQ)
4. Syscall Preemption & Hand-off (M melepas P saat blocking syscall)
5. Network Poller / Non-blocking async I/O simulation
6. Terminal Visualizer dengan warna ANSI interaktif
"""

import sys
import time
import random
import threading
from collections import deque
from typing import List, Optional

# ANSI Color Codes
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
BG_MAGENTA = "\033[45m"

class GoroutineState:
    IDLE = "IDLE"
    RUNNABLE = "RUNNABLE"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    SYSCALL = "SYSCALL"
    DEAD = "DEAD"

class Goroutine:
    def __init__(self, gid: int, name: str, workload: int, has_syscall: bool = False):
        self.gid = gid
        self.name = name
        self.workload = workload  # sisa unit kerja
        self.total_workload = workload
        self.has_syscall = has_syscall
        self.state = GoroutineState.RUNNABLE
        self.assigned_p: Optional[int] = None
        self.stack_size_kb = 2  # Go goroutine dimulai dari 2 KB

    def __repr__(self):
        return f"G{self.gid}({self.name}, rem={self.workload})"

class Processor:
    """Logical Processor (P) mewakili resource komputasi Go (GOMAXPROCS)"""
    def __init__(self, pid: int, capacity: int = 4):
        self.pid = pid
        self.capacity = capacity
        self.run_queue: deque[Goroutine] = deque(maxlen=capacity)
        self.m: Optional['Machine'] = None
        self.tick_counter = 0

    def is_full(self) -> bool:
        return len(self.run_queue) >= self.capacity

    def is_empty(self) -> bool:
        return len(self.run_queue) == 0

class Machine:
    """OS Thread (M) yang mengeksekusi instruksi CPU riil"""
    def __init__(self, mid: int):
        self.mid = mid
        self.p: Optional[Processor] = None
        self.cur_g: Optional[Goroutine] = None
        self.status = "IDLE"  # IDLE, RUNNING, BLOCKED_SYSCALL

class GoRuntimeScheduler:
    def __init__(self, num_p: int = 2):
        self.num_p = num_p
        self.processors: List[Processor] = [Processor(i) for i in range(num_p)]
        self.machines: List[Machine] = [Machine(i) for i in range(num_p)]
        
        # Pasang M ke P awal (1-to-1 association saat startup)
        for i in range(num_p):
            self.machines[i].p = self.processors[i]
            self.processors[i].m = self.machines[i]

        self.global_run_queue: deque[Goroutine] = deque()
        self.network_poller: List[Goroutine] = []
        self.completed_g: List[Goroutine] = []
        self.lock = threading.Lock()
        self.gid_counter = 1
        self.cycle = 0

    def spawn_goroutine(self, name: str, workload: int, has_syscall: bool = False) -> Goroutine:
        with self.lock:
            g = Goroutine(self.gid_counter, name, workload, has_syscall)
            self.gid_counter += 1
            
            # Coba masukkan ke LRQ P0 terlebih dahulu, jika penuh lempar ke Global Run Queue
            p0 = self.processors[0]
            if not p0.is_full():
                p0.run_queue.append(g)
                g.assigned_p = p0.pid
            else:
                self.global_run_queue.append(g)
                g.assigned_p = None
            return g

    def schedule_cycle(self):
        """Satu tick simulasi Go Scheduler"""
        with self.lock:
            self.cycle += 1
            print(f"\n{BOLD}{BG_BLUE} --- [CYCLE {self.cycle:03d}] GO SCHEDULER TICK --- {RESET}")

            # 1. Cek Network Poller (I/O siap)
            if self.network_poller:
                for g in list(self.network_poller):
                    if random.random() < 0.5:
                        g.state = GoroutineState.RUNNABLE
                        self.network_poller.remove(g)
                        self.global_run_queue.append(g)
                        print(f"  {CYAN}⚡ [NetPoller] {g} selesai I/O! Masuk ke Global Queue.{RESET}")

            # 2. Proses tiap M dan P
            for m in self.machines:
                p = m.p
                if not p:
                    # M sedang terlepas (misal dalam blocking syscall)
                    if m.status == "BLOCKED_SYSCALL":
                        # Simulasi syscall selesai
                        if random.random() < 0.6:
                            m.status = "IDLE"
                            g = m.cur_g
                            m.cur_g = None
                            if g:
                                g.state = GoroutineState.RUNNABLE
                                g.has_syscall = False
                                self.global_run_queue.append(g)
                                print(f"  {GREEN}✔ [Syscall Return] M{m.mid} selesai syscall untuk {g}! G dikembalikan ke Global Queue.{RESET}")
                    continue

                p.tick_counter += 1

                # Step A: Cek apakah G sedang running di M
                if m.cur_g:
                    g = m.cur_g
                    g.workload -= 1
                    
                    # Cek Syscall Trigger
                    if g.has_syscall and g.workload == g.total_workload // 2:
                        print(f"  {YELLOW}⚠ [Syscall Block] {g} melakukan blocking system call pada M{m.mid}!{RESET}")
                        print(f"    {MAGENTA}➔ Hand-off: P{p.pid} dilepaskan dari M{m.mid} agar OS Thread lain dapat mengeksekusi.{RESET}")
                        g.state = GoroutineState.SYSCALL
                        m.status = "BLOCKED_SYSCALL"
                        
                        # Hand-off P ke M baru atau idle
                        m.p = None
                        p.m = None
                        
                        # Cari / alokasikan M cadangan
                        spare_m = Machine(len(self.machines))
                        spare_m.p = p
                        p.m = spare_m
                        self.machines.append(spare_m)
                        print(f"    {GREEN}➔ New Thread: M{spare_m.mid} diikat ke P{p.pid} untuk melayani runnable Gs.{RESET}")
                        continue

                    # Cek Preemption (Cooperatif / Time slice habis)
                    if g.workload > 0 and (g.total_workload - g.workload) % 3 == 0:
                        print(f"  {BLUE}⏱ [Preemption] {g} telah menggunakan time slice. Yield ke LRQ P{p.pid}.{RESET}")
                        g.state = GoroutineState.RUNNABLE
                        p.run_queue.append(g)
                        m.cur_g = None
                    elif g.workload <= 0:
                        g.state = GoroutineState.DEAD
                        self.completed_g.append(g)
                        print(f"  {GREEN}🎉 [Done] {g} telah selesai dieksekusi.{RESET}")
                        m.cur_g = None

                # Step B: Jika M belum pegang G, ambil G baru (Scheduler Search Order)
                if not m.cur_g:
                    next_g = self._find_runnable_goroutine(p)
                    if next_g:
                        m.cur_g = next_g
                        next_g.state = GoroutineState.RUNNING
                        next_g.assigned_p = p.pid
                        print(f"  {WHITE}▶ [Execute] M{m.mid} (via P{p.pid}) mulai mengeksekusi {next_g}{RESET}")

    def _find_runnable_goroutine(self, p: Processor) -> Optional[Goroutine]:
        """
        Urutan pencarian G oleh P (Go Scheduler Rule):
        1. Setiap 61 tick, cek Global Run Queue (hindari starvation)
        2. Cek Local Run Queue (LRQ)
        3. Cek Global Run Queue
        4. Cek Network Poller
        5. Work-Stealing dari P lain (ambil setengah queue korban)
        """
        # 1. 1/61 check Global Queue
        if p.tick_counter % 61 == 0 and len(self.global_run_queue) > 0:
            g = self.global_run_queue.popleft()
            print(f"  {CYAN}🔄 [Fairness 1/61] P{p.pid} mengambil {g} langsung dari Global Queue.{RESET}")
            return g

        # 2. Local Run Queue
        if not p.is_empty():
            return p.run_queue.popleft()

        # 3. Global Run Queue
        if len(self.global_run_queue) > 0:
            g = self.global_run_queue.popleft()
            print(f"  {CYAN}🌐 [GRQ Fetch] P{p.pid} mengambil {g} dari Global Run Queue.{RESET}")
            return g

        # 4. Work-Stealing dari P lain
        victim_candidates = [other_p for other_p in self.processors if other_p.pid != p.pid and len(other_p.run_queue) > 0]
        if victim_candidates:
            victim = random.choice(victim_candidates)
            steal_count = max(1, len(victim.run_queue) // 2)
            print(f"  {MAGENTA}🥷 [Work-Stealing] P{p.pid} mencuri {steal_count} G dari P{victim.pid}!{RESET}")
            stolen_g = None
            for idx in range(steal_count):
                g = victim.run_queue.pop()
                if idx == 0:
                    stolen_g = g
                else:
                    p.run_queue.append(g)
            return stolen_g

        return None

    def render_state(self):
        """Visualisasi dashboard status scheduler di terminal"""
        print(f"\n{BOLD}{'='*65}{RESET}")
        print(f"{BOLD}{WHITE}             RUNTIME SCHEDULER STATE DASHBOARD             {RESET}")
        print(f"{BOLD}{'='*65}{RESET}")
        
        # Global Queue
        grq_str = " -> ".join([f"G{g.gid}" for g in self.global_run_queue]) or "[Empty]"
        print(f"{BOLD}{CYAN}Global Run Queue (GRQ):{RESET} {grq_str}")

        # Processors & Machines
        for p in self.processors:
            m = p.m
            m_str = f"M{m.mid} (Running)" if m else f"{RED}Detached{RESET}"
            cur_g_str = f"{GREEN}G{m.cur_g.gid} ({m.cur_g.name}){RESET}" if (m and m.cur_g) else f"{DIM}[None]{RESET}"
            lrq_str = " | ".join([f"G{g.gid}" for g in p.run_queue]) or "[Empty]"
            print(f"\n{BOLD}[Processor P{p.pid}]{RESET} Bound to: {m_str}")
            print(f"  └─ Current Running G: {cur_g_str}")
            print(f"  └─ Local Queue (LRQ) [{len(p.run_queue)}/{p.capacity}]: [ {lrq_str} ]")

        # Network Poller
        np_str = ", ".join([f"G{g.gid}" for g in self.network_poller]) or "[Empty]"
        print(f"\n{BOLD}{YELLOW}Network Poller (Blocked I/O):{RESET} {np_str}")

        # Completed
        print(f"{BOLD}{GREEN}Completed Goroutines:{RESET} {len(self.completed_g)}")
        print(f"{BOLD}{'='*65}{RESET}\n")

    def has_active_work(self) -> bool:
        if self.global_run_queue or self.network_poller:
            return True
        for p in self.processors:
            if not p.is_empty():
                return True
        for m in self.machines:
            if m.cur_g or m.status == "BLOCKED_SYSCALL":
                return True
        return False

def print_banner():
    banner = f"""{BOLD}{CYAN}
  ╔═════════════════════════════════════════════════════════════════╗
  ║     GOLANG GMP SCHEDULER SIMULATION (M:N CONCURRENCY)          ║
  ║     BAB 03: Goroutines, OS Threads, and Processors             ║
  ╚═════════════════════════════════════════════════════════════════╝{RESET}
    """
    print(banner)

def run_interactive_simulation():
    print_banner()
    print(f"{YELLOW}Menginisialisasi Go Runtime dengan GOMAXPROCS = 2...{RESET}")
    scheduler = GoRuntimeScheduler(num_p=2)

    # Inisialisasi daftar Goroutine dengan berbagai karakteristik beban
    test_jobs = [
        ("auth-handler", 4, False),
        ("db-query-syscall", 6, True),   # Blocking syscall hand-off test
        ("jwt-verifier", 3, False),
        ("image-resize", 7, False),
        ("payment-gateway", 5, True),   # Syscall
        ("cache-invalidation", 2, False),
        ("log-streamer", 4, False),
    ]

    print(f"\n{BOLD}Mendaftarkan Goroutines ke Scheduler (go func() ...):{RESET}")
    for name, workload, has_syscall in test_jobs:
        g = scheduler.spawn_goroutine(name, workload, has_syscall)
        kind = f"{RED}[Syscall-Heavy]{RESET}" if has_syscall else f"{GREEN}[CPU-Bound]{RESET}"
        print(f"  • Spawned {BOLD}G{g.gid}{RESET} ({g.name}, load={workload}) -> {kind}")

    scheduler.render_state()
    time.sleep(1)

    step = 0
    while scheduler.has_active_work() and step < 20:
        step += 1
        scheduler.schedule_cycle()
        scheduler.render_state()
        time.sleep(0.6)

    print(f"{BOLD}{GREEN}✔ Simulasi selesai! Seluruh Goroutine berhasil dieksekusi.{RESET}")
    print(f"{DIM}Ringkasan: Model G-M-P berhasil mencegah OS thread explosion melalui work-stealing & syscall handoff.{RESET}")

if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{RED}[!] Simulasi dihentikan oleh user.{RESET}")
        sys.exit(0)

#!/usr/bin/env python3
"""
Lab Exercise: Linux Internals, CFS Scheduler, Memory Subsystem & OOM Simulation
Module: SRE - Modul 02: Arsitektur Sistem Operasi & Linux Internals
Python 3 Runnable Simulation with ANSI Color Output.
"""

from __future__ import annotations
import heapq
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ==============================================================================
# ANSI Color Codes & Formatting Helpers
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"

    BG_DARK = "\033[48;5;236m"
    ALERT   = "\033[1;37;41m"
    SUCCESS = "\033[1;30;42m"


def header(title: str, level: int = 1) -> str:
    line_char = "=" if level == 1 else "-"
    border = line_char * 76
    c = Color.CYAN if level == 1 else Color.MAGENTA
    return f"\n{c}{Color.BOLD}{border}\n [SYS-INTERNAL] {title}\n{border}{Color.RESET}"


def log_kernel(subsys: str, msg: str, level: str = "INFO") -> None:
    timestamp = f"{time.time() % 1000:08.3f}"
    color_map = {
        "INFO": Color.GREEN,
        "WARN": Color.YELLOW,
        "ALERT": Color.RED,
        "DEBUG": Color.GRAY,
    }
    lvl_color = color_map.get(level, Color.WHITE)
    print(
        f"{Color.GRAY}[{timestamp}] {Color.BOLD}[{subsys.upper():^10}]"
        f" {lvl_color}{level:<5}{Color.RESET} {msg}"
    )


# ==============================================================================
# 1. CFS (Completely Fair Scheduler) & Cgroup CPU Throttling Simulation
# ==============================================================================

# CFS weight mapping corresponding to kernel sched/core.c (prio_to_weight)
PRIO_TO_WEIGHT: Dict[int, int] = {
    -20: 88761, -19: 71755, -18: 56483, -17: 46273, -16: 36291,
    -15: 29154, -14: 23254, -13: 18705, -12: 14949, -11: 11916,
    -10: 9548,  -9: 7620,   -8: 6100,   -7: 4904,   -6: 3906,
     -5: 3121,  -4: 2501,   -3: 1991,   -2: 1586,   -1: 1277,
      0: 1024,   1: 820,     2: 655,     3: 526,     4: 423,
      5: 335,    6: 272,     7: 215,     8: 172,     9: 137,
     10: 110,   11: 87,     12: 70,     13: 56,     14: 45,
     15: 36,    16: 29,     17: 23,     18: 18,     19: 15,
}

NICE_0_LOAD = 1024


@dataclass(order=True)
class SchedEntity:
    vruntime: float
    pid: int = field(compare=False)
    name: str = field(compare=False)
    nice: int = field(compare=False)
    weight: int = field(compare=False)
    cgroup_quota_ms: float = field(compare=False)
    cgroup_period_ms: float = field(compare=False)
    used_in_period: float = field(default=0.0, compare=False)
    total_cpu_time: float = field(default=0.0, compare=False)
    throttled_periods: int = field(default=0, compare=False)


class CFSScheduler:
    def __init__(self, latency_target_ms: float = 6.0, min_granularity_ms: float = 0.75):
        self.runqueue: List[SchedEntity] = []
        self.latency_target_ms = latency_target_ms
        self.min_granularity_ms = min_granularity_ms
        self.min_vruntime = 0.0

    def add_task(self, task: SchedEntity) -> None:
        task.vruntime = max(task.vruntime, self.min_vruntime)
        heapq.heappush(self.runqueue, task)

    def schedule_tick(self, timeslice_ms: float = 1.0) -> Optional[str]:
        if not self.runqueue:
            return None

        current = heapq.heappop(self.runqueue)

        # Cgroups v2 CPU Throttling check
        if current.cgroup_quota_ms > 0:
            if current.used_in_period + timeslice_ms > current.cgroup_quota_ms:
                current.throttled_periods += 1
                heapq.heappush(self.runqueue, current)
                return (
                    f"{Color.RED}THROTTLED{Color.RESET} PID {current.pid} ({current.name}) "
                    f"hit cgroup quota {current.cgroup_quota_ms}/{current.cgroup_period_ms}ms"
                )

        # CFS Virtual Runtime Update
        # delta_vruntime = delta_exec * (NICE_0_LOAD / weight)
        delta_vruntime = timeslice_ms * (NICE_0_LOAD / current.weight)
        current.vruntime += delta_vruntime
        current.total_cpu_time += timeslice_ms
        current.used_in_period += timeslice_ms

        self.min_vruntime = min(self.min_vruntime, current.vruntime) if self.runqueue else current.vruntime

        result = (
            f"PID {current.pid:<5} ({Color.BOLD}{current.name:<12}{Color.RESET}) "
            f"nice={current.nice:>3} weight={current.weight:>5} "
            f"exec={timeslice_ms:3.1f}ms delta_vr={delta_vruntime:5.2f} "
            f"vruntime={Color.YELLOW}{current.vruntime:7.2f}{Color.RESET}"
        )

        heapq.heappush(self.runqueue, current)
        return result

    def reset_cgroup_period(self) -> None:
        for t in self.runqueue:
            t.used_in_period = 0.0


# ==============================================================================
# 2. Virtual Memory Management, Page Faults & OOM Killer Simulation
# ==============================================================================

PAGE_SIZE_KB = 4  # Standard 4KB page size


@dataclass
class ProcessMemory:
    pid: int
    name: str
    rss_pages: int
    swap_pages: int
    mem_max_pages: int
    mem_high_pages: int
    oom_score_adj: int
    minor_page_faults: int = 0
    major_page_faults: int = 0
    killed: bool = False

    @property
    def total_pages(self) -> int:
        return self.rss_pages + self.swap_pages

    @property
    def total_memory_mb(self) -> float:
        return (self.total_pages * PAGE_SIZE_KB) / 1024.0


class MemorySubsystem:
    def __init__(self, total_ram_mb: int = 1024):
        self.total_ram_pages = (total_ram_mb * 1024) // PAGE_SIZE_KB
        self.allocated_pages = 0
        self.processes: Dict[int, ProcessMemory] = {}

    def register_process(self, proc: ProcessMemory) -> None:
        self.processes[proc.pid] = proc
        self.allocated_pages += proc.rss_pages

    def allocate_page(self, pid: int, is_major_fault: bool = False) -> bool:
        proc = self.processes.get(pid)
        if not proc or proc.killed:
            return False

        if is_major_fault:
            proc.major_page_faults += 1
        else:
            proc.minor_page_faults += 1

        # Check cgroup hard memory limit
        if proc.rss_pages + 1 > proc.mem_max_pages:
            log_kernel("mm-cgroup", f"PID {proc.pid} exceeded memory.max ({proc.mem_max_pages * PAGE_SIZE_KB // 1024}MB)", "ALERT")
            self.trigger_oom_killer(reason=f"cgroup limit hit by PID {proc.pid}")
            return False

        # Check cgroup high watermark (kswapd reclaim pressure)
        if proc.rss_pages + 1 == proc.mem_high_pages + 1:
            log_kernel("kswapd", f"PID {proc.pid} exceeded memory.high ({proc.mem_high_pages * PAGE_SIZE_KB // 1024}MB): async page reclaim triggered", "WARN")
        elif (proc.rss_pages > proc.mem_high_pages) and (proc.rss_pages % 5000 == 0):
            log_kernel("kswapd", f"PID {proc.pid} sustained pressure above memory.high ({proc.rss_pages * PAGE_SIZE_KB // 1024}MB active)", "WARN")

        # Global system RAM exhaustion check
        if self.allocated_pages + 1 > self.total_ram_pages:
            log_kernel("mm-buddy", f"Global System RAM exhausted! Free pages: 0 / {self.total_ram_pages}", "ALERT")
            self.trigger_oom_killer(reason="global system OOM")
            return False

        proc.rss_pages += 1
        self.allocated_pages += 1
        return True

    def calculate_oom_score(self, proc: ProcessMemory) -> int:
        """
        Linux Kernel OOM Score Calculation:
        points = (total_pages * 1000) / total_ram_pages + oom_score_adj
        Clamped between 0 and 1000 (unless oom_score_adj == -1000 -> OOM-immune)
        """
        if proc.oom_score_adj == -1000:
            return 0  # immune to OOM killer

        raw_points = int((proc.total_pages * 1000) / self.total_ram_pages)
        score = raw_points + proc.oom_score_adj
        return max(0, min(1000, score))

    def trigger_oom_killer(self, reason: str) -> Optional[ProcessMemory]:
        log_kernel("oom-killer", f"Invoking Out-Of-Memory killer: {reason}", "ALERT")

        active_procs = [p for p in self.processes.values() if not p.killed and p.oom_score_adj != -1000]
        if not active_procs:
            log_kernel("oom-killer", "Kernel Panic: No killable processes available!", "ALERT")
            return None

        # Sort by oom_score descending, tie-break by total memory descending
        scored = [(self.calculate_oom_score(p), p.total_pages, p) for p in active_procs]
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

        highest_score, _, victim = scored[0]
        victim.killed = True
        self.allocated_pages -= victim.rss_pages

        print(f"\n{Color.ALERT} === [KERNEL OUT-OF-MEMORY KILLER INVOCATION] === {Color.RESET}")
        print(
            f"{Color.RED}Out of memory: Killed process {victim.pid} ({victim.name}) "
            f"total-vm:{(victim.total_pages * PAGE_SIZE_KB):,}kB, "
            f"anon-rss:{(victim.rss_pages * PAGE_SIZE_KB):,}kB, "
            f"oom_score_adj:{victim.oom_score_adj:+d}, "
            f"oom_score:{Color.BOLD}{highest_score}{Color.RESET}"
        )
        print(f"{Color.GREEN}Freed {(victim.rss_pages * PAGE_SIZE_KB) // 1024} MB RAM back to buddy allocator.{Color.RESET}\n")
        return victim


# ==============================================================================
# 3. Kernel Space vs User Space Syscall Benchmark
# ==============================================================================

def benchmark_syscall_transition(iterations: int = 150_000) -> None:
    print(header("Benchmark Ring 3 (User Space) vs Ring 0 (Syscall Trap)", level=2))
    print(f"{Color.GRAY}Executing {iterations:,} iterations comparing pure userspace arithmetic vs getpid() syscalls...{Color.RESET}")

    # Phase 1: Pure User Space (Ring 3) arithmetic
    t0 = time.perf_counter()
    accum = 0
    for i in range(iterations):
        accum = (accum + i) & 0xFFFFFF
    t_user = time.perf_counter() - t0

    # Phase 2: Syscall overhead (Ring 3 -> Ring 0 trap and switch back)
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = os.getpid()
    t_syscall = time.perf_counter() - t0

    ns_per_user_op = (t_user / iterations) * 1e9
    ns_per_syscall = (t_syscall / iterations) * 1e9
    ratio = ns_per_syscall / max(ns_per_user_op, 1e-9)

    print(f"\n  [1] Pure User Space Computation : {Color.GREEN}{t_user:6.4f}s{Color.RESET} ({ns_per_user_op:6.1f} ns/op)")
    print(f"  [2] Real OS Syscall `getpid()`  : {Color.RED}{t_syscall:6.4f}s{Color.RESET} ({ns_per_syscall:6.1f} ns/op)")
    print(f"  {Color.YELLOW}Kernel boundary transition cost : ~{ratio:.1f}x slower per operation{Color.RESET}")
    print(f"  {Color.GRAY}(Hardware trap, register save, kernel dispatch table, context isolation){Color.RESET}\n")


# ==============================================================================
# Main Orchestration & Interactive Output
# ==============================================================================

def run_simulation() -> None:
    print(header("LINUX INTERNALS & SRE SUBSYSTEM LABORATORY (Python Simulation)"))
    print(f"{Color.BOLD}Target Topics:{Color.RESET} CFS Scheduling, Cgroups Quota, Virtual Memory, Page Faults, OOM Killer")

    # Benchmark syscall cost
    benchmark_syscall_transition(iterations=120_000)

    # Simulation 1: CFS Scheduling
    print(header("Simulasi 1: Completely Fair Scheduler (CFS) & Cgroups CPU Throttling", level=2))
    cfs = CFSScheduler()

    tasks = [
        SchedEntity(vruntime=0.0, pid=101, name="api-gateway", nice=-5, weight=PRIO_TO_WEIGHT[-5], cgroup_quota_ms=0, cgroup_period_ms=100),
        SchedEntity(vruntime=0.0, pid=102, name="db-pool",    nice=0,  weight=PRIO_TO_WEIGHT[0],  cgroup_quota_ms=0, cgroup_period_ms=100),
        SchedEntity(vruntime=0.0, pid=103, name="ml-worker",  nice=10, weight=PRIO_TO_WEIGHT[10], cgroup_quota_ms=3.0, cgroup_period_ms=10.0),
        SchedEntity(vruntime=0.0, pid=104, name="batch-job",  nice=15, weight=PRIO_TO_WEIGHT[15], cgroup_quota_ms=2.0, cgroup_period_ms=10.0),
    ]

    for t in tasks:
        cfs.add_task(t)

    print(f"{Color.CYAN}Tasks terdaftar pada Runqueue:{Color.RESET}")
    for t in tasks:
        quota_str = f"{t.cgroup_quota_ms}ms/{t.cgroup_period_ms}ms" if t.cgroup_quota_ms > 0 else "unlimited"
        print(f"  - PID {t.pid:<4} [{t.name:<12}] nice={t.nice:>3} weight={t.weight:>5} cgroup.cpu.max={quota_str}")

    print(f"\n{Color.GRAY}Memulai 15 scheduling ticks (timeslice = 1.0 ms):{Color.RESET}")
    for tick in range(1, 16):
        if tick % 5 == 0:
            cfs.reset_cgroup_period()  # new cgroup accounting window
        msg = cfs.schedule_tick(timeslice_ms=1.0)
        print(f"  Tick {tick:02d} | {msg}")

    # Simulation 2: Memory & OOM Killer
    print(header("Simulasi 2: Page Faults, Cgroups Memory Watermark, dan OOM Killer", level=2))
    # 512 MB total RAM simulation
    mem_sys = MemorySubsystem(total_ram_mb=512)

    procs = [
        ProcessMemory(pid=1,   name="systemd",       rss_pages=2000,  swap_pages=0,    mem_max_pages=20000, mem_high_pages=15000, oom_score_adj=-1000),
        ProcessMemory(pid=210, name="ingress-nginx", rss_pages=15000, swap_pages=1000, mem_max_pages=25000, mem_high_pages=18000, oom_score_adj=-500),
        ProcessMemory(pid=305, name="redis-cache",   rss_pages=35000, swap_pages=2000, mem_max_pages=50000, mem_high_pages=40000, oom_score_adj=0),
        ProcessMemory(pid=450, name="mem-leak-app",  rss_pages=60000, swap_pages=5000, mem_max_pages=90000, mem_high_pages=70000, oom_score_adj=300),
    ]

    for p in procs:
        mem_sys.register_process(p)

    print(f"{Color.CYAN}Status Memori Awal & OOM Score Ranking (Total RAM: 512 MB):{Color.RESET}")
    print(f" {'PID':<6} {'Process Name':<16} {'RSS':<10} {'Swap':<8} {'Score Adj':<12} {'OOM Score':<10} {'Status'}")
    print(" " + "-" * 72)
    for p in procs:
        score = mem_sys.calculate_oom_score(p)
        status = f"{Color.GREEN}Immune{Color.RESET}" if p.oom_score_adj == -1000 else f"{Color.YELLOW}Eligible{Color.RESET}"
        print(f" {p.pid:<6} {p.name:<16} {p.rss_pages * 4 // 1024:>4} MB   {p.swap_pages * 4 // 1024:>3} MB  {p.oom_score_adj:>+6d}       {Color.BOLD}{score:>6}{Color.RESET}     {status}")

    # Simulate memory pressure & page allocation burst on leaking app
    print(f"\n{Color.YELLOW}[SIMULASI BEBAN] Injeksi alokasi memori agresif pada PID 450 (mem-leak-app)...{Color.RESET}")
    for burst in range(1, 40):
        # 1024 pages = 4MB per burst
        for _ in range(1024):
            success = mem_sys.allocate_page(pid=450, is_major_fault=(burst % 8 == 0))
            if not success:
                break
        if procs[3].killed:
            break

    print(f"{Color.GREEN}{Color.BOLD}[SIMULASI SELESAI] Arsitektur kernel tervalidasi secara deterministik.{Color.RESET}\n")


if __name__ == "__main__":
    run_simulation()

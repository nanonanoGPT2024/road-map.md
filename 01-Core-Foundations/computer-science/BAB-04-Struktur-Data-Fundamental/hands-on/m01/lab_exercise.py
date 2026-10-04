#!/usr/bin/env python3
"""
Hands-on Lab M01: Advanced Computer Science Core Concepts Simulation
BAB-04: Materi Lanjutan (Operating Systems, Virtual Memory, Concurrency & Scheduling)

This interactive simulation demonstrates:
1. CPU Scheduling (Round-Robin vs Priority Scheduling)
2. Virtual Memory Management (Page Faults & LRU Page Replacement)
3. Deadlock Detection & Avoidance (Banker's Algorithm)
4. Comprehensive Interactive Demonstration Mode
"""

import sys
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

# Terminal ANSI Color Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_BLACK = "\033[40m"


def print_header(title: str) -> None:
    border = "=" * 64
    print(f"\n{CYAN}{BOLD}{border}{RESET}")
    print(f"{CYAN}{BOLD}  :: {title.upper()} ::{RESET}")
    print(f"{CYAN}{BOLD}{border}{RESET}")


def print_step(msg: str) -> None:
    print(f"{GREEN}[INFO]{RESET} {msg}")


def print_warning(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def print_error(msg: str) -> None:
    print(f"{RED}[FAIL]{RESET} {msg}")


# ---------------------------------------------------------------------------
# 1. CPU SCHEDULING SIMULATION (Round Robin with Time Quantum)
# ---------------------------------------------------------------------------
class Process:
    def __init__(self, pid: str, burst_time: int, priority: int = 1):
        self.pid = pid
        self.burst_time = burst_time
        self.remaining_time = burst_time
        self.priority = priority
        self.completion_time = 0
        self.turnaround_time = 0
        self.waiting_time = 0

    def __repr__(self) -> str:
        return f"Process({self.pid}, Burst={self.burst_time}, Remaining={self.remaining_time})"


def simulate_round_robin(processes: List[Process], quantum: int = 2) -> None:
    print_header("Subsystem 1: Round-Robin CPU Scheduler")
    print_step(f"Initial Queue: {[p.pid for p in processes]} | Time Quantum: {quantum} ms")

    queue = deque([Process(p.pid, p.burst_time, p.priority) for p in processes])
    time_clock = 0
    gantt_chart: List[Tuple[str, int, int]] = []
    completed: List[Process] = []

    while queue:
        current = queue.popleft()
        exec_time = min(quantum, current.remaining_time)
        start_time = time_clock
        time_clock += exec_time
        current.remaining_time -= exec_time

        gantt_chart.append((current.pid, start_time, time_clock))
        print(f"  {MAGENTA}Clock {start_time:02d} -> {time_clock:02d}:{RESET} CPU running {BOLD}{current.pid}{RESET} (remaining: {current.remaining_time} ms)")

        if current.remaining_time > 0:
            queue.append(current)
        else:
            current.completion_time = time_clock
            current.turnaround_time = current.completion_time
            current.waiting_time = current.turnaround_time - current.burst_time
            completed.append(current)
            print(f"    {GREEN}✔ Process {current.pid} TERMINATED at {time_clock} ms{RESET}")

    # Metrics summary
    print(f"\n{BOLD}Gantt Timeline:{RESET}")
    timeline_str = " | ".join([f"{pid} [{s}-{e}]" for pid, s, e in gantt_chart])
    print(f"  {BG_BLUE}{WHITE} {timeline_str} {RESET}\n")

    avg_wait = sum(p.waiting_time for p in completed) / len(completed)
    avg_tat = sum(p.turnaround_time for p in completed) / len(completed)

    print(f"{BOLD}{'PID':<6}{'Burst':<10}{'Turnaround':<14}{'Waiting':<10}{RESET}")
    print("-" * 40)
    for p in completed:
        print(f"{p.pid:<6}{p.burst_time:<10}{p.turnaround_time:<14}{p.waiting_time:<10}")
    print("-" * 40)
    print(f"{YELLOW}Average Waiting Time    : {avg_wait:.2f} ms{RESET}")
    print(f"{YELLOW}Average Turnaround Time : {avg_tat:.2f} ms{RESET}")


# ---------------------------------------------------------------------------
# 2. VIRTUAL MEMORY SIMULATION (LRU Page Replacement)
# ---------------------------------------------------------------------------
class LRUPageReplacer:
    def __init__(self, frame_count: int):
        self.capacity = frame_count
        self.frames: List[int] = []
        self.recency: Dict[int, int] = {}
        self.timer = 0
        self.hits = 0
        self.faults = 0

    def access_page(self, page_id: int) -> bool:
        self.timer += 1
        if page_id in self.frames:
            self.hits += 1
            self.recency[page_id] = self.timer
            return True  # Page Hit

        # Page Fault
        self.faults += 1
        if len(self.frames) < self.capacity:
            self.frames.append(page_id)
        else:
            # Evict Least Recently Used
            lru_page = min(self.frames, key=lambda p: self.recency[p])
            evict_idx = self.frames.index(lru_page)
            print(f"    {YELLOW}↳ Evicting Page {lru_page} from Frame {evict_idx}{RESET}")
            self.frames[evict_idx] = page_id

        self.recency[page_id] = self.timer
        return False  # Page Fault


def simulate_lru_paging(page_stream: List[int], frames: int = 3) -> None:
    print_header("Subsystem 2: Virtual Memory & LRU Paging")
    print_step(f"Physical Memory Frames: {frames}")
    print_step(f"Page Access Stream: {page_stream}")

    lru = LRUPageReplacer(frames)

    print(f"\n{BOLD}{'Step':<6}{'Page':<8}{'Status':<14}{'Memory Frames':<20}{RESET}")
    print("-" * 48)

    for idx, page in enumerate(page_stream, start=1):
        is_hit = lru.access_page(page)
        status_str = f"{GREEN}HIT{RESET}" if is_hit else f"{RED}FAULT{RESET}"
        frames_repr = str(lru.frames)
        print(f"{idx:<6}{page:<8}{status_str:<23}{frames_repr:<20}")

    total = len(page_stream)
    hit_ratio = (lru.hits / total) * 100
    fault_ratio = (lru.faults / total) * 100

    print("-" * 48)
    print(f"{CYAN}Total References: {total}{RESET}")
    print(f"{GREEN}Page Hits       : {lru.hits} ({hit_ratio:.1f}%){RESET}")
    print(f"{RED}Page Faults     : {lru.faults} ({fault_ratio:.1f}%){RESET}")


# ---------------------------------------------------------------------------
# 3. DEADLOCK DETECTION (Banker's Algorithm / Safe State Verification)
# ---------------------------------------------------------------------------
class BankersAlgorithm:
    def __init__(
        self,
        processes: List[str],
        available: List[int],
        maximum: List[List[int]],
        allocation: List[List[int]],
    ):
        self.processes = processes
        self.available = available[:]
        self.maximum = maximum
        self.allocation = allocation
        self.num_p = len(processes)
        self.num_r = len(available)

        # Need = Max - Allocation
        self.need = [
            [self.maximum[i][j] - self.allocation[i][j] for j in range(self.num_r)]
            for i in range(self.num_p)
        ]

    def verify_safety(self) -> Tuple[bool, List[str]]:
        work = self.available[:]
        finish = [False] * self.num_p
        safe_sequence: List[str] = []

        print_step(f"Initial Available Resources: {work}")

        while len(safe_sequence) < self.num_p:
            allocated_in_round = False
            for i in range(self.num_p):
                if not finish[i]:
                    # Check if Need <= Work
                    if all(self.need[i][j] <= work[j] for j in range(self.num_r)):
                        # Process can complete and release resources
                        for j in range(self.num_r):
                            work[j] += self.allocation[i][j]
                        finish[i] = True
                        safe_sequence.append(self.processes[i])
                        allocated_in_round = True
                        print(f"  {GREEN}✔ Process {self.processes[i]} satisfied.{RESET} New Work pool: {work}")
                        break

            if not allocated_in_round:
                return False, []

        return True, safe_sequence


def simulate_bankers_algorithm() -> None:
    print_header("Subsystem 3: Banker's Deadlock Avoidance Algorithm")

    pids = ["P0", "P1", "P2", "P3", "P4"]
    available = [3, 3, 2]  # Resources R0, R1, R2

    allocation = [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
        [2, 1, 1],
        [0, 0, 2],
    ]

    maximum = [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
        [2, 2, 2],
        [4, 3, 3],
    ]

    print(f"{BOLD}Resources Matrix Definition (3 Resource Types: R0, R1, R2):{RESET}")
    print(f"{'PID':<6}{'Allocation':<16}{'Max Claim':<16}{'Current Need':<16}")
    print("-" * 54)
    banker = BankersAlgorithm(pids, available, maximum, allocation)
    for i, p in enumerate(pids):
        print(f"{p:<6}{str(allocation[i]):<16}{str(maximum[i]):<16}{str(banker.need[i]):<16}")
    print("-" * 54)

    is_safe, seq = banker.verify_safety()
    if is_safe:
        print(f"\n{GREEN}{BOLD}SYSTEM IS IN A SAFE STATE!{RESET}")
        seq_str = " -> ".join([f"{BOLD}{p}{RESET}" for p in seq])
        print(f"Safe Execution Sequence: [ {seq_str} ]")
    else:
        print(f"\n{RED}{BOLD}DEADLOCK DETECTED! System cannot guarantee safe execution.{RESET}")


# ---------------------------------------------------------------------------
# 4. INTERACTIVE SHELL & DEMO ENGINE
# ---------------------------------------------------------------------------
def run_all_demos() -> None:
    print(f"\n{BG_BLACK}{CYAN}{BOLD}=== COMPUTER SCIENCE CORE LAB: FULL DEMO SUITE ==={RESET}")

    # 1. Scheduler Demo
    demo_processes = [
        Process("P1", burst_time=6, priority=2),
        Process("P2", burst_time=3, priority=1),
        Process("P3", burst_time=8, priority=3),
        Process("P4", burst_time=4, priority=2),
    ]
    simulate_round_robin(demo_processes, quantum=3)

    # 2. Virtual Memory Paging Demo
    sample_pages = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
    simulate_lru_paging(sample_pages, frames=3)

    # 3. Deadlock banker demo
    simulate_bankers_algorithm()

    print_header("Lab Session Completed")
    print(f"{GREEN}{BOLD}All kernel and architectural algorithms executed successfully.{RESET}\n")


def display_menu() -> None:
    print(f"\n{BOLD}{CYAN}===== COMPUTER SCIENCE FOUNDATIONS INTERACTIVE LAB ====={RESET}")
    print(f" {BOLD}1.{RESET} CPU Scheduler Simulation (Round-Robin)")
    print(f" {BOLD}2.{RESET} Virtual Memory LRU Page Replacement")
    print(f" {BOLD}3.{RESET} Deadlock Avoidance (Banker's Algorithm)")
    print(f" {BOLD}4.{RESET} Run Complete Simulation Suite")
    print(f" {BOLD}5.{RESET} Exit Lab")
    print(f"{CYAN}========================================================{RESET}")


def interactive_loop() -> None:
    while True:
        display_menu()
        try:
            choice = input(f"{YELLOW}Select option [1-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{MAGENTA}Session terminated.{RESET}")
            break

        if choice == "1":
            try:
                n_str = input("Enter number of processes (default 3): ").strip()
                n = int(n_str) if n_str else 3
                procs = []
                for i in range(1, n + 1):
                    b_str = input(f"  Burst time for P{i} in ms (default {i*2}): ").strip()
                    b = int(b_str) if b_str else i * 2
                    procs.append(Process(f"P{i}", b))
                q_str = input("Enter Time Quantum (default 2): ").strip()
                q = int(q_str) if q_str else 2
                simulate_round_robin(procs, q)
            except ValueError:
                print_error("Invalid integer input. Reverting to default values.")
                simulate_round_robin([Process("P1", 5), Process("P2", 3), Process("P3", 6)], 2)

        elif choice == "2":
            try:
                pages_str = input("Enter page sequence comma-separated (e.g. 1,2,3,1,4): ").strip()
                if pages_str:
                    stream = [int(x.strip()) for x in pages_str.split(",") if x.strip()]
                else:
                    stream = [1, 3, 0, 3, 5, 6, 3]
                f_str = input("Enter number of frames (default 3): ").strip()
                f_cnt = int(f_str) if f_str else 3
                simulate_lru_paging(stream, f_cnt)
            except ValueError:
                print_error("Invalid input format. Using standard benchmark sequence.")
                simulate_lru_paging([7, 0, 1, 2, 0, 3, 0, 4, 2, 3], 3)

        elif choice == "3":
            simulate_bankers_algorithm()

        elif choice == "4":
            run_all_demos()

        elif choice == "5":
            print(f"{GREEN}Exiting lab. Selamat belajar fondasi computer science!{RESET}\n")
            break
        else:
            print_warning("Option not recognized. Please choose from 1 to 5.")


def main() -> None:
    # If run in non-interactive environment (CI, pipe, or args), run demo suite automatically
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_all_demos()
        return

    if not sys.stdin.isatty():
        print_step("Non-interactive pipe detected. Executing automated demo suite...")
        run_all_demos()
        return

    interactive_loop()


if __name__ == "__main__":
    main()

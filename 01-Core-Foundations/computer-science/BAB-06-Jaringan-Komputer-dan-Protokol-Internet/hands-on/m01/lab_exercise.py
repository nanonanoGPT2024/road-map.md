#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Computer Science - Advanced Core Foundations (BAB-06)
Simulasi Interaktif:
 1. Turing Machine Simulator (Tape computation & state transitions)
 2. Operating System Deadlock Detection (Banker's Algorithm & Resource Allocation)
 3. Dynamic Programming Matrix Visualizer (Needleman-Wunsch / Edit Distance)

Dibuat untuk eksekusi mandiri (standalone) dengan output ANSI terminal color.
"""

import sys
import time
from typing import Dict, List, Tuple, Set


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}======================================================================
  ADVANCED COMPUTER SCIENCE FOUNDATIONS LAB (BAB-06 MATERI LANJUTAN)
  Simulasi Interaktif: Automata, Concurrency Safety, & Dinamika Algoritma
======================================================================{Colors.RESET}
"""
    print(banner)


# -----------------------------------------------------------------------------
# 1. TURING MACHINE SIMULATOR
# -----------------------------------------------------------------------------
class TuringMachine:
    """Simulasi Turing Machine deterministik untuk pengenalan bahasa {0^n 1^n | n >= 1}"""

    def __init__(self, tape_str: str):
        self.tape = list(tape_str) + ["_"] * 10
        self.head = 0
        self.state = "q0"
        self.halted = False
        self.accepted = False
        self.step_count = 0

        # Transitions: (state, symbol) -> (next_state, write_symbol, direction)
        self.transitions = {
            ("q0", "0"): ("q1", "X", "R"),
            ("q0", "Y"): ("q3", "Y", "R"),
            ("q1", "0"): ("q1", "0", "R"),
            ("q1", "Y"): ("q1", "Y", "R"),
            ("q1", "1"): ("q2", "Y", "L"),
            ("q2", "0"): ("q2", "0", "L"),
            ("q2", "Y"): ("q2", "Y", "L"),
            ("q2", "X"): ("q0", "X", "R"),
            ("q3", "Y"): ("q3", "Y", "R"),
            ("q3", "_"): ("q_accept", "_", "R"),
        }

    def render_tape(self):
        tape_vis = []
        for i, char in enumerate(self.tape[:16]):
            if i == self.head:
                tape_vis.append(f"{Colors.YELLOW}{Colors.BOLD}[{char}]{Colors.RESET}")
            else:
                tape_vis.append(f" {char} ")
        tape_line = "".join(tape_vis)
        print(f"  Step {self.step_count:02d} | State: {Colors.CYAN}{self.state:<8}{Colors.RESET} | Pita: {tape_line}")

    def step(self) -> bool:
        if self.state == "q_accept":
            self.halted = True
            self.accepted = True
            return False

        current_symbol = self.tape[self.head]
        key = (self.state, current_symbol)

        if key not in self.transitions:
            self.halted = True
            self.accepted = False
            return False

        next_state, write_sym, direction = self.transitions[key]
        self.tape[self.head] = write_sym
        self.state = next_state
        self.head += 1 if direction == "R" else -1
        if self.head < 0:
            self.head = 0
        self.step_count += 1
        return True


def run_turing_machine_interactive():
    print(f"\n{Colors.BOLD}{Colors.GREEN}[1] Turing Machine: Recognizer Bahasa L = {{0^n 1^n}}{Colors.RESET}")
    print(f"Aturan: Memverifikasi apakah string biner memiliki jumlah 0 diikuti jumlah 1 yang sama.")
    default_input = "000111"
    raw_in = input(f"{Colors.YELLOW}Masukkan input tape (default: '{default_input}'): {Colors.RESET}").strip()
    input_str = raw_in if raw_in else default_input

    tm = TuringMachine(input_str)
    print(f"\n{Colors.BLUE}Memulai simulasi Turing Machine:{Colors.RESET}")
    tm.render_tape()

    while not tm.halted:
        cont = tm.step()
        tm.render_tape()
        time.sleep(0.08)

    if tm.accepted:
        print(f"\n{Colors.GREEN}{Colors.BOLD}>> HASIL: STRING VALID (Accepted oleh Turing Machine)!{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}>> HASIL: STRING DITOLAK (Rejected / Invalid Pattern)!{Colors.RESET}\n")


# -----------------------------------------------------------------------------
# 2. OPERATING SYSTEM CONCURRENCY & BANKER'S ALGORITHM
# -----------------------------------------------------------------------------
class BankersAlgorithm:
    """Simulasi penghindaran deadlock menggunakan algoritma Banker (Dijkstra)"""

    def __init__(self, allocation: List[List[int]], max_matrix: List[List[int]], available: List[int]):
        self.alloc = allocation
        self.max = max_matrix
        self.avail = available[:]
        self.num_proc = len(allocation)
        self.num_res = len(available)
        self.need = [
            [self.max[i][j] - self.alloc[i][j] for j in range(self.num_res)]
            for i in range(self.num_proc)
        ]

    def display_state(self):
        print(f"\n{Colors.CYAN}--- STATUS SISTEM SAAT INI ---{Colors.RESET}")
        print(f"Resource Tersedia (Available): {Colors.BOLD}{self.avail}{Colors.RESET}")
        print(f"{'Proses':<8}{'Alokasi':<16}{'Maksimum':<16}{'Kebutuhan (Need)':<16}")
        for i in range(self.num_proc):
            print(f"P{i:<7}{str(self.alloc[i]):<16}{str(self.max[i]):<16}{str(self.need[i]):<16}")

    def evaluate_safe_state(self) -> Tuple[bool, List[int]]:
        work = self.avail[:]
        finish = [False] * self.num_proc
        safe_sequence = []

        print(f"\n{Colors.BLUE}Mengevaluasi Safe Sequence via Banker's Algorithm:{Colors.RESET}")
        for step in range(self.num_proc):
            found_candidate = False
            for p in range(self.num_proc):
                if not finish[p]:
                    # Cek apakah Need[p] <= Work
                    if all(self.need[p][r] <= work[r] for r in range(self.num_res)):
                        for r in range(self.num_res):
                            work[r] += self.alloc[p][r]
                        finish[p] = True
                        safe_sequence.append(p)
                        found_candidate = True
                        print(f"  {Colors.GREEN}✓ P{p} dapat dialokasikan resource.{Colors.RESET} Work baru: {work}")
                        break
            if not found_candidate:
                break

        is_safe = len(safe_sequence) == self.num_proc
        return is_safe, safe_sequence


def run_bankers_simulation():
    print(f"\n{Colors.BOLD}{Colors.GREEN}[2] Concurrency & Deadlock Avoidance (Banker's Algorithm){Colors.RESET}")
    # Default scenario: 5 proses, 3 resource types (A, B, C)
    alloc = [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
        [2, 1, 1],
        [0, 0, 2]
    ]
    max_m = [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
        [2, 2, 2],
        [4, 3, 3]
    ]
    avail = [3, 3, 2]

    banker = BankersAlgorithm(alloc, max_m, avail)
    banker.display_state()
    is_safe, sequence = banker.evaluate_safe_state()

    if is_safe:
        seq_str = " -> ".join([f"P{p}" for p in sequence])
        print(f"\n{Colors.GREEN}{Colors.BOLD}>> SISTEM DALAM STATUS SAFE! Urutan Eksekusi: < {seq_str} >{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}>> DEADLOCK UNSAFE! Sistem berpotensi mengalami starvation/deadlock.{Colors.RESET}\n")


# -----------------------------------------------------------------------------
# 3. DYNAMIC PROGRAMMING: SEQUENCE ALIGNMENT / EDIT DISTANCE
# -----------------------------------------------------------------------------
def run_dynamic_programming_visualizer():
    print(f"\n{Colors.BOLD}{Colors.GREEN}[3] Dynamic Programming: String Alignment Matrix (Levenshtein){Colors.RESET}")
    s1_default = "ALGO"
    s2_default = "LOGIC"
    
    in_s1 = input(f"{Colors.YELLOW}String Asal (default: '{s1_default}'): {Colors.RESET}").strip()
    in_s2 = input(f"{Colors.YELLOW}String Target (default: '{s2_default}'): {Colors.RESET}").strip()
    s1 = in_s1 if in_s1 else s1_default
    s2 = in_s2 if in_s2 else s2_default

    n, m = len(s1), len(s2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    print(f"\n{Colors.BLUE}Membangun DP Table Secara Iteratif:{Colors.RESET}")
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    # Visualisasi matriks dengan warna
    header = "      " + "  ".join([f"{Colors.BOLD}{c}{Colors.RESET}" for c in (" " + s2)])
    print(header)
    for i in range(n + 1):
        row_char = " " if i == 0 else s1[i - 1]
        row_vals = []
        for j in range(m + 1):
            val = dp[i][j]
            if i == n and j == m:
                row_vals.append(f"{Colors.RED}{Colors.BOLD}{val:2d}{Colors.RESET}")
            else:
                row_vals.append(f"{Colors.CYAN}{val:2d}{Colors.RESET}")
        print(f" {Colors.BOLD}{row_char}{Colors.RESET} | " + " ".join(row_vals))

    min_ops = dp[n][m]
    print(f"\n{Colors.GREEN}{Colors.BOLD}>> Jarak Edit Minimum (Levenshtein Distance) '{s1}' ke '{s2}': {min_ops} operasi.{Colors.RESET}\n")


# -----------------------------------------------------------------------------
# MAIN INTERACTIVE DISPATCHER
# -----------------------------------------------------------------------------
def main():
    while True:
        print_banner()
        print("Pilih modul simulasi fondasi komputer:")
        print(f"  {Colors.BOLD}1.{Colors.RESET} Turing Machine Simulator (Bahasa Formal & Mesin Abstrak)")
        print(f"  {Colors.BOLD}2.{Colors.RESET} Banker's Algorithm (OS Deadlock Avoidance)")
        print(f"  {Colors.BOLD}3.{Colors.RESET} Dynamic Programming Visualizer (Levenshtein Distance)")
        print(f"  {Colors.BOLD}4.{Colors.RESET} Jalankan Semua Modul Otomatis")
        print(f"  {Colors.BOLD}0.{Colors.RESET} Keluar")

        choice = input(f"\n{Colors.YELLOW}Pilihan Anda (0-4): {Colors.RESET}").strip()
        if choice == "1":
            run_turing_machine_interactive()
        elif choice == "2":
            run_bankers_simulation()
        elif choice == "3":
            run_dynamic_programming_visualizer()
        elif choice == "4":
            run_turing_machine_interactive()
            run_bankers_simulation()
            run_dynamic_programming_visualizer()
        elif choice in ("0", "q", "exit"):
            print(f"{Colors.CYAN}Sesi lab selesai. Terima kasih.{Colors.RESET}")
            sys.exit(0)
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")

        input(f"{Colors.HEADER}Tekan [Enter] untuk melanjutkan ke menu utama...{Colors.RESET}")


if __name__ == "__main__":
    main()

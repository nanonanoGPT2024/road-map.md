#!/usr/bin/env python3
"""
Lab Exercise M01: Computer Science Core Foundations Simulator
BAB-02: Materi Lanjutan (Virtual Memory, Cache Hierarchy & CPU Instruction Cycle)

Simulasi interaktif tingkat lanjut yang mencakup:
1. Von Neumann Architecture & Instruction Cycle (Fetch, Decode, Execute, Writeback)
2. Direct-Mapped Cache & Memory Hierarchy (Hit/Miss ratio, Eviction policy)
3. Virtual Memory & Page Table Translation (Virtual to Physical Address, Page Fault)
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}  {title.center(61)}  {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")


def status_badge(hit: bool) -> str:
    if hit:
        return f"{BOLD}{GREEN}[ HIT  ]{RESET}"
    return f"{BOLD}{RED}[ MISS ]{RESET}"


# ==========================================
# 1. CPU & Instruction Cycle Simulation
# ==========================================
@dataclass
class CPU:
    registers: Dict[str, int] = field(default_factory=lambda: {"R0": 0, "R1": 0, "R2": 0, "ACC": 0})
    pc: int = 0
    flags: Dict[str, bool] = field(default_factory=lambda: {"ZERO": False, "NEGATIVE": False})

    def reset(self) -> None:
        self.registers = {"R0": 0, "R1": 0, "R2": 0, "ACC": 0}
        self.pc = 0
        self.flags = {"ZERO": False, "NEGATIVE": False}

    def execute_instruction(self, instruction: str) -> str:
        parts = instruction.strip().split()
        if not parts:
            return "NOP"

        opcode = parts[0].upper()
        args = parts[1:]

        if opcode == "LOAD":
            reg, val = args[0], int(args[1])
            self.registers[reg] = val
            return f"Loaded immediate {val} into {reg}"

        elif opcode == "ADD":
            reg = args[0]
            self.registers["ACC"] += self.registers[reg]
            self._update_flags()
            return f"ACC = ACC + {reg} -> ACC={self.registers['ACC']}"

        elif opcode == "SUB":
            reg = args[0]
            self.registers["ACC"] -= self.registers[reg]
            self._update_flags()
            return f"ACC = ACC - {reg} -> ACC={self.registers['ACC']}"

        elif opcode == "MOV":
            dst, src = args[0], args[1]
            self.registers[dst] = self.registers[src]
            return f"Moved {src} ({self.registers[src]}) to {dst}"

        elif opcode == "HALT":
            return "HALT reached"

        return f"Unknown opcode: {opcode}"

    def _update_flags(self) -> None:
        self.flags["ZERO"] = self.registers["ACC"] == 0
        self.flags["NEGATIVE"] = self.registers["ACC"] < 0


def run_cpu_demo() -> None:
    header("MODUL 1: CPU Instruction Cycle Simulation")
    cpu = CPU()
    program = [
        "LOAD R0 15",
        "LOAD R1 25",
        "MOV ACC R0",
        "ADD R1",
        "SUB R0",
        "HALT"
    ]

    print(f"{YELLOW}Program Assembly sederhana:{RESET}")
    for idx, inst in enumerate(program):
        print(f"  [{idx:02d}] {inst}")
    print()

    for idx, inst in enumerate(program):
        cpu.pc = idx
        print(f"{BOLD}{BLUE}[FETCH]{RESET} PC=0x{cpu.pc:02X} | Instruksi: {WHITE}{inst}{RESET}")
        time.sleep(0.15)
        print(f"  {BOLD}{MAGENTA}[DECODE & EXECUTE]{RESET} ...", end=" ")
        result = cpu.execute_instruction(inst)
        print(f"{GREEN}{result}{RESET}")
        print(f"  {BOLD}{DIM}[REGISTERS]{RESET} R0={cpu.registers['R0']} | R1={cpu.registers['R1']} | ACC={cpu.registers['ACC']} | ZeroFlag={cpu.flags['ZERO']}")
        print()


# ==========================================
# 2. Cache Memory Simulator (Direct-Mapped)
# ==========================================
@dataclass
class CacheLine:
    valid: bool = False
    tag: int = -1
    data: int = 0


class CacheSimulator:
    def __init__(self, num_lines: int = 4, block_size: int = 4):
        self.num_lines = num_lines
        self.block_size = block_size
        self.lines: List[CacheLine] = [CacheLine() for _ in range(num_lines)]
        self.hits = 0
        self.misses = 0

    def access(self, address: int) -> Tuple[bool, int, int]:
        block_address = address // self.block_size
        index = block_address % self.num_lines
        tag = block_address // self.num_lines

        line = self.lines[index]
        if line.valid and line.tag == tag:
            self.hits += 1
            return True, index, tag
        else:
            self.misses += 1
            # Cache fill / replacement
            line.valid = True
            line.tag = tag
            line.data = address * 10
            return False, index, tag

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


def run_cache_demo() -> None:
    header("MODUL 2: L1 Direct-Mapped Cache Hierarchy")
    cache = CacheSimulator(num_lines=4, block_size=4)
    access_stream = [0x00, 0x04, 0x10, 0x04, 0x00, 0x14, 0x04, 0x10]

    print(f"Spesifikasi Cache: {BOLD}4 Cache Lines, Block Size 4 bytes{RESET}\n")
    print(f"{'Mem Address':<14} | {'Block':<8} | {'Index':<8} | {'Tag':<8} | {'Result'}")
    print("-" * 55)

    for addr in access_stream:
        block_addr = addr // cache.block_size
        hit, idx, tag = cache.access(addr)
        print(f"0x{addr:04X} ({addr:<4}) | {block_addr:<8} | {idx:<8} | {tag:<8} | {status_badge(hit)}")
        time.sleep(0.12)

    print("-" * 55)
    print(f"{BOLD}Total Akses:{RESET} {len(access_stream)}")
    print(f"{GREEN}Cache Hits :{RESET} {cache.hits}")
    print(f"{RED}Cache Miss :{RESET} {cache.misses}")
    print(f"{BOLD}{CYAN}Hit Rate   :{RESET} {BOLD}{cache.hit_rate():.2f}%{RESET}\n")


# ==========================================
# 3. Virtual Memory & Page Table Simulator
# ==========================================
@dataclass
class PageTableEntry:
    frame_number: Optional[int] = None
    present: bool = False


class VirtualMemorySimulator:
    def __init__(self, page_size: int = 256, num_frames: int = 4):
        self.page_size = page_size
        self.num_frames = num_frames
        self.page_table: Dict[int, PageTableEntry] = {}
        self.free_frames: List[int] = list(range(num_frames))
        self.fifo_queue: List[int] = []
        self.page_faults = 0
        self.total_translations = 0

    def translate(self, virtual_address: int) -> Tuple[int, bool]:
        self.total_translations += 1
        page_num = virtual_address // self.page_size
        offset = virtual_address % self.page_size

        if page_num not in self.page_table:
            self.page_table[page_num] = PageTableEntry()

        entry = self.page_table[page_num]
        fault = False

        if not entry.present:
            fault = True
            self.page_faults += 1
            if self.free_frames:
                assigned_frame = self.free_frames.pop(0)
            else:
                # FIFO Page Replacement
                victim_page = self.fifo_queue.pop(0)
                assigned_frame = self.page_table[victim_page].frame_number
                self.page_table[victim_page].present = False
                self.page_table[victim_page].frame_number = None

            entry.frame_number = assigned_frame
            entry.present = True
            self.fifo_queue.append(page_num)

        physical_address = (entry.frame_number * self.page_size) + offset
        return physical_address, fault


def run_virtual_memory_demo() -> None:
    header("MODUL 3: Virtual Memory & Page Table Translation (MMU)")
    vmm = VirtualMemorySimulator(page_size=256, num_frames=3)
    test_addresses = [0x0020, 0x0150, 0x0050, 0x0280, 0x0350, 0x0080]

    print(f"Spesifikasi MMU: {BOLD}Page Size = 256 Bytes, Total Physical Frames = 3{RESET}\n")
    print(f"{'Virtual Addr':<14} | {'Page #':<8} | {'Offset':<8} | {'Physical Addr':<15} | {'MMU Event'}")
    print("-" * 65)

    for vaddr in test_addresses:
        page_num = vaddr // vmm.page_size
        offset = vaddr % vmm.page_size
        paddr, fault = vmm.translate(vaddr)

        event_str = f"{RED}[PAGE FAULT]{RESET}" if fault else f"{GREEN}[PAGED HIT]{RESET}"
        print(f"0x{vaddr:04X} ({vaddr:<5}) | {page_num:<8} | 0x{offset:02X}   | 0x{paddr:04X} ({paddr:<5}) | {event_str}")
        time.sleep(0.12)

    print("-" * 65)
    print(f"{BOLD}Total Terjemahan MMU:{RESET} {vmm.total_translations}")
    print(f"{YELLOW}Page Faults         :{RESET} {vmm.page_faults}")
    print(f"{GREEN}Page Hit Rate       :{RESET} {((vmm.total_translations - vmm.page_faults) / vmm.total_translations * 100):.2f}%\n")


# ==========================================
# Main Menu & Interactive CLI
# ==========================================
def main() -> None:
    while True:
        print(f"{BOLD}{MAGENTA}======================================================{RESET}")
        print(f"{BOLD}{WHITE}   CS FOUNDATION SIMULATOR (BAB-02 MATERI LANJUTAN)   {RESET}")
        print(f"{BOLD}{MAGENTA}======================================================{RESET}")
        print(f" {CYAN}1.{RESET} CPU & Instruction Cycle (Von Neumann)")
        print(f" {CYAN}2.{RESET} Cache Memory & Direct-Mapped Hierarchy")
        print(f" {CYAN}3.{RESET} Virtual Memory & Page Table MMU Translation")
        print(f" {CYAN}4.{RESET} Jalankan Seluruh Demonstrasi (Pipeline Lengkap)")
        print(f" {RED}0.{RESET} Keluar")
        print(f"{BOLD}{MAGENTA}------------------------------------------------------{RESET}")

        try:
            choice = input(f"{YELLOW}Pilih opsi [0-4]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GREEN}Sampai jumpa!{RESET}")
            sys.exit(0)

        if choice == "1":
            run_cpu_demo()
        elif choice == "2":
            run_cache_demo()
        elif choice == "3":
            run_virtual_memory_demo()
        elif choice == "4":
            run_cpu_demo()
            run_cache_demo()
            run_virtual_memory_demo()
        elif choice == "0":
            print(f"{GREEN}Simulasi selesai. Teruslah bereksplorasi!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-4.{RESET}\n")


if __name__ == "__main__":
    # If run in non-interactive / pipe mode, execute full suite directly
    if not sys.stdin.isatty():
        run_cpu_demo()
        run_cache_demo()
        run_virtual_memory_demo()
    else:
        main()

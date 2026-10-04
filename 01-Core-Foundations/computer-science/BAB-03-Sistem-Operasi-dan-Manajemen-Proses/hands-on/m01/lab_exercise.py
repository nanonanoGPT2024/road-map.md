#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Komputer Lanjutan (BAB-03)
Topik:
  1. Virtual Memory Paging & TLB Simulation (LRU Replacement)
  2. CPU Process Scheduling Simulation (Round Robin with Context Switching)
  3. Memory Hierarchy & L1 Cache Simulation (Direct Mapped Hit/Miss)

Format: Terminal Interaktif dengan ANSI Colors.
"""

import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ANSI Escape Sequences
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_GRAY = "\033[90m"


def print_banner(title: str) -> None:
    border = "=" * 64
    print(f"\n{CLR_CYAN}{CLR_BOLD}{border}{CLR_RESET}")
    print(f"{CLR_YELLOW}{CLR_BOLD}  {title.center(60)}{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}{border}{CLR_RESET}\n")


def print_success(msg: str) -> None:
    print(f"{CLR_GREEN}[✓] {msg}{CLR_RESET}")


def print_info(msg: str) -> None:
    print(f"{CLR_BLUE}[i] {msg}{CLR_RESET}")


def print_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}[!] {msg}{CLR_RESET}")


def print_error(msg: str) -> None:
    print(f"{CLR_RED}[✗] {msg}{CLR_RESET}")


# ==============================================================================
# MODUL 1: VIRTUAL MEMORY, TLB, & LRU PAGE REPLACEMENT
# ==============================================================================
class VirtualMemoryManager:
    def __init__(self, num_frames: int = 3, tlb_size: int = 2):
        self.num_frames = num_frames
        self.tlb_size = tlb_size
        self.tlb: Dict[int, int] = {}  # VPN -> PFN
        self.tlb_lru: List[int] = []
        self.page_table: Dict[int, Optional[int]] = {}  # VPN -> PFN
        self.frames: List[Optional[int]] = [None] * num_frames  # Frame index -> VPN
        self.frame_history: List[int] = []  # For LRU page replacement

    def access_page(self, vpn: int) -> Tuple[bool, bool, int]:
        """
        Mengakses halaman virtual (VPN).
        Mengembalikan tuple: (tlb_hit, page_fault, pfn)
        """
        tlb_hit = False
        page_fault = False

        # 1. Cek TLB
        if vpn in self.tlb:
            tlb_hit = True
            pfn = self.tlb[vpn]
            self.tlb_lru.remove(vpn)
            self.tlb_lru.append(vpn)
            self._update_frame_lru(pfn)
            return tlb_hit, page_fault, pfn

        # 2. Cek Page Table
        if vpn in self.page_table and self.page_table[vpn] is not None:
            pfn = self.page_table[vpn]
            self._update_frame_lru(pfn)
        else:
            # Page Fault!
            page_fault = True
            pfn = self._allocate_frame(vpn)

        # 3. Update TLB (LRU)
        if len(self.tlb) >= self.tlb_size:
            evicted_tlb = self.tlb_lru.pop(0)
            del self.tlb[evicted_tlb]
        self.tlb[vpn] = pfn
        self.tlb_lru.append(vpn)

        return tlb_hit, page_fault, pfn

    def _update_frame_lru(self, pfn: int) -> None:
        if pfn in self.frame_history:
            self.frame_history.remove(pfn)
        self.frame_history.append(pfn)

    def _allocate_frame(self, vpn: int) -> int:
        # Cek jika ada frame kosong
        for idx in range(self.num_frames):
            if self.frames[idx] is None:
                self.frames[idx] = vpn
                self.page_table[vpn] = idx
                self.frame_history.append(idx)
                return idx

        # Jika penuh, lakukan LRU eviction
        victim_pfn = self.frame_history.pop(0)
        old_vpn = self.frames[victim_pfn]
        if old_vpn is not None:
            self.page_table[old_vpn] = None
            if old_vpn in self.tlb:
                del self.tlb[old_vpn]
                if old_vpn in self.tlb_lru:
                    self.tlb_lru.remove(old_vpn)

        self.frames[victim_pfn] = vpn
        self.page_table[vpn] = victim_pfn
        self.frame_history.append(victim_pfn)
        return victim_pfn


def run_virtual_memory_demo() -> None:
    print_banner("SIMULASI 1: VIRTUAL MEMORY & TLB CACHE (LRU)")
    vm = VirtualMemoryManager(num_frames=3, tlb_size=2)
    access_stream = [1, 2, 3, 2, 4, 1, 5, 2]

    print(f"{CLR_BOLD}Konfigurasi:{CLR_RESET} Kapasitas Frame Fisik = 3, Kapasitas TLB = 2")
    print(f"{CLR_BOLD}Urutan Akses VPN:{CLR_RESET} {access_stream}\n")

    print(f"{'Akses':<7} | {'TLB':<10} | {'Status Memori':<16} | {'Frame Fisik (PFN 0,1,2)':<25}")
    print("-" * 68)

    for vpn in access_stream:
        tlb_hit, page_fault, pfn = vm.access_page(vpn)
        tlb_str = f"{CLR_GREEN}HIT{CLR_RESET}" if tlb_hit else f"{CLR_RED}MISS{CLR_RESET}"
        if page_fault:
            pf_str = f"{CLR_RED}PAGE FAULT{CLR_RESET}"
        else:
            pf_str = f"{CLR_GREEN}RAM HIT{CLR_RESET}"

        frames_disp = [f"P{v}" if v is not None else "--" for v in vm.frames]
        print(f"VPN {vpn:<3} | {tlb_str:<19} | {pf_str:<25} | {str(frames_disp):<25}")
        time.sleep(0.08)

    print_success("Simulasi MMU & TLB Selesai. Perhatikan bagaimana LRU mengevikasi halaman terlama.")


# ==============================================================================
# MODUL 2: PREEMPTIVE CPU SCHEDULING (ROUND ROBIN)
# ==============================================================================
@dataclass
class Process:
    pid: str
    burst_time: int
    remaining_time: int
    arrival_time: int
    completion_time: int = 0
    waiting_time: int = 0
    turnaround_time: int = 0


def run_cpu_scheduler_demo() -> None:
    print_banner("SIMULASI 2: CPU PREEMPTIVE SCHEDULING (ROUND ROBIN)")
    quantum = 2
    processes = [
        Process(pid="P1", burst_time=5, remaining_time=5, arrival_time=0),
        Process(pid="P2", burst_time=3, remaining_time=3, arrival_time=1),
        Process(pid="P3", burst_time=2, remaining_time=2, arrival_time=2),
        Process(pid="P4", burst_time=4, remaining_time=4, arrival_time=4),
    ]

    print(f"{CLR_BOLD}Time Quantum:{CLR_RESET} {quantum} unit waktu")
    print(f"{CLR_BOLD}Daftar Proses Awal:{CLR_RESET}")
    for p in processes:
        print(f"  - {CLR_CYAN}{p.pid}{CLR_RESET}: Burst Time = {p.burst_time}, Arrival Time = {p.arrival_time}")
    print()

    current_time = 0
    ready_queue: deque[Process] = deque()
    completed: List[Process] = []
    gantt_log: List[Tuple[str, int, int]] = []
    unstarted = sorted(processes, key=lambda x: x.arrival_time)

    # Tambahkan proses yang tiba pada t=0
    while unstarted and unstarted[0].arrival_time <= current_time:
        ready_queue.append(unstarted.pop(0))

    while ready_queue or unstarted:
        if not ready_queue:
            current_time = unstarted[0].arrival_time
            while unstarted and unstarted[0].arrival_time <= current_time:
                ready_queue.append(unstarted.pop(0))

        curr_proc = ready_queue.popleft()
        exec_time = min(quantum, curr_proc.remaining_time)
        start_t = current_time
        current_time += exec_time
        curr_proc.remaining_time -= exec_time
        gantt_log.append((curr_proc.pid, start_t, current_time))

        # Masukkan proses yang baru tiba saat CPU mengeksekusi
        while unstarted and unstarted[0].arrival_time <= current_time:
            ready_queue.append(unstarted.pop(0))

        if curr_proc.remaining_time > 0:
            ready_queue.append(curr_proc)
        else:
            curr_proc.completion_time = current_time
            curr_proc.turnaround_time = curr_proc.completion_time - curr_proc.arrival_time
            curr_proc.waiting_time = curr_proc.turnaround_time - curr_proc.burst_time
            completed.append(curr_proc)

    # Visualisasi Gantt Chart
    print(f"{CLR_BOLD}Visualisasi Gantt Chart CPU Execution:{CLR_RESET}")
    chart_str = ""
    for pid, s, e in gantt_log:
        chart_str += f"{CLR_MAGENTA}[ {pid} {CLR_GRAY}(t={s}..{e}){CLR_MAGENTA} ]{CLR_RESET} -> "
    print(chart_str + f"{CLR_GREEN}DONE{CLR_RESET}\n")

    # Tabel Metrik
    print(f"{'PID':<6} | {'Arrival':<8} | {'Burst':<6} | {'Finish':<8} | {'Turnaround':<11} | {'Waiting':<8}")
    print("-" * 62)
    total_tat, total_wt = 0, 0
    for p in sorted(completed, key=lambda x: x.pid):
        total_tat += p.turnaround_time
        total_wt += p.waiting_time
        print(f"{CLR_CYAN}{p.pid:<6}{CLR_RESET} | {p.arrival_time:<8} | {p.burst_time:<6} | {p.completion_time:<8} | {p.turnaround_time:<11} | {p.waiting_time:<8}")

    n = len(completed)
    print("-" * 62)
    print(f"{CLR_BOLD}Rata-rata Turnaround Time:{CLR_RESET} {total_tat / n:.2f} unit")
    print(f"{CLR_BOLD}Rata-rata Waiting Time   :{CLR_RESET} {total_wt / n:.2f} unit")


# ==============================================================================
# MODUL 3: L1 DIRECT-MAPPED CACHE SIMULATION
# ==============================================================================
class DirectMappedCache:
    def __init__(self, num_lines: int = 4, block_size: int = 4):
        self.num_lines = num_lines
        self.block_size = block_size
        # Table lines: index -> (valid_bit, tag, data_block)
        self.lines: Dict[int, Tuple[bool, int, List[int]]] = {
            i: (False, -1, []) for i in range(num_lines)
        }

    def access(self, byte_address: int) -> Tuple[bool, int, int, int]:
        block_address = byte_address // self.block_size
        offset = byte_address % self.block_size
        index = block_address % self.num_lines
        tag = block_address // self.num_lines

        valid, stored_tag, _ = self.lines[index]
        if valid and stored_tag == tag:
            is_hit = True
        else:
            is_hit = False
            # Load block from Main Memory
            mock_block = [byte_address - offset + i for i in range(self.block_size)]
            self.lines[index] = (True, tag, mock_block)

        return is_hit, index, tag, offset


def run_cache_demo() -> None:
    print_banner("SIMULASI 3: L1 DIRECT-MAPPED CACHE (SPATIAL & TEMPORAL)")
    cache = DirectMappedCache(num_lines=4, block_size=4)
    memory_addresses = [0x00, 0x01, 0x02, 0x10, 0x00, 0x14, 0x11, 0x20]

    print(f"{CLR_BOLD}Spesifikasi Cache:{CLR_RESET} 4 Cache Lines, Block Size = 4 Bytes")
    print(f"{CLR_BOLD}Alamat Memori (Hex):{CLR_RESET} {[hex(a) for a in memory_addresses]}\n")

    print(f"{'Address':<8} | {'Tag':<5} | {'Index':<6} | {'Offset':<7} | {'Hasil':<15}")
    print("-" * 52)

    hits, misses = 0, 0
    for addr in memory_addresses:
        is_hit, idx, tag, offset = cache.access(addr)
        if is_hit:
            hits += 1
            res_str = f"{CLR_GREEN}CACHE HIT{CLR_RESET}"
        else:
            misses += 1
            res_str = f"{CLR_RED}CACHE MISS{CLR_RESET}"

        print(f"0x{addr:02X}     | {tag:<5} | {idx:<6} | {offset:<7} | {res_str}")
        time.sleep(0.06)

    hit_rate = (hits / len(memory_addresses)) * 100
    print("-" * 52)
    print(f"{CLR_BOLD}Total Akses :{CLR_RESET} {len(memory_addresses)}")
    print(f"{CLR_BOLD}Cache Hits  :{CLR_RESET} {hits} | {CLR_BOLD}Cache Misses:{CLR_RESET} {misses}")
    print(f"{CLR_BOLD}Hit Rate    :{CLR_RESET} {hit_rate:.1f}%")


# ==============================================================================
# MENU UTAMA INTERAKTIF
# ==============================================================================
def display_menu() -> None:
    print(f"\n{CLR_CYAN}{CLR_BOLD}=== MENU LAB INTI COMPUTER SCIENCE (BAB-03) ==={CLR_RESET}")
    print(f"{CLR_YELLOW}1.{CLR_RESET} Jalankan Simulasi Virtual Memory & TLB (LRU)")
    print(f"{CLR_YELLOW}2.{CLR_RESET} Jalankan Simulasi CPU Scheduling (Round Robin)")
    print(f"{CLR_YELLOW}3.{CLR_RESET} Jalankan Simulasi L1 Cache (Direct-Mapped)")
    print(f"{CLR_YELLOW}4.{CLR_RESET} Jalankan Semua Simulasi Sekaligus")
    print(f"{CLR_YELLOW}0.{CLR_RESET} Keluar")
    print(f"{CLR_CYAN}================================================={CLR_RESET}")


def main() -> None:
    # Mode non-interaktif bila argumen terminal diberikan atau bukan tty
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg == "--all":
            run_virtual_memory_demo()
            run_cpu_scheduler_demo()
            run_cache_demo()
            return
        elif arg == "--vm":
            run_virtual_memory_demo()
            return
        elif arg == "--cpu":
            run_cpu_scheduler_demo()
            return
        elif arg == "--cache":
            run_cache_demo()
            return

    # Jika berjalan di lingkungan automated / non-interactive stdin
    if not sys.stdin.isatty():
        print_info("Lingkungan non-interaktif terdeteksi. Menjalankan semua modul uji...")
        run_virtual_memory_demo()
        run_cpu_scheduler_demo()
        run_cache_demo()
        return

    # Loop interaktif
    while True:
        display_menu()
        try:
            choice = input(f"{CLR_BOLD}Pilih opsi [0-4]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break

        if choice == "1":
            run_virtual_memory_demo()
        elif choice == "2":
            run_cpu_scheduler_demo()
        elif choice == "3":
            run_cache_demo()
        elif choice == "4":
            run_virtual_memory_demo()
            run_cpu_scheduler_demo()
            run_cache_demo()
        elif choice == "0":
            print_info("Sesi lab selesai. Sampai jumpa!")
            break
        else:
            print_warn("Pilihan tidak valid. Silakan masukkan angka 0-4.")


if __name__ == "__main__":
    main()

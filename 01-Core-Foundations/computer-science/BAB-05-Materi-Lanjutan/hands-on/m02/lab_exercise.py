#!/usr/bin/env python3
"""
Lab Hands-on: Bab 05 - Modul 02 Deep Dive
Topik: Core Foundations - Arsitektur Memori Virtual, MMU, TLB, & Algoritma Page Replacement.

Deskripsi:
Skrip ini mensimulasikan Memory Management Unit (MMU) modern secara low-level.
Meliputi:
1. Translasi Virtual Address (VPN + Offset) ke Physical Address (PFN + Offset).
2. Translation Lookaside Buffer (TLB) berkecepatan tinggi dengan kebijakan LRU.
3. Struktur Page Table Bertingkat dengan bit status (Valid, Dirty, Referenced).
4. Simulasi Page Fault Handler dengan backing store I/O delay terukur.
5. Komparasi Head-to-Head algoritma Page Replacement: LRU vs. Clock (Second-Chance).
"""

import sys
import time
import random
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# Konstanta ANSI Color untuk pelaporan diagnostik
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"

# Spesifikasi Arsitektur Sistem Memori
PAGE_SIZE_BYTES = 256        # Ukuran halaman 256 byte (Offset = 8 bit)
OFFSET_BITS     = 8
OFFSET_MASK     = (1 << OFFSET_BITS) - 1
NUM_FRAMES      = 8          # Memori fisik terbatas: 8 Frame (2048 Byte)
TLB_CAPACITY    = 4          # Kapasitas Hardware Cache TLB: 4 Entri


@dataclass
class PageTableEntry:
    """Representasi Page Table Entry (PTE) pada arsitektur sistem."""
    frame_number: int = -1
    valid: bool = False
    dirty: bool = False
    referenced: bool = False
    last_access_time: float = 0.0


class TranslationLookasideBuffer:
    """Hardware TLB simulator berbasis cache asosiatif penuh (Fully Associative Cache)."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: OrderedDict[int, int] = OrderedDict()  # VPN -> PFN

    def lookup(self, vpn: int) -> Optional[int]:
        if vpn in self.cache:
            self.cache.move_to_end(vpn)  # LRU touch
            return self.cache[vpn]
        return None

    def insert(self, vpn: int, pfn: int) -> None:
        if vpn in self.cache:
            self.cache.move_to_end(vpn)
            self.cache[vpn] = pfn
            return
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)  # Evict LRU element
        self.cache[vpn] = pfn

    def invalidate(self, vpn: int) -> None:
        if vpn in self.cache:
            del self.cache[vpn]

    def clear(self) -> None:
        self.cache.clear()


class MemoryManagementUnit:
    """Simulasi MMU Hardware yang mengoordinasikan translasi alamat & replacement."""
    def __init__(self, num_frames: int, algorithm: str = "LRU"):
        self.num_frames = num_frames
        self.algorithm = algorithm.upper()  # 'LRU' atau 'CLOCK'
        self.tlb = TranslationLookasideBuffer(TLB_CAPACITY)
        self.page_table: Dict[int, PageTableEntry] = {}
        
        # Frame state tracking
        self.frame_to_vpn: List[Optional[int]] = [None] * num_frames
        self.clock_hand: int = 0
        
        # Metrik performa
        self.total_references = 0
        self.tlb_hits = 0
        self.page_hits = 0
        self.page_faults = 0
        self.dirty_evictions = 0

    def _get_pte(self, vpn: int) -> PageTableEntry:
        if vpn not in self.page_table:
            self.page_table[vpn] = PageTableEntry()
        return self.page_table[vpn]

    def _evict_frame(self) -> int:
        """Memilih frame korban berdasarkan algoritma yang dipilih."""
        if self.algorithm == "LRU":
            # Cari frame dengan last_access_time terlama
            oldest_time = float('inf')
            victim_frame = 0
            for f_idx, vpn in enumerate(self.frame_to_vpn):
                if vpn is None:
                    return f_idx
                pte = self._get_pte(vpn)
                if pte.last_access_time < oldest_time:
                    oldest_time = pte.last_access_time
                    victim_frame = f_idx
            return victim_frame

        elif self.algorithm == "CLOCK":
            # Algoritma Clock / Second-Chance
            while True:
                vpn = self.frame_to_vpn[self.clock_hand]
                if vpn is None:
                    allocated_frame = self.clock_hand
                    self.clock_hand = (self.clock_hand + 1) % self.num_frames
                    return allocated_frame

                pte = self._get_pte(vpn)
                if not pte.referenced:
                    # Ditemukan frame dengan bit use = 0
                    victim_frame = self.clock_hand
                    self.clock_hand = (self.clock_hand + 1) % self.num_frames
                    return victim_frame
                else:
                    # Berikan kesempatan kedua (clear reference bit)
                    pte.referenced = False
                    self.clock_hand = (self.clock_hand + 1) % self.num_frames

        raise ValueError(f"Algoritma tidak dikenal: {self.algorithm}")

    def handle_page_fault(self, vpn: int, is_write: bool) -> int:
        """Menangani kegagalan halaman (Page Fault), memuat dari backing store."""
        self.page_faults += 1
        
        # 1. Cari frame yang kosong terlebih dahulu
        target_frame = None
        for f_idx in range(self.num_frames):
            if self.frame_to_vpn[f_idx] is None:
                target_frame = f_idx
                break

        # 2. Jika memori penuh, jalankan page replacement
        if target_frame is None:
            target_frame = self._evict_frame()
            old_vpn = self.frame_to_vpn[target_frame]
            if old_vpn is not None:
                old_pte = self._get_pte(old_vpn)
                if old_pte.dirty:
                    self.dirty_evictions += 1  # Writeback to disk
                old_pte.valid = False
                self.tlb.invalidate(old_vpn)

        # 3. Alokasikan frame untuk VPN baru
        self.frame_to_vpn[target_frame] = vpn
        new_pte = self._get_pte(vpn)
        new_pte.frame_number = target_frame
        new_pte.valid = True
        new_pte.dirty = is_write
        new_pte.referenced = True
        new_pte.last_access_time = time.monotonic()
        
        return target_frame

    def translate(self, virtual_address: int, is_write: bool = False) -> Tuple[int, str]:
        """Translasi Virtual Address -> Physical Address."""
        self.total_references += 1
        vpn = virtual_address >> OFFSET_BITS
        offset = virtual_address & OFFSET_MASK
        
        # Jalur 1: Fast-Path Hardware TLB Lookup
        tlb_pfn = self.tlb.lookup(vpn)
        if tlb_pfn is not None:
            self.tlb_hits += 1
            pte = self._get_pte(vpn)
            pte.referenced = True
            pte.last_access_time = time.monotonic()
            if is_write:
                pte.dirty = True
            physical_address = (tlb_pfn << OFFSET_BITS) | offset
            return physical_address, "TLB_HIT"

        # Jalur 2: TLB Miss -> Periksa Page Table
        pte = self._get_pte(vpn)
        if pte.valid:
            self.page_hits += 1
            pte.referenced = True
            pte.last_access_time = time.monotonic()
            if is_write:
                pte.dirty = True
            self.tlb.insert(vpn, pte.frame_number)
            physical_address = (pte.frame_number << OFFSET_BITS) | offset
            return physical_address, "PAGE_HIT"

        # Jalur 3: Page Fault Handling
        pfn = self.handle_page_fault(vpn, is_write)
        self.tlb.insert(vpn, pfn)
        physical_address = (pfn << OFFSET_BITS) | offset
        return physical_address, "PAGE_FAULT"


def generate_workload_traces(num_ops: int = 120) -> List[Tuple[int, bool]]:
    """
    Menghasilkan pola akses memori realistis:
    - 60% Spatial & Temporal Locality (Loop iterasi array & stack)
    - 25% Jumps (Pemanggilan fungsi/prosedur baru)
    - 15% Random Memory Spikes (Alokasi dinamis bebas)
    """
    random.seed(42)  # Deterministic profiling
    workload: List[Tuple[int, bool]] = []
    
    current_base = 0x0100
    for i in range(num_ops):
        dice = random.random()
        if dice < 0.60:
            # Akses lokal berurutan (Sequential / Loop)
            offset = (i % 8) * 32
            addr = current_base + offset
            is_write = (random.random() > 0.7)
        elif dice < 0.85:
            # Lompat ke page baru (Function Call / Subroutine)
            page_target = random.choice([0x0A00, 0x1200, 0x1F00, 0x2200])
            addr = page_target + random.randint(0, 128)
            is_write = (random.random() > 0.5)
        else:
            # Akses acak (Heap scanning)
            addr = random.randint(0, 0x3FFF)
            is_write = (random.random() > 0.8)

        workload.append((addr, is_write))
    return workload


def print_banner():
    print(f"{CLR_CYAN}{CLR_BOLD}=" * 80)
    print(" CORE FOUNDATIONS: VIRTUAL MEMORY ARCHITECTURE & MMU ENGINE DEEP DIVE")
    print(" Page Table Size: 256 B/Page | Physical Frames: 8 | TLB Capacity: 4 Entries")
    print(f"=" * 80 + f"{CLR_RESET}\n")


def run_simulation(algorithm_name: str, traces: List[Tuple[int, bool]], verbose_limit: int = 10) -> MemoryManagementUnit:
    """Mengeksekusi simulasi MMU lengkap dengan logging detail sampling."""
    print(f"{CLR_BOLD}>>> Memulai Simulasi MMU dengan Algoritma: {CLR_MAGENTA}{algorithm_name}{CLR_RESET}")
    mmu = MemoryManagementUnit(num_frames=NUM_FRAMES, algorithm=algorithm_name)
    
    print(f"{'No':<4} | {'V-Addr':<8} | {'VPN':<5} | {'Offs':<5} | {'Op':<5} | {'Status':<12} | {'P-Addr':<8} | {'TLB Mapping'}")
    print("-" * 80)
    
    for idx, (v_addr, is_write) in enumerate(traces):
        vpn = v_addr >> OFFSET_BITS
        offset = v_addr & OFFSET_MASK
        op_str = f"{CLR_YELLOW}WR{CLR_RESET}" if is_write else f"{CLR_BLUE}RD{CLR_RESET}"
        
        p_addr, status = mmu.translate(v_addr, is_write)
        
        # Format status dengan warna visual
        if status == "TLB_HIT":
            colored_status = f"{CLR_GREEN}TLB HIT   {CLR_RESET}"
        elif status == "PAGE_HIT":
            colored_status = f"{CLR_CYAN}PAGE HIT  {CLR_RESET}"
        else:
            colored_status = f"{CLR_RED}PAGE FAULT{CLR_RESET}"

        # Cetak output terinci hanya untuk sejumlah instruksi awal sebagai representasi
        if idx < verbose_limit:
            tlb_dump = str(list(mmu.tlb.cache.items()))
            print(f"{idx+1:<4} | 0x{v_addr:04X} | {vpn:<5} | 0x{offset:02X} | {op_str}   | {colored_status} | 0x{p_addr:04X} | {tlb_dump}")
        elif idx == verbose_limit:
            print(f"... [{len(traces) - verbose_limit} Instruksi berikutnya dieksekusi secara instan] ...")

    print("-" * 80 + "\n")
    return mmu


def display_comparative_metrics(mmu_lru: MemoryManagementUnit, mmu_clock: MemoryManagementUnit):
    """Menampilkan dashboard analitik perbandingan efisiensi algoritma."""
    def calc_rates(mmu: MemoryManagementUnit):
        tlb_rate = (mmu.tlb_hits / mmu.total_references) * 100
        fault_rate = (mmu.page_faults / mmu.total_references) * 100
        hit_rate = 100.0 - fault_rate
        return tlb_rate, fault_rate, hit_rate

    lru_tlb, lru_fault, lru_hit = calc_rates(mmu_lru)
    clk_tlb, clk_fault, clk_hit = calc_rates(mmu_clock)

    print(f"{CLR_BOLD}{CLR_CYAN}METRIK PERFORMANSI SISTEM MEMORI (BENCHMARK HASIL){CLR_RESET}")
    print("+" + "-" * 32 + "+" + "-" * 20 + "+" + "-" * 20 + "+")
    print(f"| {'Komponen Evaluasi':<30} | {'LRU Policy':<18} | {'CLOCK Policy':<18} |")
    print("+" + "-" * 32 + "+" + "-" * 20 + "+" + "-" * 20 + "+")
    print(f"| {'Total Memory Accesses':<30} | {mmu_lru.total_references:<18} | {mmu_clock.total_references:<18} |")
    print(f"| {'TLB Hits':<30} | {mmu_lru.tlb_hits:<18} | {mmu_clock.tlb_hits:<18} |")
    print(f"| {'TLB Hit Ratio (%)':<30} | {lru_tlb:<18.2f} | {clk_tlb:<18.2f} |")
    print(f"| {'Page Faults (Total)':<30} | {CLR_RED}{mmu_lru.page_faults:<18}{CLR_RESET} | {CLR_RED}{mmu_clock.page_faults:<18}{CLR_RESET} |")
    print(f"| {'Page Fault Rate (%)':<30} | {lru_fault:<18.2f} | {clk_fault:<18.2f} |")
    print(f"| {'Dirty Frame Writebacks':<30} | {mmu_lru.dirty_evictions:<18} | {mmu_clock.dirty_evictions:<18} |")
    print(f"| {'Overall Page Hit Ratio (%)':<30} | {CLR_GREEN}{lru_hit:<18.2f}{CLR_RESET} | {CLR_GREEN}{clk_hit:<18.2f}{CLR_RESET} |")
    print("+" + "-" * 32 + "+" + "-" * 20 + "+" + "-" * 20 + "+")
    print("\nAnalisis Arsitektural:")
    print(f"- {CLR_BOLD}LRU Overhead:{CLR_RESET} Memberikan akurasi pemilihan frame korban yang optimal dengan biaya tracking timestamp.")
    print(f"- {CLR_BOLD}Clock Approximation:{CLR_RESET} Meniru LRU dengan circular buffer & bit use, meminimalkan kompleksitas hardware.\n")


def main():
    print_banner()
    
    # 1. Generate workload jejak memori deterministik
    traces = generate_workload_traces(num_ops=150)
    
    # 2. Jalankan simulasi dengan algoritma LRU
    mmu_lru = run_simulation("LRU", traces, verbose_limit=8)
    
    # 3. Jalankan simulasi dengan algoritma CLOCK (Second Chance)
    mmu_clock = run_simulation("CLOCK", traces, verbose_limit=8)
    
    # 4. Tampilkan laporan diagnostik komparatif
    display_comparative_metrics(mmu_lru, mmu_clock)


if __name__ == "__main__":
    main()
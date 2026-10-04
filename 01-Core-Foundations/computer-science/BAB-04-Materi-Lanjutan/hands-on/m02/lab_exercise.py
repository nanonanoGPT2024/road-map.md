#!/usr/bin/env python3
"""
Lab Hands-on: CS Core Foundations - Bab 04 Modul 02
Topik: Virtual Memory Architecture & Memory Management Unit (MMU) Simulator
Implementasi: TLB (Translation Lookaside Buffer), Multi-Level Paging, & Page Replacement (LRU)
"""

import sys
import time
from dataclasses import dataclass, field
from collections import OrderedDict
from typing import Optional, Tuple

# ANSI Colors untuk output visual terminal
CLR_RESET  = "\033[0m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"
CLR_MAG    = "\033[95m"
CLR_BOLD   = "\033[1m"


@dataclass
class PageTableEntry:
    """Representasi Page Table Entry (PTE) pada arsitektur hardware x86/ARM."""
    frame_number: int = -1
    valid: bool = False
    dirty: bool = False
    referenced: bool = False
    read_only: bool = False


@dataclass
class MemoryMetrics:
    """Metrik observabilitas performa MMU."""
    total_accesses: int = 0
    tlb_hits: int = 0
    tlb_misses: int = 0
    page_faults: int = 0
    disk_writes: int = 0
    simulated_latency_ns: int = 0


class TranslationLookasideBuffer:
    """
    Simulasi hardware associative cache (TLB) berkapasitas kecil berkecepatan tinggi.
    Menggunakan replacement policy Least Recently Used (LRU) melalui OrderedDict.
    """
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.entries: OrderedDict[int, int] = OrderedDict()  # VPN -> PFN

    def lookup(self, vpn: int) -> Optional[int]:
        """Lookup virtual page number. Operasi hardware setara 1 siklus CPU."""
        if vpn in self.entries:
            self.entries.move_to_end(vpn)
            return self.entries[vpn]
        return None

    def insert(self, vpn: int, pfn: int) -> None:
        """Memasukkan mapping baru ke TLB, meng-evict LRU jika penuh."""
        if vpn in self.entries:
            self.entries.move_to_end(vpn)
        else:
            if len(self.entries) >= self.capacity:
                self.entries.popitem(last=False)  # Evict LRU
        self.entries[vpn] = pfn

    def invalidate(self, vpn: int) -> None:
        """TLB shootdown / invalidation ketika halaman dievicted dari DRAM."""
        if vpn in self.entries:
            del self.entries[vpn]


class MemoryManagementUnit:
    """
    MMU yang mengkoordinasikan translasi Virtual Address ke Physical Address,
    menghandle Page Fault, dan manajemen Physical Frame Allocation.
    """
    def __init__(self, page_size: int = 256, num_physical_frames: int = 4, tlb_size: int = 4):
        self.page_size = page_size
        self.num_physical_frames = num_physical_frames
        
        # Konfigurasi Latensi Siklus Hardware (Nanodetik)
        self.LATENCY_TLB_HIT_NS = 1
        self.LATENCY_DRAM_ACCESS_NS = 50
        self.LATENCY_PAGE_FAULT_NS = 5_000_000  # Disk I/O cost

        self.tlb = TranslationLookasideBuffer(capacity=tlb_size)
        self.page_table: dict[int, PageTableEntry] = {}
        
        # Tracking frame fisik: Frame ID -> VPN
        self.physical_frames: list[Optional[int]] = [None] * num_physical_frames
        self.lru_tracker: OrderedDict[int, bool] = OrderedDict()  # Frame tracking untuk replacement
        self.metrics = MemoryMetrics()

    def _get_vpn_and_offset(self, virtual_address: int) -> Tuple[int, int]:
        """Dekomposisi virtual address menjadi Virtual Page Number (VPN) dan Page Offset."""
        vpn = virtual_address // self.page_size
        offset = virtual_address % self.page_size
        return vpn, offset

    def _allocate_frame(self, vpn: int) -> int:
        """
        Alokasi physical frame. Jika memori fisik habis, eksekusi Page Replacement (LRU).
        """
        # Cek apakah ada frame kosong
        for pfn in range(self.num_physical_frames):
            if self.physical_frames[pfn] is None:
                self.physical_frames[pfn] = vpn
                self.lru_tracker[pfn] = True
                return pfn

        # Out of physical memory: Lakukan Eviction terhadap LRU frame
        victim_pfn, _ = self.lru_tracker.popitem(last=False)
        victim_vpn = self.physical_frames[victim_pfn]
        victim_pte = self.page_table[victim_vpn]

        print(f"    {CLR_YELLOW}[PAGE EVIC] Out of DRAM! Evicting PFN={victim_pfn} (Milik VPN={victim_vpn}){CLR_RESET}")

        # Jika dirty bit aktif, harus disinkronkan kembali ke storage (Swap/Disk write)
        if victim_pte.dirty:
            self.metrics.disk_writes += 1
            print(f"    {CLR_MAG}[SWAP WRITE] VPN={victim_vpn} dirty -> Memflushing ke Disk.{CLR_RESET}")

        # Invalidasi TLB dan PTE
        victim_pte.valid = False
        victim_pte.frame_number = -1
        victim_pte.dirty = False
        self.tlb.invalidate(victim_vpn)

        # Re-assign frame ke halaman baru
        self.physical_frames[victim_pfn] = vpn
        self.lru_tracker[victim_pfn] = True
        return victim_pfn

    def access_memory(self, virtual_address: int, is_write: bool = False, payload: str = "") -> int:
        """
        Alur translasi memori penuh:
        1. Query TLB (Hit: selesai cepat, Miss: translasi lewat Page Table).
        2. Cek Validitas PTE di Page Table.
        3. Jika Invalid -> Trigger Hardware Interrupt (Page Fault Exception).
        4. Swap-in dari storage/alokasi frame, update PTE dan update TLB.
        5. Return computed Physical Address.
        """
        self.metrics.total_accesses += 1
        vpn, offset = self._get_vpn_and_offset(virtual_address)
        op_label = f"{CLR_RED}WRITE{CLR_RESET}" if is_write else f"{CLR_CYAN}READ {CLR_RESET}"
        
        print(f"\n{CLR_BOLD}--> Access [{op_label}] V-Addr: {virtual_address:04d} (VPN: {vpn}, Offset: {offset}){CLR_RESET}")

        # Tahap 1: Evaluasi TLB (Fast Path)
        pfn = self.tlb.lookup(vpn)
        if pfn is not None:
            self.metrics.tlb_hits += 1
            self.metrics.simulated_latency_ns += self.LATENCY_TLB_HIT_NS
            print(f"  [{CLR_GREEN}TLB HIT{CLR_RESET}] VPN={vpn} -> PFN={pfn} (+{self.LATENCY_TLB_HIT_NS}ns)")
        else:
            # Tahap 2: Evaluasi Page Table (Slow Path)
            self.metrics.tlb_misses += 1
            self.metrics.simulated_latency_ns += self.LATENCY_DRAM_ACCESS_NS
            print(f"  [{CLR_RED}TLB MISS{CLR_RESET}] Membaca Page Table di DRAM (+{self.LATENCY_DRAM_ACCESS_NS}ns)")

            if vpn not in self.page_table:
                self.page_table[vpn] = PageTableEntry()

            pte = self.page_table[vpn]

            # Tahap 3: Deteksi Page Fault
            if not pte.valid:
                self.metrics.page_faults += 1
                self.metrics.simulated_latency_ns += self.LATENCY_PAGE_FAULT_NS
                print(f"  [{CLR_RED}PAGE FAULT{CLR_RESET}] VPN={vpn} tidak ada di DRAM! Handler OS Disk-Fetch (+{self.LATENCY_PAGE_FAULT_NS:,}ns)")
                
                # Fetch frame baru via Page Replacement
                pfn = self._allocate_frame(vpn)
                pte.frame_number = pfn
                pte.valid = True
            else:
                pfn = pte.frame_number

            # Update TLB dengan mapping yang berhasil ditranslasikan
            self.tlb.insert(vpn, pfn)

        # Update status Frame dan PTE
        pte = self.page_table[vpn]
        pte.referenced = True
        if is_write:
            pte.dirty = True

        # Refresh LRU queue untuk physical frame
        if pfn in self.lru_tracker:
            self.lru_tracker.move_to_end(pfn)

        physical_address = (pfn * self.page_size) + offset
        print(f"  {CLR_GREEN}==> Translasi Berhasil! P-Addr: {physical_address:04d} [Frame: {pfn}, Offset: {offset}]{CLR_RESET}")
        return physical_address

    def print_diagnostics(self) -> None:
        """Cetak status memory layout dan kalkulasi metrik latensi."""
        print(f"\n{CLR_BOLD}{'='*60}")
        print(f"       MMU RUNTIME SUMMARY & BENCHMARK METRICS")
        print(f"{'='*60}{CLR_RESET}")
        
        hit_ratio = (self.metrics.tlb_hits / self.metrics.total_accesses) * 100 if self.metrics.total_accesses else 0
        pf_ratio = (self.metrics.page_faults / self.metrics.total_accesses) * 100 if self.metrics.total_accesses else 0
        amat = self.metrics.simulated_latency_ns / self.metrics.total_accesses if self.metrics.total_accesses else 0

        print(f"Total Instruksi Memori : {self.metrics.total_accesses}")
        print(f"TLB Hits               : {CLR_GREEN}{self.metrics.tlb_hits}{CLR_RESET}")
        print(f"TLB Misses             : {CLR_RED}{self.metrics.tlb_misses}{CLR_RESET}")
        print(f"TLB Hit Ratio          : {CLR_GREEN}{hit_ratio:.2f}%{CLR_RESET}")
        print(f"Page Faults            : {CLR_RED}{self.metrics.page_faults}{CLR_RESET} ({pf_ratio:.2f}%)")
        print(f"Swap/Disk Writeback    : {CLR_MAG}{self.metrics.disk_writes}{CLR_RESET}")
        print(f"Total Simulated Latency: {self.metrics.simulated_latency_ns:,} ns")
        print(f"Average Memory Access  : {CLR_BOLD}{amat:,.2f} ns (AMAT){CLR_RESET}")

        print(f"\n{CLR_CYAN}Current Physical Frame State:{CLR_RESET}")
        for pfn, vpn in enumerate(self.physical_frames):
            status = f"VPN: {vpn}" if vpn is not None else "EMPTY"
            dirty_flag = " [DIRTY]" if vpn is not None and self.page_table[vpn].dirty else ""
            print(f"  Frame [{pfn}]: {status}{dirty_flag}")
        print(f"{CLR_BOLD}{'='*60}{CLR_RESET}\n")


def execute_lab_simulation():
    """
    Mensimulasikan pola akses memori realistis:
    1. Spatial Locality (Sequential access dalam satu halaman)
    2. Temporal Locality (Re-accessing recent addresses)
    3. Memory Pressure / Thrashing (Mengakses variasi halaman lebih banyak dari ukuran DRAM)
    """
    print(f"{CLR_BOLD}{CLR_BLUE}Starting Virtual Memory Subsystem Simulation...{CLR_RESET}")
    print("Konfigurasi Hardware:")
    print("  - Ukuran Halaman (Page Size)     : 256 Bytes")
    print("  - Physical DRAM Capacity         : 4 Frames (1024 Bytes Total)")
    print("  - TLB Cache Size                 : 3 Entries")
    print("  - Latency Constants: TLB Hit=1ns, DRAM Access=50ns, Disk Fault=5,000,000ns")

    # Inisialisasi MMU: PageSize=256B, DRAM=4 Frames, TLB=3 Entries
    mmu = MemoryManagementUnit(page_size=256, num_physical_frames=4, tlb_size=3)

    workload = [
        # Fase 1: Cold start & Spatial locality (Halaman 0)
        (0x0010, False),  # VPN 0: Page Fault awal
        (0x0040, True),   # VPN 0: TLB Hit (Spatial Locality)
        (0x0080, False),  # VPN 0: TLB Hit

        # Fase 2: Alokasi Halaman Baru (VPN 1, 2, 3) - Memenuhi seluruh 4 frame fisik
        (0x0110, False),  # VPN 1: Page Fault
        (0x0210, True),   # VPN 2: Page Fault
        (0x0310, True),   # VPN 3: Page Fault (Physical memory penuh!)

        # Fase 3: TLB Thrashing dan Temporal Access
        (0x0020, False),  # VPN 0: TLB Miss (dievict dari TLB sebelumnya), tapi Page Hit di DRAM
        
        # Fase 4: Page Eviction & Swap Writing (Kapasitas DRAM terlampaui)
        (0x0410, False),  # VPN 4: Page Fault! Harus meng-evict salah satu frame via LRU
        (0x0510, True),   # VPN 5: Page Fault! Eviction berikutnya, writeback jika dirty
        (0x0120, False),  # VPN 1: Mengakses kembali halaman yang kemungkinan sudah di-swap
    ]

    for vaddr, is_write in workload:
        mmu.access_memory(virtual_address=vaddr, is_write=is_write)
        time.sleep(0.02)  # Delay simulasi untuk kestabilan visual

    # Tampilkan diagnostik akhir
    mmu.print_diagnostics()


if __name__ == "__main__":
    execute_lab_simulation()
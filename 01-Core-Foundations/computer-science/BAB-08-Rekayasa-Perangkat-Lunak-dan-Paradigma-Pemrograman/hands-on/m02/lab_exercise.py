#!/usr/bin/env python3
"""
Lab Hands-on: Core Foundations - Virtual Memory Management & Multi-Level Paging Simulation
Topik: Computer Science (01-Core-Foundations) - Bab 08: Storage & Virtual Memory Architectures

Simulasi arsitektur Memory Management Unit (MMU) modern mencakup:
1. Virtual Address Translation (32-bit: Directory -> Page Table -> Offset)
2. Hardware Translation Lookaside Buffer (TLB) dengan kebijakan LRU
3. Two-Level Hierarchical Page Table (Sparse Allocation)
4. Demand Paging & Page Fault Handling
5. Physical Memory Frame Allocation & LRU Page Replacement Engine
"""

import sys
import time
import random
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

# ANSI Color Codes untuk visualisasi terminal
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_DIM    = "\033[2m"
C_RED    = "\033[91m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE   = "\033[94m"
C_MAG    = "\033[95m"
C_CYAN   = "\033[96m"

# Konfigurasi Arsitektur Memori 32-bit
# Page Size: 4 KiB (12-bit offset)
# Page Directory (Level 1): 10-bit
# Page Table (Level 2): 10-bit
OFFSET_BITS = 12
PAGE_SIZE   = 1 << OFFSET_BITS        # 4096 bytes
TABLE_BITS  = 10
DIR_BITS    = 10

PAGE_MASK   = PAGE_SIZE - 1
INDEX_MASK  = (1 << TABLE_BITS) - 1

# Latensi Hardware Teoritis (Nanoseconds)
LATENCY_TLB_HIT   = 1       # Akses SRAM pada CPU Core
LATENCY_RAM_READ  = 50      # Akses Main Memory (DRAM Bus)
LATENCY_PAGE_FAULT = 5000   # Disk I/O & Interrupt Trapping


@dataclass
class PageTableEntry:
    """Mewakili 1 entri pada Page Table (PTE)."""
    pfn: int = -1             # Physical Frame Number
    valid: bool = False       # Present bit
    dirty: bool = False       # Modified bit
    referenced: bool = False  # Accessed bit


@dataclass
class FrameMetadata:
    """Informasi alokasi Physical Frame dalam DRAM."""
    vpn: int = -1
    allocated: bool = False


class TranslationLookasideBuffer:
    """Simulasi TLB Cache ter-asosiasi penuh dengan LRU eviction."""
    def __init__(self, capacity: int = 8):
        self.capacity = capacity
        self.cache: OrderedDict[int, int] = OrderedDict()  # vpn -> pfn

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
            self.cache.popitem(last=False)  # Evict Least Recently Used
        self.cache[vpn] = pfn

    def invalidate(self, vpn: int) -> None:
        if vpn in self.cache:
            del self.cache[vpn]


class VirtualMemoryManager:
    """
    Sub-sistem MMU lengkap yang mengelola:
    - 2-Level Page Tables
    - TLB
    - Physical Frame Allocation & Eviction (LRU Replacement)
    - Backing Store (Swap Disk)
    """
    def __init__(self, physical_frames_count: int = 16, tlb_size: int = 8):
        self.num_frames = physical_frames_count
        self.frames: List[FrameMetadata] = [FrameMetadata() for _ in range(self.num_frames)]
        self.frame_lru: OrderedDict[int, None] = OrderedDict()  # pfn tracking
        
        # Two-Level Page Table: Directory Index -> Page Table Index -> PTE
        self.page_directory: Dict[int, Dict[int, PageTableEntry]] = {}
        self.backing_store: Dict[int, bytes] = {}  # vpn -> swapped data
        
        self.tlb = TranslationLookasideBuffer(capacity=tlb_size)
        
        # Metrik performa
        self.total_accesses = 0
        self.tlb_hits = 0
        self.page_faults = 0
        self.total_latency_ns = 0

    def _split_vaddr(self, vaddr: int) -> Tuple[int, int, int, int]:
        """Memecah alamat virtual 32-bit menjadi VPN1, VPN2, Offset, dan Global VPN."""
        offset = vaddr & PAGE_MASK
        vpn = vaddr >> OFFSET_BITS
        vpn2 = vpn & INDEX_MASK
        vpn1 = (vpn >> TABLE_BITS) & INDEX_MASK
        return vpn1, vpn2, offset, vpn

    def _allocate_physical_frame(self, target_vpn: int) -> int:
        """Mencari physical frame kosong atau melakukan page replacement via LRU."""
        # Cari frame kosong
        for pfn in range(self.num_frames):
            if not self.frames[pfn].allocated:
                self.frames[pfn].allocated = True
                self.frames[pfn].vpn = target_vpn
                self.frame_lru[pfn] = None
                return pfn

        # Jika memori penuh, jalankan LRU Page Replacement
        evict_pfn, _ = self.frame_lru.popitem(last=False)
        evicted_vpn = self.frames[evict_pfn].vpn

        # Sinkronisasi PTE dari halaman yang ditendang
        e_vpn1 = (evicted_vpn >> TABLE_BITS) & INDEX_MASK
        e_vpn2 = evicted_vpn & INDEX_MASK
        old_pte = self.page_directory[e_vpn1][e_vpn2]
        
        if old_pte.dirty:
            # Simulasi write-back ke backing store
            self.backing_store[evicted_vpn] = b"[DIRTY_DATA_SYNCED]"
        
        old_pte.valid = False
        old_pte.pfn = -1
        self.tlb.invalidate(evicted_vpn)

        # Tetapkan frame ke VPN baru
        self.frames[evict_pfn].vpn = target_vpn
        self.frame_lru[evict_pfn] = None
        return evict_pfn

    def _handle_page_fault(self, vpn1: int, vpn2: int, vpn: int) -> int:
        """ISR (Interrupt Service Routine) untuk Page Fault."""
        self.page_faults += 1
        self.total_latency_ns += LATENCY_PAGE_FAULT

        # Alokasikan frame dari pool fisik
        pfn = self._allocate_physical_frame(vpn)

        # Perbarui PTE
        pte = self.page_directory[vpn1][vpn2]
        pte.pfn = pfn
        pte.valid = True
        pte.referenced = True

        # Ambil payload jika tersedia pada swap backing store
        _ = self.backing_store.get(vpn, b"\x00" * PAGE_SIZE)
        return pfn

    def access_memory(self, vaddr: int, is_write: bool = False) -> Tuple[int, str]:
        """
        Menjalankan translasi memori end-to-end:
        1. Probe TLB
        2. Walk Page Table (Level 1 & Level 2)
        3. Trigger Fault jika tidak valid
        4. Bentuk Physical Address
        """
        self.total_accesses += 1
        vpn1, vpn2, offset, vpn = self._split_vaddr(vaddr)

        # 1. Cek TLB Cache (Fast Path)
        pfn = self.tlb.lookup(vpn)
        if pfn is not None:
            self.tlb_hits += 1
            self.total_latency_ns += LATENCY_TLB_HIT
            self.frame_lru.move_to_end(pfn)
            paddr = (pfn << OFFSET_BITS) | offset
            return paddr, "TLB_HIT"

        # 2. TLB Miss: Lakukan Page Table Walk (Slow Path)
        self.total_latency_ns += (LATENCY_RAM_READ * 2)  # Level 1 + Level 2 Table lookup

        if vpn1 not in self.page_directory:
            self.page_directory[vpn1] = {}

        if vpn2 not in self.page_directory[vpn1]:
            self.page_directory[vpn1][vpn2] = PageTableEntry()

        pte = self.page_directory[vpn1][vpn2]

        # 3. Validasi Keberadaan Halaman di Memori Fisik
        status = "PT_HIT"
        if not pte.valid:
            pfn = self._handle_page_fault(vpn1, vpn2, vpn)
            status = "PAGE_FAULT"
        else:
            pfn = pte.pfn
            self.frame_lru.move_to_end(pfn)

        if is_write:
            pte.dirty = True
        pte.referenced = True

        # 4. Update TLB untuk akses berikutnya
        self.tlb.insert(vpn, pfn)
        paddr = (pfn << OFFSET_BITS) | offset
        return paddr, status


def run_workload_simulation():
    """Menjalankan trace benchmarking beban akses memori nyata."""
    print(f"{C_BOLD}{C_CYAN}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  SIMULASI HARDWARE MEMORY MANAGEMENT UNIT (MMU) & VIRTUAL PAGING     {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}======================================================================{C_RESET}\n")

    mmu = VirtualMemoryManager(physical_frames_count=8, tlb_size=4)

    print(f"{C_YELLOW}[CONFIG]{C_RESET} DRAM Physical Frames: {mmu.num_frames} ({mmu.num_frames * 4} KiB)")
    print(f"{C_YELLOW}[CONFIG]{C_RESET} TLB Cache Capacity   : {mmu.tlb.capacity} Entries")
    print(f"{C_YELLOW}[CONFIG]{C_RESET} Page Size            : {PAGE_SIZE} Bytes (12-bit offset)")
    print(f"{C_YELLOW}[CONFIG]{C_RESET} Table Architecture   : 2-Level Multi-Level Hierarchical\n")

    # Pola Akses: Temporal Locality (looping), Spatial Locality (sequential), & Random Thrashing
    workload = []
    
    # Fase 1: Spatial Locality (Sequential access streaming)
    base_addr = 0x00400000  # .text / code segment
    for i in range(16):
        workload.append((base_addr + (i * 1024), False, "Loop Execution (Spatial)"))

    # Fase 2: Temporal Locality (Akses berulang pada working set kecil)
    stack_addr = 0x7FFF0000  # Stack memory
    for _ in range(8):
        offset = random.choice([0x00, 0x20, 0x40, 0x1000])
        workload.append((stack_addr + offset, True, "Stack Push/Pop (Temporal)"))

    # Fase 3: Heap Allocation & Thrashing (Memaksa eviksi DRAM dan Page Fault cascade)
    heap_base = 0x10000000
    for i in range(12):
        workload.append((heap_base + (i * 4096), True, "Heap Alloc (Sparse Thrash)"))

    print(f"{C_BOLD}{'VIRTUAL ADDR':<14} {'VPN1':<6} {'VPN2':<6} {'OFFSET':<8} -> {'PHYS ADDR':<12} {'STATUS':<12} {'LATENCY'}{C_RESET}")
    print(f"{C_DIM}{'-'*75}{C_RESET}")

    for vaddr, is_write, tag in workload:
        vpn1, vpn2, offset, _ = mmu._split_vaddr(vaddr)
        t_start = time.perf_counter_ns()
        paddr, status = mmu.access_memory(vaddr, is_write=is_write)
        elapsed = time.perf_counter_ns() - t_start

        if status == "TLB_HIT":
            status_str = f"{C_GREEN}[TLB HIT]{C_RESET}"
            lat_str = f"{LATENCY_TLB_HIT} ns"
        elif status == "PT_HIT":
            status_str = f"{C_YELLOW}[PT HIT]{C_RESET}"
            lat_str = f"{LATENCY_RAM_READ * 2} ns"
        else:
            status_str = f"{C_RED}[FAULT]{C_RESET} "
            lat_str = f"{LATENCY_PAGE_FAULT} ns"

        print(f"0x{vaddr:08X}   0x{vpn1:03X}  0x{vpn2:03X}  0x{offset:03X}    -> 0x{paddr:08X}   {status_str:<21} {lat_str:<10} {C_DIM}#{tag}{C_RESET}")

    # Output Metrik Statistik
    print(f"\n{C_BOLD}{C_CYAN}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}                  LAPORAN METRIK KINERJA SUBSISTEM                    {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}======================================================================{C_RESET}")

    tlb_hit_rate = (mmu.tlb_hits / mmu.total_accesses) * 100
    pf_rate = (mmu.page_faults / mmu.total_accesses) * 100
    amat = mmu.total_latency_ns / mmu.total_accesses  # Average Memory Access Time

    print(f"Total Instruksi Memori : {C_BOLD}{mmu.total_accesses}{C_RESET}")
    print(f"TLB Hit Rate           : {C_GREEN if tlb_hit_rate > 50 else C_YELLOW}{tlb_hit_rate:.2f}%{C_RESET} ({mmu.tlb_hits}/{mmu.total_accesses})")
    print(f"Page Fault Rate        : {C_RED if pf_rate > 30 else C_GREEN}{pf_rate:.2f}%{C_RESET} ({mmu.page_faults}/{mmu.total_accesses})")
    print(f"Average Mem Latency    : {C_BOLD}{amat:,.2f} ns{C_RESET}")
    print(f"Total Accumulated Delay: {C_MAG}{mmu.total_latency_ns:,} ns{C_RESET}")

    # Visualisasi Frame Table Terisi
    print(f"\n{C_BOLD}State Physical Frame DRAM (LRU Order):{C_RESET}")
    frame_dump = []
    for pfn in mmu.frame_lru.keys():
        vpn = mmu.frames[pfn].vpn
        frame_dump.append(f"[Frame {pfn:02d} -> VPN 0x{vpn:05X}]")
    print(f"{C_BLUE}{' -> '.join(frame_dump)}{C_RESET}")
    print(f"{C_DIM}(Sisi kiri: Paling dingin/LRU target, Sisi kanan: MRU terkini){C_RESET}\n")


if __name__ == "__main__":
    run_workload_simulation()
    sys.exit(0)
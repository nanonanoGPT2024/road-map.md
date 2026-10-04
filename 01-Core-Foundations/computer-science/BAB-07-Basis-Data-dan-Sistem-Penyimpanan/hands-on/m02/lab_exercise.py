#!/usr/bin/env python3
"""
Lab Hands-on: Virtual Memory Management & Page Replacement Simulation
Kategori: 01-Core-Foundations | Bab 07 - Modul 02 Deep Dive

Deskripsi:
Simulasi komparatif arsitektur subsistem Virtual Memory dan Memory Management
Unit (MMU). Mengimplementasikan TLB (Translation Lookaside Buffer), Page Table,
serta membandingkan 3 algoritma eviksi halaman fisik (FIFO, LRU, dan Clock/Second-Chance)
terhadap beban kerja dengan karakteristik spasial dan temporal locality.
"""

import sys
import time
import random
from collections import deque, OrderedDict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# ==============================================================================
# ANSI Color Codes untuk Visualisasi CLI
# ==============================================================================
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"

# ==============================================================================
# Definisi Struktur Data Virtual Memory
# ==============================================================================
@dataclass
class PageTableEntry:
    frame_number: Optional[int] = None
    valid: bool = False
    referenced: bool = False
    dirty: bool = False

@dataclass
class MemoryAccess:
    vpn: int          # Virtual Page Number
    offset: int       # Byte offset dalam page
    is_write: bool    # True jika operasi penulisan (DIRTY bit update)

# ==============================================================================
# Translation Lookaside Buffer (TLB)
# ==============================================================================
class TLB:
    """Hardware cache berkecepatan tinggi untuk translasi VPN -> PFN."""
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        # Menggunakan OrderedDict untuk LRU cache internal pada TLB
        self.entries: OrderedDict[int, int] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def lookup(self, vpn: int) -> Optional[int]:
        """Mencari mapping frame untuk VPN yang diberikan."""
        if vpn in self.entries:
            self.hits += 1
            self.entries.move_to_end(vpn)
            return self.entries[vpn]
        self.misses += 1
        return None

    def update(self, vpn: int, pfn: int) -> None:
        """Menambahkan/memperbarui entri TLB dengan kebijakan eviksi LRU."""
        if vpn in self.entries:
            self.entries.move_to_end(vpn)
        elif len(self.entries) >= self.capacity:
            self.entries.popitem(last=False)
        self.entries[vpn] = pfn

    def invalidate(self, vpn: int) -> None:
        """Flushing entri TLB saat page di-evict dari physical memory."""
        if vpn in self.entries:
            del self.entries[vpn]

# ==============================================================================
# Strategi Page Replacement (Eviction Algorithms)
# ==============================================================================
class PageReplacementPolicy:
    def __init__(self, num_frames: int):
        self.num_frames = num_frames

    def select_victim(self, page_table: Dict[int, PageTableEntry], frame_to_vpn: Dict[int, int]) -> int:
        raise NotImplementedError

    def on_page_access(self, vpn: int, pfn: int) -> None:
        pass

    def on_page_loaded(self, vpn: int, pfn: int) -> None:
        pass

class FIFOReplacement(PageReplacementPolicy):
    """First-In, First-Out: Mengeluarkan frame yang dialokasikan paling awal."""
    def __init__(self, num_frames: int):
        super().__init__(num_frames)
        self.queue = deque()

    def on_page_loaded(self, vpn: int, pfn: int) -> None:
        self.queue.append(pfn)

    def select_victim(self, page_table: Dict[int, PageTableEntry], frame_to_vpn: Dict[int, int]) -> int:
        return self.queue.popleft()

class LRUReplacement(PageReplacementPolicy):
    """Least Recently Used: Mengeluarkan frame yang paling lama tidak diakses."""
    def __init__(self, num_frames: int):
        super().__init__(num_frames)
        self.access_order = OrderedDict()

    def on_page_access(self, vpn: int, pfn: int) -> None:
        if pfn in self.access_order:
            self.access_order.move_to_end(pfn)

    def on_page_loaded(self, vpn: int, pfn: int) -> None:
        self.access_order[pfn] = True

    def select_victim(self, page_table: Dict[int, PageTableEntry], frame_to_vpn: Dict[int, int]) -> int:
        victim_pfn, _ = self.access_order.popitem(last=False)
        return victim_pfn

class ClockReplacement(PageReplacementPolicy):
    """Clock / Second-Chance Algorithm: Menggunakan bit 'referenced'."""
    def __init__(self, num_frames: int):
        super().__init__(num_frames)
        self.hand = 0

    def select_victim(self, page_table: Dict[int, PageTableEntry], frame_to_vpn: Dict[int, int]) -> int:
        while True:
            candidate_pfn = self.hand
            self.hand = (self.hand + 1) % self.num_frames
            
            vpn = frame_to_vpn.get(candidate_pfn)
            if vpn is None:
                return candidate_pfn

            entry = page_table[vpn]
            if not entry.referenced:
                # Ditemukan frame tanpa second chance
                return candidate_pfn
            else:
                # Reset bit reference (berikan kesempatan kedua)
                entry.referenced = False

# ==============================================================================
# Simulator MMU & Subsistem Memori
# ==============================================================================
class VirtualMemorySimulator:
    def __init__(self, num_frames: int, page_size: int, policy: PageReplacementPolicy, tlb_size: int = 4):
        self.num_frames = num_frames
        self.page_size = page_size
        self.policy = policy
        self.tlb = TLB(capacity=tlb_size)
        self.page_table: Dict[int, PageTableEntry] = {}
        self.frame_to_vpn: Dict[int, int] = {}
        self.free_frames = list(range(num_frames))
        
        # Metrik performa
        self.page_faults = 0
        self.disk_writes = 0
        self.total_accesses = 0

    def access_memory(self, access: MemoryAccess) -> Tuple[int, bool, bool]:
        """
        Translasi virtual address ke physical address.
        Mengembalikan: (physical_address, is_tlb_hit, is_page_fault)
        """
        self.total_accesses += 1
        vpn = access.vpn
        offset = access.offset
        
        # 1. Periksa TLB
        pfn = self.tlb.lookup(vpn)
        tlb_hit = (pfn is not None)
        page_fault = False

        if not tlb_hit:
            # 2. Periksa Page Table (TLB Miss)
            if vpn not in self.page_table:
                self.page_table[vpn] = PageTableEntry()

            entry = self.page_table[vpn]
            if not entry.valid:
                # 3. Handle Page Fault
                self.page_faults += 1
                page_fault = True
                pfn = self._handle_page_fault(vpn)
            else:
                pfn = entry.frame_number

            # Update TLB
            self.tlb.update(vpn, pfn)

        # 4. Sinkronisasi state halaman
        entry = self.page_table[vpn]
        entry.referenced = True
        if access.is_write:
            entry.dirty = True

        self.policy.on_page_access(vpn, pfn)
        physical_address = (pfn * self.page_size) + offset
        return physical_address, tlb_hit, page_fault

    def _handle_page_fault(self, vpn: int) -> int:
        """Mengalokasikan frame kosong atau melakukan page eviction."""
        if self.free_frames:
            pfn = self.free_frames.pop(0)
        else:
            # Physical memory penuh, lakukan eviksi
            pfn = self.policy.select_victim(self.page_table, self.frame_to_vpn)
            old_vpn = self.frame_to_vpn[pfn]
            victim_entry = self.page_table[old_vpn]
            
            # Jika dirty, flush ke swap disk
            if victim_entry.dirty:
                self.disk_writes += 1
            
            # Invalidation
            victim_entry.valid = False
            victim_entry.frame_number = None
            self.tlb.invalidate(old_vpn)

        # Mapping frame baru
        self.page_table[vpn].frame_number = pfn
        self.page_table[vpn].valid = True
        self.page_table[vpn].dirty = False
        self.frame_to_vpn[pfn] = vpn
        self.policy.on_page_loaded(vpn, pfn)
        return pfn

# ==============================================================================
# Generator Beban Kerja Memori (Workload Synthetic)
# ==============================================================================
def generate_workload(num_requests: int = 120, num_pages: int = 16, page_size: int = 4096) -> List[MemoryAccess]:
    """
    Menghasilkan pola akses campuran:
    - 70% Temporal/Spatial Locality (Hot working set)
    - 30% Random Uniform Scanning (Cold access / Sequential scan)
    """
    random.seed(42)
    workload = []
    hot_pages = [1, 2, 3, 4]  # Working set inti

    for _ in range(num_requests):
        is_write = random.random() < 0.25
        offset = random.randint(0, page_size - 1)
        
        if random.random() < 0.70:
            vpn = random.choice(hot_pages)
        else:
            vpn = random.randint(0, num_pages - 1)
            
        workload.append(MemoryAccess(vpn=vpn, offset=offset, is_write=is_write))
    return workload

# ==============================================================================
# Eksekusi Utama dan Pelaporan
# ==============================================================================
def main():
    print(f"{CLR_BOLD}{CLR_CYAN}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}   CORE CS: VIRTUAL MEMORY SUBSYSTEM & PAGE REPLACEMENT LAB      {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}================================================================={CLR_RESET}")

    PAGE_SIZE = 4096      # 4KB per page
    NUM_FRAMES = 4        # 4 Physical Frames (Memori fisik terbatas untuk simulasi thrashing)
    NUM_REQUESTS = 100    # Total siklus instruksi memori
    TLB_CAPACITY = 3      # 3 Entri TLB hardware

    print(f"{CLR_WHITE}Konfigurasi Hardware Simulasi:{CLR_RESET}")
    print(f"  • Ukuran Frame/Page : {CLR_YELLOW}{PAGE_SIZE} Bytes (4 KiB){CLR_RESET}")
    print(f"  • Kapasitas Ram     : {CLR_YELLOW}{NUM_FRAMES} Frame ({NUM_FRAMES * PAGE_SIZE // 1024} KiB){CLR_RESET}")
    print(f"  • Kapasitas TLB     : {CLR_YELLOW}{TLB_CAPACITY} Entri (Fully Associative LRU){CLR_RESET}")
    print(f"  • Jumlah Request    : {CLR_YELLOW}{NUM_REQUESTS} Akses Memori{CLR_RESET}\n")

    workload = generate_workload(num_requests=NUM_REQUESTS, num_pages=12, page_size=PAGE_SIZE)

    policies = [
        ("FIFO (First-In, First-Out)", FIFOReplacement(NUM_FRAMES)),
        ("LRU (Least Recently Used)",  LRUReplacement(NUM_FRAMES)),
        ("Clock (Second-Chance)",      ClockReplacement(NUM_FRAMES))
    ]

    benchmark_results = []

    for name, policy in policies:
        sim = VirtualMemorySimulator(num_frames=NUM_FRAMES, page_size=PAGE_SIZE, policy=policy, tlb_size=TLB_CAPACITY)
        
        # Eksekusi simulasi
        trace_sample = []
        for i, req in enumerate(workload):
            paddr, tlb_hit, page_fault = sim.access_memory(req)
            if i < 8:  # Ambil trace untuk 8 langkah pertama
                trace_sample.append((req.vpn, req.offset, req.is_write, paddr, tlb_hit, page_fault))

        benchmark_results.append({
            "name": name,
            "sim": sim,
            "trace": trace_sample
        })

    # Tampilkan Execution Trace untuk LRU sebagai sample teknis
    print(f"{CLR_BOLD}{CLR_MAGENTA}--- MMU TRANSLATION TRACE SAMPLE (Algoritma: LRU) ---{CLR_RESET}")
    print(f"{CLR_WHITE}VPN   Offset  Aksi   TLB Status   Page Status   Physical Addr{CLR_RESET}")
    print("-" * 65)
    for vpn, off, is_wr, paddr, tlb_h, pf in benchmark_results[1]["trace"]:
        act_str = f"{CLR_RED}WRITE{CLR_RESET}" if is_wr else f"{CLR_GREEN}READ {CLR_RESET}"
        tlb_str = f"{CLR_GREEN}HIT {CLR_RESET}" if tlb_h else f"{CLR_YELLOW}MISS{CLR_RESET}"
        pf_str  = f"{CLR_RED}FAULT{CLR_RESET}" if pf else f"{CLR_BLUE}VALID{CLR_RESET}"
        print(f"0x{vpn:02X}  0x{off:03X}   {act_str}  {tlb_str}        {pf_str}         0x{paddr:06X}")
    print("-" * 65 + "\n")

    # Rekapitulasi Metrik Performa
    print(f"{CLR_BOLD}{CLR_WHITE}--- KOMPARASI PERFORMA PAGE REPLACEMENT POLICIES ---{CLR_RESET}")
    print(f"{'Kebijakan (Policy)':<28} | {'TLB Hit %':<10} | {'Fault Rate':<12} | {'Disk Writes':<11} | {'Effective Time':<14}")
    print("-" * 85)

    # Asumsi Latensi Perangkat Keras:
    # TLB Hit = 1ns, Memory Access = 100ns, Swap/Disk Latency = 10,000,000ns (10ms)
    TLB_LATENCY = 1
    MEM_LATENCY = 100
    DISK_LATENCY = 10_000_000

    for res in benchmark_results:
        sim = res["sim"]
        tlb_rate = (sim.tlb.hits / sim.total_accesses) * 100
        fault_rate = (sim.page_faults / sim.total_accesses) * 100
        
        # Kalkulasi Effective Memory Access Time (EMAT) dalam mikrodetik
        total_time_ns = (
            (sim.tlb.hits * (TLB_LATENCY + MEM_LATENCY)) +
            (sim.tlb.misses * (TLB_LATENCY + (2 * MEM_LATENCY))) +
            (sim.page_faults * DISK_LATENCY) +
            (sim.disk_writes * DISK_LATENCY)
        )
        emat_us = (total_time_ns / sim.total_accesses) / 1000.0

        print(f"{res['name']:<28} | "
              f"{CLR_CYAN}{tlb_rate:6.2f}%{CLR_RESET}   | "
              f"{CLR_YELLOW}{fault_rate:6.2f}% ({sim.page_faults:02d}){CLR_RESET} | "
              f"{CLR_RED}{sim.disk_writes:4d} pages{CLR_RESET} | "
              f"{CLR_GREEN}{emat_us:10.2f} µs{CLR_RESET}")

    print("-" * 85)
    print(f"{CLR_BOLD}{CLR_GREEN}[✔] Analisis Selesai:{CLR_RESET} "
          f"Algoritma LRU dan Clock secara konsisten menekan tingkat Page Fault\n"
          f"dibandingkan FIFO dengan mengeksploitasi locality of reference.")

if __name__ == "__main__":
    main()